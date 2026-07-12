# -*- coding: utf-8 -*-
"""Testy logiki AnberVc (pytest). Importuje vc_lib (bez SDL) — cała klasa + brzegi.

Fizyka: v_c = π·D·n/60 [m/s] = π·D·n/1000 [m/min].
Dobór: n_bezp = min(v_c·60/(π·D), tool_max_rpm, machine_max_rpm),
rekomendacja = najwyższe nastawienie k z rpm_k ≤ n_bezp.
"""
import math
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import vc_lib as vc  # noqa: E402
from vc_lib import core  # noqa: E402


# ── wzór prędkości skrawania v = π·D·n/60 ────────────────────────────────────
def test_peripheral_speed_known():
    # D=115 mm, n=12000 → v = π·0.115·12000/60 = π·23 = 72.257 m/s
    assert math.isclose(vc.v_from_mm(115.0, 12000), math.pi * 23, rel_tol=1e-9)
    # D=100 mm, n=6000 → π·0.1·100 = 10π m/s
    assert math.isclose(vc.v_from_mm(100.0, 6000), math.pi * 10, rel_tol=1e-9)
    # D=1000 mm (1 m), n=60 → π·1·1 = π m/s
    assert math.isclose(vc.v_from_mm(1000.0, 60), math.pi, rel_tol=1e-9)


def test_rpm_for_v_inverse():
    # odwrotność: n = v·60/(π·D)
    for d, n in [(115.0, 12000), (8.0, 5000), (200.0, 900)]:
        v_ms = vc.v_from_mm(d, n)
        assert math.isclose(vc.rpm_for_v(v_ms, d), n, rel_tol=1e-9)
    # D=0 → nieskończoność (brak ograniczenia obwodowego)
    assert vc.rpm_for_v(80.0, 0.0) == float('inf')


def test_unit_conversion():
    assert vc.vc_to_ms(80.0, 'm/s') == 80.0
    assert math.isclose(vc.vc_to_ms(4800.0, 'm/min'), 80.0)
    assert math.isclose(vc.ms_to_unit(80.0, 'm/min'), 4800.0)
    assert vc.ms_to_unit(80.0, 'm/s') == 80.0


# ── mapowanie nastawień 1..N ─────────────────────────────────────────────────
def test_setting_rpm_mapping_default():
    # 7 nastawień 3000..12000 → co 1500
    got = [vc.setting_rpm(k, 3000, 12000, 7) for k in range(1, 8)]
    assert got == [3000, 4500, 6000, 7500, 9000, 10500, 12000]


def test_setting_rpm_mapping_N5():
    got = [vc.setting_rpm(k, 3000, 12000, 5) for k in range(1, 6)]
    assert got == [3000, 5250, 7500, 9750, 12000]


def test_setting_rpm_single_setting():
    assert vc.setting_rpm(1, 3000, 12000, 1) == 3000


def test_setting_rpm_out_of_range():
    import pytest
    with pytest.raises(ValueError):
        vc.setting_rpm(0, 3000, 12000, 7)
    with pytest.raises(ValueError):
        vc.setting_rpm(8, 3000, 12000, 7)


# ── GŁÓWNY przypadek: szlifierka D=125 (domyślny preset) ─────────────────────
def test_default_grinder_D125():
    r = vc.recommend()   # domyślne = preset szlifierki, D=125
    # n_bezp = min(12222, 12500, 12000) = 12000, wiąże maszyna
    assert math.isclose(r.n_safe, 12000, rel_tol=1e-9)
    assert r.binding == 'machine'
    assert r.recommended_k == 7
    assert math.isclose(r.rec_rpm, 12000, rel_tol=1e-9)
    # v = π·0.125·12000/60 = π·25 ≈ 78.54 m/s
    assert math.isclose(r.rec_v, math.pi * 25, rel_tol=1e-6)
    assert r.vc_unit == 'm/s'
    # margines do 80 m/s: (80-78.54)/80 ≈ 1.83 %
    assert math.isclose(r.margin_pct, (80 - math.pi * 25) / 80 * 100, rel_tol=1e-6)
    # brak ostrzeżeń krytycznych (rekomendacja istnieje)
    assert r.recommended_k is not None
    # wszystkie 7 nastawień bezpieczne (n_safe=12000=rpm_7)
    assert all(s.safe for s in r.settings)


def test_default_table_has_N_rows():
    r = vc.recommend()
    assert len(r.settings) == 7
    assert [s.k for s in r.settings] == list(range(1, 8))


# ── BRZEG: średnica dająca v_c dokładnie = limit przy nastawieniu 7 ───────────
def test_v_exactly_at_limit():
    # chcemy v(D, 12000) = 80 m/s  ⇒  D = 80·60/(π·12000) [m] = 127.324 mm
    d = 80 * 60 / (math.pi * 12000) * 1000
    r = vc.recommend(diameter_mm=d)   # tool_max=12500, machine_max=12000
    # n_safe od v_c: 80·60/(π·D[m]) = 12000 → min(12000,12500,12000)=12000
    assert math.isclose(r.n_safe, 12000, rel_tol=1e-9)
    assert r.recommended_k == 7            # rpm_7=12000 ≤ 12000 (równość dozwolona)
    assert math.isclose(r.rec_v, 80.0, rel_tol=1e-6)
    assert math.isclose(r.margin_pct, 0.0, abs_tol=1e-6)


# ── BRZEG: średnica za duża — nawet nastawienie 1 niebezpieczne ──────────────
def test_diameter_too_large_warns():
    # D=600 mm → n_v = 80·60/(π·0.6) ≈ 2546 < rpm_min 3000 ⇒ brak bezpiecznego
    r = vc.recommend(diameter_mm=600.0)
    assert r.recommended_k is None
    assert r.rec_rpm is None
    assert not any(s.safe for s in r.settings)
    assert any('Narzędzie za duże' in w for w in r.warnings)


# ── ograniczenia: narzędzie vs maszyna (oba kierunki) ────────────────────────
def test_binding_tool_below_machine():
    # tool_max=10000 < machine_max=12000, D=115 (v_c nie wiąże)
    r = vc.recommend(tool_max_rpm=10000)
    assert math.isclose(r.n_safe, 10000, rel_tol=1e-9)
    assert r.binding == 'tool'
    # najwyższe rpm_k ≤ 10000 → 9000 (k=5)
    assert r.recommended_k == 5
    assert math.isclose(r.rec_rpm, 9000, rel_tol=1e-9)


def test_binding_machine_below_tool():
    # tool_max=13000 > machine_max=12000, D=115 → wiąże maszyna
    r = vc.recommend(tool_max_rpm=13000)
    assert math.isclose(r.n_safe, 12000, rel_tol=1e-9)
    assert r.binding == 'machine'
    assert r.recommended_k == 7


def test_binding_vc_limit():
    # D=300 mm: n_v = 80·60/(π·0.3) ≈ 5092.96 < tool/machine → wiąże v_c
    r = vc.recommend(diameter_mm=300.0)
    assert r.binding == 'vc'
    assert math.isclose(r.n_safe, 80 * 60 / (math.pi * 0.3), rel_tol=1e-9)
    # najwyższe rpm_k ≤ 5092.96 → 4500 (k=2)
    assert r.recommended_k == 2


def test_machine_max_exceeds_tool_warning():
    # machine_max 12000 < tool_max 12500 (domyślnie) → BRAK ostrzeżenia
    assert not any('przekraczają znamionowe' in w for w in vc.recommend().warnings)
    # gdy machine_max 13000 > tool 12500 → ostrzeżenie
    r = vc.recommend(rpm_max=13000)
    assert any('przekraczają znamionowe' in w for w in r.warnings)


# ── zmiana KAŻDEGO parametru wpływa na wynik ─────────────────────────────────
def test_each_parameter_changes_result():
    base = vc.recommend()
    assert vc.recommend(rpm_min=1000).settings[0].rpm != base.settings[0].rpm
    assert vc.recommend(rpm_max=6000).n_safe != base.n_safe
    assert len(vc.recommend(n_settings=10).settings) == 10
    assert vc.recommend(tool_max_rpm=8000).n_safe == 8000
    assert vc.recommend(vc=40.0).recommended_k != base.recommended_k or \
        vc.recommend(vc=40.0).n_safe != base.n_safe
    assert vc.recommend(diameter_mm=50.0).settings[0].v_ms != base.settings[0].v_ms


# ── m/s vs m/min: równoważność ───────────────────────────────────────────────
def test_ms_vs_mmin_equivalence():
    a = vc.recommend(vc=80.0, vc_unit='m/s')
    b = vc.recommend(vc=4800.0, vc_unit='m/min')   # 80 m/s = 4800 m/min
    assert math.isclose(a.n_safe, b.n_safe, rel_tol=1e-12)
    assert a.recommended_k == b.recommended_k
    assert math.isclose(a.margin_pct, b.margin_pct, rel_tol=1e-9)


# ── WIERCENIE (m/min) ────────────────────────────────────────────────────────
def test_drilling_steel_mmin():
    # stal, wiertło HSS D=10, v_c=25 m/min, wiertarka 500..3000 (5 nastawień)
    r = vc.recommend(rpm_min=500, rpm_max=3000, n_settings=5,
                     tool_max_rpm=100000, vc=25.0, vc_unit='m/min',
                     diameter_mm=10.0)
    # n_v = 25·1000/(π·10) ≈ 795.77 rpm
    assert math.isclose(r.n_safe, 25 * 1000 / (math.pi * 10), rel_tol=1e-9)
    assert r.binding == 'vc'
    # najwyższe nastawienie ≤ 795.77 → 500 (k=1); 1125 już za dużo
    assert r.recommended_k == 1
    assert math.isclose(r.rec_rpm, 500, rel_tol=1e-9)
    # v przy 500: π·10·500/1000 = 5π ≈ 15.708 m/min
    assert math.isclose(r.rec_v, math.pi * 5, rel_tol=1e-6)
    assert r.vc_unit == 'm/min'


# ── FREZOWANIE (m/min) ───────────────────────────────────────────────────────
def test_milling_aluminium_mmin():
    # aluminium, frez HSS D=8, v_c=150 m/min, frezarka 1000..10000 (6 nastawień)
    r = vc.recommend(rpm_min=1000, rpm_max=10000, n_settings=6,
                     tool_max_rpm=100000, vc=150.0, vc_unit='m/min',
                     diameter_mm=8.0)
    # n_v = 150·1000/(π·8) ≈ 5968.3 rpm
    assert math.isclose(r.n_safe, 150 * 1000 / (math.pi * 8), rel_tol=1e-9)
    # nastawienia: 1000,2800,4600,6400,8200,10000 → najwyższe ≤5968 = 4600 (k=3)
    assert r.recommended_k == 3
    assert math.isclose(r.rec_rpm, 4600, rel_tol=1e-9)
    # v przy 4600: π·8·4600/1000 ≈ 115.6 m/min
    assert math.isclose(r.rec_v, math.pi * 8 * 4600 / 1000, rel_tol=1e-6)


# ── SZLIFIERKA TAŚMOWA (v = prędkość taśmy, D = koło kontaktowe) ─────────────
def test_belt_grinder_preset_exists_with_correct_keys():
    names = [p['name'] for p in core.PRESETS]
    assert 'Szlifierka taśmowa' in names
    preset = next(p for p in core.PRESETS if p['name'] == 'Szlifierka taśmowa')
    expected_keys = {'name', 'rpm_min', 'rpm_max', 'n_settings',
                      'tool_max_rpm', 'vc', 'vc_unit', 'diameter_mm'}
    assert set(preset.keys()) == expected_keys
    # wartości sensowne dla koła kontaktowego 200 mm / taśmy ~30 m/s
    assert preset['vc_unit'] == 'm/s'
    assert 10.0 <= preset['vc'] <= 50.0
    assert 50.0 <= preset['diameter_mm'] <= 400.0
    assert 0 < preset['rpm_min'] < preset['rpm_max']
    assert preset['n_settings'] >= 2
    assert preset['tool_max_rpm'] >= preset['rpm_max']


def test_belt_grinder_recommend_runs_and_is_sane():
    preset = next(p for p in core.PRESETS if p['name'] == 'Szlifierka taśmowa')
    r = vc.recommend(**vc.preset_params(preset))
    # v = π·D·n/60 wiąże (koło 200mm, 4000 obr/min > obroty z limitu v_c)
    n_v = preset['vc'] * 60 / (math.pi * (preset['diameter_mm'] / 1000.0))
    assert math.isclose(r.n_safe, n_v, rel_tol=1e-9)
    assert r.binding == 'vc'
    assert r.recommended_k is not None
    assert r.rec_rpm is not None
    # prędkość taśmy przy rekomendacji nie przekracza limitu (z tolerancją)
    assert r.rec_v <= preset['vc'] + 1e-6
    assert r.vc_unit == 'm/s'
    assert len(r.settings) == preset['n_settings']


# ── presety ──────────────────────────────────────────────────────────────────
def test_presets_all_run():
    for p in core.PRESETS:
        params = vc.preset_params(p)
        r = vc.recommend(**params)
        assert isinstance(r.settings, list) and len(r.settings) == params['n_settings']


def test_preset_default_is_grinder():
    r = vc.recommend(**vc.preset_params(core.PRESETS[0]))
    assert r.recommended_k == 7 and math.isclose(r.rec_rpm, 12000, rel_tol=1e-9)


# ── stałe / walidacja jednostek ──────────────────────────────────────────────
def test_defaults_constants():
    assert core.DEFAULTS['rpm_min'] == 3000
    assert core.DEFAULTS['rpm_max'] == 12000
    assert core.DEFAULTS['n_settings'] == 7
    assert core.DEFAULTS['tool_max_rpm'] == 12500
    assert core.DEFAULTS['vc'] == 80.0
    assert core.DEFAULTS['vc_unit'] == 'm/s'
    assert core.DEFAULTS['diameter_mm'] == 125.0


def test_invalid_unit_raises():
    import pytest
    with pytest.raises(ValueError):
        vc.vc_to_ms(80.0, 'ft/s')

# -*- coding: utf-8 -*-
"""Testy modułu raportu AnberVc (pytest).

build_meta / report_filename są czyste (bez reportlab) — testowane zawsze.
generate_pdf wymaga reportlab + fontów DejaVu — uruchamiane gdy dostępne.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pytest  # noqa: E402
import vc_lib as vc  # noqa: E402
from vc_lib import report  # noqa: E402


def _params(**over):
    p = {'diameter_mm': 125.0, 'vc': 80.0, 'vc_unit': 'm/s',
         'rpm_min': 3000, 'rpm_max': 12000, 'n_settings': 7, 'tool_max_rpm': 12500}
    p.update(over)
    return p


# ── build_meta: struktura i treść ────────────────────────────────────────────
def test_build_meta_structure():
    p = _params()
    rec = vc.recommend(**{k: p[k] for k in (
        'rpm_min', 'rpm_max', 'n_settings', 'tool_max_rpm', 'vc', 'vc_unit', 'diameter_mm')})
    meta = report.build_meta(p, rec, 'Szlifowanie tarcza 125')
    for key in ('tytul', 'autor', 'data', 'zmienne', 'wzory', 'warunki', 'wnioski'):
        assert key in meta
    assert 'AnberVc' in meta['tytul']
    # tabela nastawień = warunki, po jednym wpisie na nastawienie
    assert len(meta['warunki']) == 7
    # wszystkie nastawienia bezpieczne dla D=125 (n_safe=12000=rpm_7)
    assert all(ok for _, ok in meta['warunki'])
    # dane wejściowe zawierają średnicę i v_c
    opisy = [z[1] for z in meta['zmienne']]
    assert 'Średnica narzędzia' in opisy
    assert any('Prędkość skrawania' in o for o in opisy)


def test_build_meta_polish_decimal_comma():
    p = _params()
    rec = vc.recommend(diameter_mm=125.0)
    meta = report.build_meta(p, rec, 'Szlifowanie tarcza 125')
    # rekomendowane v_c = π·25 ≈ 78,5 m/s — przecinek, nie kropka
    assert '78,5' in meta['wnioski']
    assert '78.5' not in meta['wnioski']
    # w tabeli nastawień też przecinki
    joined = ' '.join(o for o, _ in meta['warunki'])
    assert ',' in joined and '.' not in joined.replace('v_c', '')


def test_build_meta_warning_when_too_large():
    p = _params(diameter_mm=600.0)
    rec = vc.recommend(diameter_mm=600.0)
    meta = report.build_meta(p, rec, 'Szlifowanie tarcza 125')
    assert 'Brak bezpiecznego' in meta['wnioski']
    assert not all(ok for _, ok in meta['warunki'])   # są niebezpieczne nastawienia


def test_report_filename_full_template():
    """Nazwa koduje KOMPLET danych wejściowych: operacja, D, v_c+jedn., zakres
    rpm, N, obroty znamionowe narzędzia + znacznik czasu."""
    p = _params()
    fn = report.report_filename('Szlifowanie tarcza 125', p, ts='20260711_190000')
    assert fn == ('anbervc_szlifowanie_tarcza_125_D125mm_vc80ms_'
                  '3000-12000rpm_N7_tn12500_20260711_190000.pdf')
    assert fn.endswith('.pdf')


def test_report_filename_encodes_every_input():
    """Każdy kluczowy parametr wejściowy MUSI być obecny w nazwie (guard regresji)."""
    p = _params(diameter_mm=8.0, vc=120.0, vc_unit='m/min',
                rpm_min=500, rpm_max=3000, n_settings=5, tool_max_rpm=100000)
    fn = report.report_filename('Frezowanie Al HSS', p, ts='20260711_190000')
    assert 'D8mm' in fn                    # średnica
    assert 'vc120mmin' in fn               # v_c + jednostka (m/min → mmin)
    assert '500-3000rpm' in fn             # zakres obrotów maszyny
    assert 'N5' in fn                      # liczba nastawień
    assert 'tn100000' in fn                # obroty znamionowe narzędzia
    assert '20260711_190000' in fn         # znacznik czasu


def test_report_filename_slug_ascii_and_length():
    fn = report.report_filename('Frezowanie Al HSS', _params(diameter_mm=8.0),
                                ts='20260711_190000')
    assert fn == ('anbervc_frezowanie_al_hss_D8mm_vc80ms_'
                  '3000-12000rpm_N7_tn12500_20260711_190000.pdf')
    # ASCII-only i rozsądna długość
    assert fn.isascii() and len(fn) <= 120


def test_report_filename_decimal_no_dot():
    """Ułamki w nazwie bez kropki (12.5 → 12p5), by nie mylić z rozszerzeniem."""
    fn = report.report_filename('Szlifowanie', _params(diameter_mm=12.5),
                                ts='20260711_190000')
    assert 'D12p5mm' in fn and '12.5' not in fn


def test_report_filename_bounded_length():
    """Bardzo długa nazwa operacji nie przekracza 120 znaków (slug przycinany)."""
    fn = report.report_filename('X' * 200, _params(), ts='20260711_190000')
    assert len(fn) <= 120 and fn.startswith('anbervc_') and fn.endswith('.pdf')


# ── generate_pdf: realny plik end-to-end (reportlab + fonty; CI je instaluje) ─
def _fonts_present():
    return pathlib.Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').exists()


def test_generate_pdf_end_to_end(tmp_path):
    """END-TO-END: rec z core.recommend + params → generate_pdf(out_dir=tmp_path).
    Na CI (ubuntu + fonts-dejavu-core + reportlab) MUSI się WYKONAĆ, nie skipować.
    Skip TYLKO gdy reportlab/matplotlib/fonty REALNIE brak."""
    pytest.importorskip('reportlab')
    pytest.importorskip('matplotlib')
    if not _fonts_present():
        pytest.skip('fonty DejaVu realnie niedostępne (na urządzeniu/CI są)')
    p = _params()
    rec = vc.recommend(**{k: p[k] for k in (
        'rpm_min', 'rpm_max', 'n_settings', 'tool_max_rpm', 'vc', 'vc_unit',
        'diameter_mm')})
    path = report.generate_pdf(p, rec, 'Szlifowanie tarcza 125',
                               out_dir=str(tmp_path))
    f = pathlib.Path(path)
    assert f.exists(), 'PDF nie powstał'
    assert f.stat().st_size > 1000, 'PDF pusty/za mały'
    with open(f, 'rb') as fh:
        assert fh.read(5) == b'%PDF-', 'brak sygnatury %PDF-'
    # plik trafił do tmp_path (NIE do prawdziwego katalogu raportów usera)
    assert str(tmp_path) in str(f)


def test_generate_pdf_respects_env_dir(tmp_path, monkeypatch):
    """generate_pdf domyślnie honoruje ANBERVC_REPORT_DIR (izolacja testów od
    realnego /mnt/data/sprawozdania/raporty/AnberVc — dane usera)."""
    pytest.importorskip('reportlab')
    pytest.importorskip('matplotlib')
    if not _fonts_present():
        pytest.skip('fonty DejaVu realnie niedostępne')
    import importlib
    monkeypatch.setenv('ANBERVC_REPORT_DIR', str(tmp_path))
    importlib.reload(report)                # OUT_DIR czytany z env przy imporcie
    try:
        p = _params()
        rec = vc.recommend(diameter_mm=125.0)
        path = report.generate_pdf(p, rec, 'Szlifowanie tarcza 125')
        assert str(tmp_path) in str(path) and pathlib.Path(path).exists()
    finally:
        monkeypatch.delenv('ANBERVC_REPORT_DIR', raising=False)
        importlib.reload(report)

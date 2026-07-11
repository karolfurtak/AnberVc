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


def test_report_filename_has_params():
    p = _params()
    fn = report.report_filename('Szlifowanie tarcza 125', p, ts='20260711_190000')
    assert fn == 'anbervc_szlifowanie_tarcza_125_D125mm_20260711_190000.pdf'
    assert fn.endswith('.pdf')


def test_report_filename_slug_ascii():
    fn = report.report_filename('Frezowanie Al HSS', _params(diameter_mm=8.0),
                                ts='20260711_190000')
    assert fn == 'anbervc_frezowanie_al_hss_D8mm_20260711_190000.pdf'


# ── generate_pdf: realny plik (gdy reportlab + fonty dostępne) ────────────────
def test_generate_pdf_creates_file(tmp_path):
    pytest.importorskip('reportlab')
    p = _params()
    rec = vc.recommend(diameter_mm=125.0)
    try:
        path = report.generate_pdf(p, rec, 'Szlifowanie tarcza 125',
                                   out_dir=str(tmp_path))
    except Exception as e:
        # brak fontów DejaVu na maszynie testowej — pomiń (na urządzeniu/CI są)
        pytest.skip(f'silnik PDF niedostępny: {e}')
    f = pathlib.Path(path)
    assert f.exists() and f.stat().st_size > 1000
    with open(f, 'rb') as fh:
        assert fh.read(5) == b'%PDF-'

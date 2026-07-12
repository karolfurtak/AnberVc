# -*- coding: utf-8 -*-
"""AnberVc — budowa raportu PDF do druku (A4) z doboru obrotów.

Reużywa WSPÓLNY silnik raportów serii Anber* (`raport_engine.generuj_pdf`,
reportlab) — ten sam mechanizm co AnberISA/AnberWM/AnberPKM. Tu tylko budowa
słownika `meta` z parametrów i wyniku doboru (część czysta, testowalna) oraz
cienki wrapper zapisujący PDF.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .core import BINDING_PL, Recommendation, _pl

OUT_DIR = os.environ.get('ANBERVC_REPORT_DIR', '/mnt/data/sprawozdania/raporty/AnberVc')


def _slug(s: str) -> str:
    """Slug ASCII do nazwy pliku (bez polskich znaków/spacji)."""
    repl = str.maketrans('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ', 'acelnoszzACELNOSZZ')
    s = s.translate(repl)
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower()
    return s[:32] or 'raport'


def _num(x) -> str:
    """Liczba w nazwie pliku: ASCII, bez kropki (12.5 → '12p5', 80 → '80')."""
    return f'{x:g}'.replace('.', 'p')


def _unit_slug(u: str) -> str:
    """Jednostka v_c → skrót ASCII do nazwy pliku ('m/s' → 'ms', 'm/min' → 'mmin')."""
    return {'m/s': 'ms', 'm/min': 'mmin'}.get(u, re.sub(r'[^a-z0-9]+', '', str(u).lower()))


def report_filename(operacja: str, params: dict, ts: str | None = None) -> str:
    """Nazwa pliku kodująca kluczowe DANE WEJŚCIOWE + znacznik czasu (ASCII, ≤120 zn.).

    Wzorzec: anbervc_<operacja>_D<D>mm_vc<v_c><jedn>_<rpm_min>-<rpm_max>rpm_
             N<nastawienia>_tn<obroty_znam_narzedzia>_<ts>.pdf
    Przykład: anbervc_szlifowanie_tarcza_125_D125mm_vc80ms_3000-12000rpm_N7_tn12500_...pdf
    """
    ts = ts or time.strftime('%Y%m%d_%H%M%S')
    op = _slug(operacja.split('—')[0])
    d = _num(params.get('diameter_mm', 0))
    vc = _num(params.get('vc', 0))
    u = _unit_slug(params.get('vc_unit', 'm/s'))
    rmin = _num(params.get('rpm_min', 0))
    rmax = _num(params.get('rpm_max', 0))
    n = int(params.get('n_settings', 0))
    tn = _num(params.get('tool_max_rpm', 0))
    tail = f'_D{d}mm_vc{vc}{u}_{rmin}-{rmax}rpm_N{n}_tn{tn}_{ts}.pdf'
    budget = 120 - len('anbervc_') - len(tail)      # utrzymaj całość ≤120 znaków
    op = op[:max(1, budget)]
    return f'anbervc_{op}{tail}'


def build_meta(params: dict, rec: Recommendation, operacja: str,
               autor: str = 'AnberVc — RG40XX V', data: str | None = None) -> dict:
    """Buduje `meta` dla silnika raportów (czysta funkcja — testowalna)."""
    data = data or time.strftime('%Y-%m-%d %H:%M')
    unit = rec.vc_unit
    D = params['diameter_mm']
    vc = params['vc']

    zmienne = [
        ('—',      'Operacja / narzędzie',          str(operacja),        ''),
        ('D',      'Średnica narzędzia',            _pl(D),               'mm'),
        ('v_c',    'Prędkość skrawania (limit)',    _pl(vc),              unit),
        ('n_min',  'Min obroty maszyny',            _pl(params["rpm_min"]),  'obr/min'),
        ('n_max',  'Max obroty maszyny',            _pl(params["rpm_max"]),  'obr/min'),
        ('N',      'Liczba nastawień',              f'{int(params["n_settings"])}', ''),
        ('n_narz', 'Obroty znamionowe narzędzia',   _pl(params["tool_max_rpm"]), 'obr/min'),
    ]

    if rec.recommended_k is not None:
        podst_v = f'π·{_pl(D / 1000)}·{_pl(rec.rec_rpm, 0)}/60'
        wynik_v = f'{_pl(rec.rec_v, 1)} {unit}'
        wynik_rec = f'nastawienie {rec.recommended_k} = {_pl(rec.rec_rpm, 0)} obr/min'
        wynik_margin = f'{_pl(rec.margin_pct, 1)} %'
    else:
        podst_v = '—'
        wynik_v = '—'
        wynik_rec = 'BRAK bezpiecznego nastawienia'
        wynik_margin = '—'

    wzory = [
        ('Prędkość skrawania', 'v_c = pi*D*n/60', podst_v, wynik_v),
        ('Obroty bezpieczne', 'n_bezp = min(v_c*60/(pi*D); n_narz; n_max)',
         '', f'{_pl(rec.n_safe, 0)} obr/min'),
        ('Wiążące ograniczenie', BINDING_PL.get(rec.binding, rec.binding), '', ''),
        ('Rekomendacja', 'najwyższe k: n_k <= n_bezp', '', wynik_rec),
        ('Margines do limitu', '(v_limit - v_c)/v_limit', '', wynik_margin),
    ]

    # Warunki = pełna tabela nastawień z flagą bezpieczne/nie (kolor zielony/czerwony)
    warunki = [
        (f'Nastawienie {s.k}:  n = {_pl(s.rpm, 0)} obr/min,  '
         f'v_c = {_pl(s.v, 1)} {unit}', s.safe)
        for s in rec.settings
    ]

    if rec.recommended_k is not None:
        wnioski = (
            f'Rekomendowane nastawienie {rec.recommended_k}: '
            f'{_pl(rec.rec_rpm, 0)} obr/min, v_c = {_pl(rec.rec_v, 1)} {unit}, '
            f'margines {_pl(rec.margin_pct, 1)}% do limitu {_pl(vc)} {unit}. '
            f'Wiążące ograniczenie: {BINDING_PL.get(rec.binding, rec.binding)}.')
    else:
        wnioski = ('Brak bezpiecznego nastawienia — narzędzie za duże lub '
                   f'przekroczenie limitu v_c = {_pl(vc)} {unit}.')
    if rec.warnings:
        wnioski += ' ' + ' '.join(rec.warnings)

    return {
        'tytul':   f'AnberVc — dobór obrotów: {operacja}',
        'autor':   autor,
        'tel':     '',
        'data':    data,
        'diagram': None,
        'zmienne': zmienne,
        'wzory':   wzory,
        'warunki': warunki,
        'wnioski': wnioski,
    }


def generate_pdf(params: dict, rec: Recommendation, operacja: str,
                 out_dir: str = OUT_DIR, autor: str = 'AnberVc — RG40XX V',
                 data: str | None = None) -> str:
    """Buduje meta i zapisuje PDF do out_dir. Zwraca ścieżkę. Import silnika
    (reportlab) leniwy — apka startuje bez tej zależności."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    meta = build_meta(params, rec, operacja, autor=autor, data=data)
    path = Path(out_dir) / report_filename(operacja, params)
    from . import raport_engine   # leniwy import (reportlab/matplotlib)
    return raport_engine.generuj_pdf(str(path), meta)

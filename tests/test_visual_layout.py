# -*- coding: utf-8 -*-
"""Testy WIZUALNE AnberVc (pytest) — render realnej klatki (bez SDL/fb),
inspekcja PIKSELI wyrenderowanego obrazu.

Klasa regresji, którą te testy pilnują: „test przechodzi, apka na ekranie
wygląda zepsuta". Sam fakt, że _clip()/_wrap() ISTNIEJĄ i są wołane nie
gwarantuje, że naprawdę mieszczą tekst w 640×480 ani że pasek statusu
faktycznie wygląda jak pomarańczowy/czerwony prostokąt z tekstem — to
mierzymy tutaj wprost, metryką fontu PIL (ta sama, której używa _draw())
oraz odczytem pikseli z wyrenderowanej klatki.

Dwie klasy assercji:
  (a) SZEROKOŚĆ: najdłuższe realne treści (etykiety pól, wartości graniczne,
      stopka, etykiety wiązania, komunikaty statusu, ostrzeżenia) — po
      przejściu przez _clip()/_wrap() — MUSZĄ mieścić się w dostępnej
      szerokości KOLUMNY (nie tylko „w 640px w ogóle"), parametrycznie po
      WSZYSTKICH polach/komunikatach, nie próbce.
  (b) WYGLĄD paska statusu: po realnym _draw() na wyrenderowanej klatce musi
      być widoczny POMARAŃCZOWY prostokąt tła (Generuję/Zapisano) lub
      CZERWONY (błąd) we właściwym miejscu (y≈330, pełna szerokość), Z
      tekstem narysowanym NA nim (kolor tekstu paska wykryty w jego
      obszarze) — nie goły tekst na ciemnym tle strony.

app/main.py importuje `sdl2` bezwarunkowo i ładuje font z absolutnej ścieżki
konsoli (/usr/share/fonts/.../DejaVuSansMono.ttf) — obu może brakować na PC
dev. Poniżej: minimalny fake `sdl2` (jedyne użycie w trybie headless to
SDL_GetTicks()) + podmiana FONT_PATH na dostępny lokalnie monospace font PO
imporcie modułu (ta sama nazwa globalna, którą _draw() odczytuje w locie) —
logika layoutu (_clip/_wrap/_status_bar) jest identyczna z konsolową,
różni się tylko plik fontu użyty do pomiaru pikseli.
"""
import importlib.util
import os
import re
import sys
import types
import pathlib
import time

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_APP_DIR = _ROOT / 'app'
_MAIN_PY = _APP_DIR / 'main.py'
_SRC = _MAIN_PY.read_text(encoding='utf-8')

sys.path.insert(0, str(_ROOT))
import vc_lib as vc  # noqa: E402

W, H = 640, 480


# ── fake sdl2: main.py go importuje bezwarunkowo; w trybie headless jedyne
#    użycie to SDL_GetTicks() (timeout paska statusu) ─────────────────────────
def _install_fake_sdl2():
    if 'sdl2' in sys.modules and hasattr(sys.modules['sdl2'], 'SDL_GetTicks'):
        return
    fake = types.ModuleType('sdl2')
    fake.SDL_GetTicks = lambda: int(time.monotonic() * 1000)
    sys.modules['sdl2'] = fake


def _local_font_path(declared_path):
    """Font konsoli (DejaVuSansMono) może nie istnieć na PC dev — podstaw
    dostępny monospace. Sama LOGIKA _clip()/_wrap() (kod pod testem) jest
    identyczna niezależnie od pliku fontu; różnią się tylko dokładne piksele,
    co jest OK — mierzymy TĄ SAMĄ metryką (draw.textlength), której używa
    _draw() na konsoli."""
    if os.path.exists(declared_path):
        return declared_path
    for cand in (
        'C:/Windows/Fonts/consola.ttf',
        'C:/Windows/Fonts/CascadiaMono.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    ):
        if os.path.exists(cand):
            return cand
    pytest.skip('brak dostępnego fontu monospace do testu wizualnego')


def _load_app_main():
    _install_fake_sdl2()
    spec = importlib.util.spec_from_file_location('anbervc_app_main', _MAIN_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.FONT_PATH = _local_font_path(mod.FONT_PATH)
    return mod


@pytest.fixture(scope='module')
def app_main():
    return _load_app_main()


@pytest.fixture
def app(app_main):
    return app_main.VcApp(headless=True)


# ── budżety pikselowe wyciągnięte Z ŹRÓDŁA (nie przepisane ręcznie) ───────────
# Niezależność od dryfu: jeśli ktoś zmieni layout w _draw()/_status_bar() bez
# aktualizacji tego testu, liczby i tak są brane z main.py — test i tak
# wykryje realną regresję (bo mierzy PRAWDZIWE piksele wyrenderowanej treści
# względem TYCH SAMYCH liczb, które realnie sterują rysowaniem).
def _int_after(pattern):
    m = re.search(pattern, _SRC)
    assert m, f'wzorzec nie znaleziony w app/main.py: {pattern!r}'
    return int(m.group(1))


BUDGET_DESC = _int_after(r"_clip\(f'\{mark\} \{desc\}', self\.f_sm, (\d+)\)")
BUDGET_VAL = _int_after(r"_clip\(f'\{val_str\}\{unit_str\}', self\.f_md, (\d+)\)")
BUDGET_WARN = _int_after(r"_wrap\('! ' \+ w, self\.f_sm, (\d+)\)")
RX = _int_after(r"\n\s*rx = (\d+)\n")
BUDGET_BINDING = W - RX - 8   # matches literal `W - rx - 8` passed to _clip in _draw()
STATBAR_X0 = _int_after(r"x0, x1 = (\d+), W - 10")
STATBAR_PAD = _int_after(r"\n\s*pad = (\d+)\n")
BUDGET_STATBAR = (W - STATBAR_X0) - STATBAR_X0 - 2 * STATBAR_PAD

FOOTER_TEXT = re.search(
    r"self\._t\(12, H - 14,\s*\n\s*'([^']+)'", _SRC).group(1)


# ═══════════════════════════════════════════════════════════════════════════
# (a) SZEROKOŚĆ — najdłuższe realne treści muszą mieścić się w dostępnej
#     kolumnie po _clip()/_wrap() (parametrycznie, cała klasa, nie próbka)
# ═══════════════════════════════════════════════════════════════════════════

def test_footer_fits_screen_width(app):
    """Stopka NIE jest przycinana przez _clip/_wrap w kodzie — jeśli kiedyś
    urośnie (nowy skrót klawiszowy dopisany do tekstu), musi to i tak zmieścić
    się między x=12 a x=W-12, inaczej uciekłaby poza 640×480."""
    avail = W - 12 - 12
    w = app.draw.textlength(FOOTER_TEXT, font=app.f_sm)
    assert w <= avail, (
        f'stopka {w:.0f}px > dostępne {avail}px — ucieka poza ekran: {FOOTER_TEXT!r}')


def _fields(app_main):
    # FIELDS zdefiniowane w app/main.py (nie w vc_lib) — bierzemy z załadowanego modułu.
    return app_main.FIELDS


def _worst_value_str(app, field):
    """Najdłuższy realny string wartości dla pola: skrajne (min/max) + typowe
    duże liczby, po przejściu przez _fmt_val (dokładnie tak jak w _draw)."""
    name, unit, dflt, sb, mn, mx, kind, desc = field
    candidates = []
    if kind == 'idx':
        n = int(mx - mn + 1)
        candidates = [app._fmt_val(name, i) for i in range(mn, mn + n)]
    elif kind == 'int':
        candidates = [app._fmt_val(name, mn), app._fmt_val(name, mx)]
    else:  # 'num'
        candidates = [app._fmt_val(name, mn), app._fmt_val(name, mx),
                      app._fmt_val(name, dflt)]
    unit_str = f' {unit}' if unit else ''
    strs = [f'{c}{unit_str}' for c in candidates]
    return max(strs, key=lambda s: app.draw.textlength(s, font=app.f_md))


@pytest.mark.parametrize('field_idx', range(8))
def test_field_desc_fits_after_clip(app, app_main, field_idx):
    """Opis pola (z markerem '> ' zaznaczenia) po _clip() mieści się w
    kolumnie lewej (do separatora)."""
    fields = _fields(app_main)
    name, unit, dflt, sb, mn, mx, kind, desc = fields[field_idx]
    raw = f'> {desc}'
    clipped = app._clip(raw, app.f_sm, BUDGET_DESC)
    w = app.draw.textlength(clipped, font=app.f_sm)
    assert w <= BUDGET_DESC, f'{name}: opis {w:.0f}px > budżet {BUDGET_DESC}px'


@pytest.mark.parametrize('field_idx', range(8))
def test_field_value_fits_after_clip(app, app_main, field_idx):
    """WARTOŚĆ pola (skrajne min/max/preset, + jednostka) po _clip() mieści
    się w kolumnie lewej — sprawdzone dla KAŻDEGO pola, nie próbki."""
    fields = _fields(app_main)
    field = fields[field_idx]
    worst = _worst_value_str(app, field)
    clipped = app._clip(worst, app.f_md, BUDGET_VAL)
    w = app.draw.textlength(clipped, font=app.f_md)
    assert w <= BUDGET_VAL, (
        f'{field[0]}: wartość {w:.0f}px > budżet {BUDGET_VAL}px (raw={worst!r})')


@pytest.mark.parametrize('key', list(vc.BINDING_PL.keys()))
def test_binding_label_fits_after_clip(app, key):
    """Etykieta „(wiąże: ...)” dla każdego z 3 ograniczeń (vc/tool/machine)
    mieści się w prawej kolumnie po _clip()."""
    label = vc.BINDING_PL[key]
    raw = f'(wiąże: {label})'
    clipped = app._clip(raw, app.f_sm, BUDGET_BINDING)
    w = app.draw.textlength(clipped, font=app.f_sm)
    assert w <= BUDGET_BINDING, f'{key}: {w:.0f}px > budżet {BUDGET_BINDING}px'


# ── ostrzeżenia: cała klasa scenariuszy generujących WSZYSTKIE gałęzie
#    warnings w vc_lib.recommend(), w tym z ekstremalnie dużymi liczbami ─────
_WARNING_SCENARIOS = [
    dict(rpm_min=3000, rpm_max=12000, n_settings=7, tool_max_rpm=100,
         vc=80.0, vc_unit='m/s', diameter_mm=125.0),          # narzędzie za duże
    dict(rpm_min=3000, rpm_max=200000, n_settings=7, tool_max_rpm=12500,
         vc=80.0, vc_unit='m/s', diameter_mm=125.0),          # maszyna > narzędzie
    dict(rpm_min=3000, rpm_max=200000, n_settings=30, tool_max_rpm=1000000,
         vc=100000.0, vc_unit='m/min', diameter_mm=2000.0),   # ekstremalne liczby
]


def _all_warning_texts():
    texts = []
    for kw in _WARNING_SCENARIOS:
        r = vc.recommend(**kw)
        texts.extend(r.warnings)
    assert texts, 'scenariusze testowe nie wygenerowały ŻADNYCH ostrzeżeń — dobierz inne'
    return texts


@pytest.mark.parametrize('warning_text', _all_warning_texts())
def test_warning_lines_fit_after_wrap(app, warning_text):
    """Każda linia ostrzeżenia (po zawinięciu _wrap, tak jak w _draw) mieści
    się w budżecie kolumny lewej — w tym ekstremalnie duże liczby."""
    lines = app._wrap('! ' + warning_text, app.f_sm, BUDGET_WARN)
    assert lines, 'puste ostrzeżenie po _wrap'
    for line in lines:
        w = app.draw.textlength(line, font=app.f_sm)
        assert w <= BUDGET_WARN, (
            f'linia ostrzeżenia {w:.0f}px > budżet {BUDGET_WARN}px: {line!r}')


# ── komunikaty statusu STAŁE (literały bez dynamicznej treści — bezpiecznie
#    testowalne wprost) ────────────────────────────────────────────────────
_FIXED_STATUS_MESSAGES = [
    'Generuję PDF...',
    'Brak wyniku obliczeń — popraw parametry (PDF pominięty).',
]


@pytest.mark.parametrize('status_text', _FIXED_STATUS_MESSAGES)
def test_status_bar_lines_fit_after_wrap(app, status_text):
    """Każda linia paska statusu (po zawinięciu, jak w _status_bar) mieści się
    w interiorze paska."""
    lines = app._wrap(status_text, app.f_sm, BUDGET_STATBAR)
    for line in lines:
        w = app.draw.textlength(line, font=app.f_sm)
        assert w <= BUDGET_STATBAR, (
            f'linia paska {w:.0f}px > budżet {BUDGET_STATBAR}px: {line!r}')
    # pasek też musi zmieścić się PIONOWO nad stopką (y=330 start, stopka H-14)
    line_h = 15
    pad = STATBAR_PAD
    total_h = 2 * pad + len(lines) * line_h
    assert 330 + total_h <= H - 20, (
        f'pasek statusu ({len(lines)} linii, {total_h}px) wchodzi na stopkę: '
        f'{status_text!r}')


# ── komunikaty statusu DYNAMICZNE ('Zapisano...'/'Błąd PDF: ...') — oracle
#    NIEZALEŻNY od zgadywania treści: wołamy PRAWDZIWY _make_report() z
#    zamockowanym generate_pdf (zwraca realistyczną DŁUGĄ ścieżkę konsoli /
#    podnosi wyjątek z długim komunikatem), i mierzymy STATUS, JAKI APKA
#    NAPRAWDĘ USTAWIA — to właśnie złapało (red→green) regresję
#    'Zapisano PDF: {pełna_ścieżka}' uciekającą poza 640×480. ───────────────
_LONG_REALISTIC_PATH = (
    '/mnt/data/sprawozdania/raporty/AnberVc/'
    'AnberVc_Szlifowanie_tarcza_125_D125_v80_2026-07-12_23-59-59.pdf')


def _run_make_report(app, monkeypatch, *, raise_exc=None, return_path=None):
    import vc_lib.report as report_mod

    def _fake_generate_pdf(params, rec, operacja):
        if raise_exc is not None:
            raise raise_exc
        return return_path

    monkeypatch.setattr(report_mod, 'generate_pdf', _fake_generate_pdf)
    # _make_report() woła self.render() (_draw + SDL _blit) w trakcie „Generuję
    # PDF…” — w headless nie ma prawdziwego SDL (fake sdl2 ma tylko
    # SDL_GetTicks), więc podmieniamy render() na sam _draw() (bez blitu do
    # okna) — identyczny wzorzec jak reszta tego pliku testowego.
    monkeypatch.setattr(app, 'render', app._draw)
    app._make_report()
    return app._status


def _assert_status_fits_and_bar(app, app_main, status_text, *, is_err):
    # (a) szerokość: REALNY tekst po zawinięciu jak w _status_bar
    lines = app._wrap(status_text, app.f_sm, BUDGET_STATBAR)
    for line in lines:
        w = app.draw.textlength(line, font=app.f_sm)
        assert w <= BUDGET_STATBAR, (
            f'REALNY status apki {w:.0f}px > budżet {BUDGET_STATBAR}px: {line!r} '
            f'(pełny status: {status_text!r})')
    line_h = 15
    total_h = 2 * STATBAR_PAD + len(lines) * line_h
    assert 330 + total_h <= H - 20, (
        f'REALNY pasek statusu ({len(lines)} linii) wchodzi na stopkę: {status_text!r}')

    # (b) wygląd: render pełnej klatki z tym STANEM (nie z podstawionym tekstem)
    app._draw()
    bar_color = (app_main.STATBAR_RED if is_err else app_main.ORANGE)[:3]
    text_color = (app_main.FG if is_err else app_main.ORANGE_TX)[:3]
    rows = _bg_rows(app.img, bar_color)
    assert rows, f'brak prostokąta tła {bar_color} dla realnego statusu: {status_text!r}'
    assert abs(min(rows) - 330) <= 3
    band = range(min(rows), min(rows) + 60)
    assert _has_pixel(app.img, text_color, band), (
        f'brak tekstu na pasku dla realnego statusu: {status_text!r}')


def test_real_make_report_success_status_fits_and_looks_right(app, app_main, monkeypatch):
    """R2 z sukcesem, konsolowa DŁUGA ścieżka zwrócona przez generate_pdf —
    _make_report() musi wystawić KRÓTKI self._status (pełna ścieżka tylko do
    logu), który mieści się na pasku i renderuje się jako pomarańczowy pasek."""
    status = _run_make_report(app, monkeypatch, return_path=_LONG_REALISTIC_PATH)
    assert _LONG_REALISTIC_PATH not in status, (
        f'pełna ścieżka pliku wyciekła do self._status (poza log): {status!r}')
    _assert_status_fits_and_bar(app, app_main, status, is_err=False)


def test_real_make_report_error_status_fits_and_looks_right(app, app_main, monkeypatch):
    """R2 z wyjątkiem o DŁUGIM komunikacie (typowy PermissionError z pełną
    ścieżką) — realny self._status ustawiony przez _make_report() musi się
    zmieścić na pasku (zawinięty znak-po-znaku w razie potrzeby) i renderować
    się jako czerwony pasek błędu."""
    exc = PermissionError(f"[Errno 13] Permission denied: '{_LONG_REALISTIC_PATH}'")
    status = _run_make_report(app, monkeypatch, raise_exc=exc)
    assert status.startswith('Błąd PDF:')
    _assert_status_fits_and_bar(app, app_main, status, is_err=True)


# ═══════════════════════════════════════════════════════════════════════════
# (b) WYGLĄD — render pełnej klatki, inspekcja pikseli: pasek statusu MUSI
#     być kolorowym prostokątem tła + tekst NA nim, we właściwym miejscu.
# ═══════════════════════════════════════════════════════════════════════════

def _bg_rows(img, bg_rgb, y_from=300, min_run=400):
    """Wiersze zawierające ciągły poziomy pas koloru bg_rgb (min_run px) —
    identyfikuje realny obszar tła prostokąta paska w wyrenderowanej klatce
    (niezależnie od dokładnej matematyki wewnątrz _status_bar)."""
    px = img.load()
    w, h = img.size
    rows = []
    for y in range(y_from, h):
        run = maxrun = 0
        for x in range(0, w):
            if px[x, y][:3] == bg_rgb:
                run += 1
                maxrun = max(maxrun, run)
            else:
                run = 0
        if maxrun >= min_run:
            rows.append(y)
    return rows


def _has_pixel(img, rgb, y_range, x_range=(10, 630)):
    px = img.load()
    for y in y_range:
        for x in x_range if isinstance(x_range, range) else range(*x_range):
            if px[x, y][:3] == rgb:
                return True
    return False


def _render_with_status(app_main, app, status_text):
    app._status = status_text
    app._status_until = sys.modules['sdl2'].SDL_GetTicks() + 60000
    app._draw()
    return app.img


def test_generating_status_is_orange_bar_with_text(app_main, app):
    """'Generuję PDF...' → prostokąt tła POMARAŃCZOWY (ORANGE) zaczynający się
    ~y=330, pełna szerokość ekranu, Z tekstem (kolor ORANGE_TX) narysowanym
    na nim — nie goły żółty/pomarańczowy tekst na ciemnym tle strony."""
    img = _render_with_status(app_main, app, 'Generuję PDF...')
    orange = app_main.ORANGE[:3]
    orange_tx = app_main.ORANGE_TX[:3]

    rows = _bg_rows(img, orange)
    assert rows, 'brak pomarańczowego prostokąta tła w wyrenderowanej klatce'
    assert abs(min(rows) - 330) <= 3, (
        f'pasek zaczyna się w y={min(rows)}, oczekiwano ~330 (właściwe miejsce)')

    band = range(min(rows), min(rows) + 60)
    assert _has_pixel(img, orange_tx, band), (
        'brak tekstu (kolor ORANGE_TX) NA pomarańczowym pasku — sam prostokąt tła to za mało')


def test_saved_status_is_orange_bar_with_text(app_main, app):
    """'Zapisano raport PDF ✓' — ten sam motyw paska co 'Generuję…' (spójny
    wygląd obu stanów pośrednich)."""
    img = _render_with_status(app_main, app, 'Zapisano raport PDF ✓')
    orange = app_main.ORANGE[:3]
    orange_tx = app_main.ORANGE_TX[:3]

    rows = _bg_rows(img, orange)
    assert rows, 'brak pomarańczowego prostokąta tła dla komunikatu „Zapisano”'
    band = range(min(rows), min(rows) + 60)
    assert _has_pixel(img, orange_tx, band), 'brak tekstu na pasku „Zapisano”'


def test_error_status_is_red_bar_with_text(app_main, app):
    """Błąd (prefiks 'Błąd'/'Brak') → ten sam mechanizm paska, ale kolor
    STATBAR_RED zamiast ORANGE — spójny styl, odróżnialny kolor."""
    img = _render_with_status(app_main, app, 'Błąd PDF: dysk pełny')
    red = app_main.STATBAR_RED[:3]
    fg = app_main.FG[:3]
    orange = app_main.ORANGE[:3]

    rows = _bg_rows(img, red)
    assert rows, 'brak czerwonego prostokąta tła dla komunikatu błędu'
    assert abs(min(rows) - 330) <= 3
    assert not _bg_rows(img, orange), 'błąd NIE powinien renderować się pomarańczowo'

    band = range(min(rows), min(rows) + 60)
    assert _has_pixel(img, fg, band), 'brak tekstu na czerwonym pasku błędu'


def test_no_status_bar_when_status_expired(app_main, app):
    """Po wygaśnięciu timeoutu paska statusu (status_until w przeszłości) NIE
    ma już pomarańczowego/czerwonego prostokąta na klatce — pasek nie zostaje
    'zawieszony' na ekranie."""
    app._status = 'Generuję PDF...'
    app._status_until = sys.modules['sdl2'].SDL_GetTicks() - 1000   # w przeszłości
    app._draw()
    orange = app_main.ORANGE[:3]
    red = app_main.STATBAR_RED[:3]
    assert not _bg_rows(app.img, orange), 'pasek pomarańczowy nie powinien być widoczny po timeoucie'
    assert not _bg_rows(app.img, red), 'pasek czerwony nie powinien być widoczny po timeoucie'

# -*- coding: utf-8 -*-
"""Testy WIZUALNE AnberVc (pytest) — render realnej klatki (bez SDL/fb),
inspekcja PIKSELI wyrenderowanego obrazu.

Klasa regresji, którą te testy pilnują: „test przechodzi, apka na ekranie
wygląda zepsuta". Sam fakt, że _clip()/_wrap()/_fit_status() ISTNIEJĄ i są
wołane nie gwarantuje, że naprawdę mieszczą tekst w 640×480 ani że komunikat
raportu faktycznie wygląda jak REALNY AnberWM (ciemnozielony pasek tła +
żółty tekst na nim) — to mierzymy tutaj wprost, metryką fontu PIL (ta sama,
której używa _draw()) oraz odczytem pikseli z wyrenderowanej klatki.

Dwie klasy assercji:
  (a) SZEROKOŚĆ: najdłuższe realne treści (etykiety pól, wartości graniczne,
      stopka, etykiety wiązania, komunikaty statusu, ostrzeżenia) — po
      przejściu przez _clip()/_wrap()/_fit_status() — MUSZĄ mieścić się w
      dostępnej szerokości (kolumny albo całego ekranu), parametrycznie po
      WSZYSTKICH polach/komunikatach, nie próbce.
  (b) WYGLĄD komunikatu statusu: po realnym _draw() na wyrenderowanej klatce
      MUSI istnieć ciemnozielony pasek tła pełnej szerokości w pasie
      y∈[H-40, H-24) (kolor WM_BAR = (38,58,44)), a tekst statusu musi być
      widoczny NA tym pasku przy dolnej krawędzi (x=8, y≈H-38) w kolorze SEL
      = (255,210,90) — to jest kanon REALNEGO AnberWM (main.py ~L33,
      570-572, 645-669), nie wcześniej błędnie odczytany „goły tekst".

app/main.py importuje `sdl2` bezwarunkowo i ładuje font z absolutnej ścieżki
konsoli (/usr/share/fonts/.../DejaVuSansMono.ttf) — obu może brakować na PC
dev. Poniżej: minimalny fake `sdl2` (jedyne użycie w trybie headless to
SDL_GetTicks()) + podmiana FONT_PATH na dostępny lokalnie monospace font PO
imporcie modułu (ta sama nazwa globalna, którą _draw() odczytuje w locie) —
logika layoutu (_clip/_wrap/_fit_status) jest identyczna z konsolową, różni
się tylko plik fontu użyty do pomiaru pikseli.
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
# Niezależność od dryfu: jeśli ktoś zmieni layout w _draw()/_fit_status() bez
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
BUDGET_STATUS = W - 16        # matches literal `W - 16` passed to _fit_status() in _make_report

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
#    testowalne wprost). Komunikat to JEDNA linia tekstu (styl AnberWM, bez
#    zawijania/paska) — musi mieścić się w CAŁOŚCI na szerokości ekranu. ───────
_FIXED_STATUS_MESSAGES = [
    'Generuję raport (chwila)...',
    'Brak wyniku obliczeń — popraw parametry (PDF pominięty).',
]


@pytest.mark.parametrize('status_text', _FIXED_STATUS_MESSAGES)
def test_fixed_status_messages_fit_screen_width(app, status_text):
    """Każdy stały komunikat statusu (jedna linia, x=8..W-8) mieści się w
    całości na ekranie bez zawijania/przycinania."""
    w = app.draw.textlength(status_text, font=app.f_sm)
    assert w <= BUDGET_STATUS, (
        f'status {w:.0f}px > budżet {BUDGET_STATUS}px: {status_text!r}')


def test_status_texts_match_wm_pattern():
    """Dosłowne teksty statusu (wzór AnberWM, dostosowany do AnberVc) muszą
    być obecne w źródle main.py — regresja treści komunikatu."""
    assert "self._status = 'Generuję raport (chwila)...'" in _SRC
    assert "'✔ Zapisano: '" in _SRC
    assert "✘ Błąd: " in _SRC
    assert 'str(e)[:42]' in _SRC


def test_status_timeout_unified_to_5000ms():
    """Auto-znikanie statusu ujednolicone na 5000 ms (usunięty stary wariant
    6000 ms) — wszystkie przypisania _status_until używają tej samej wartości."""
    assert '6000' not in _SRC, 'stary wariant timeoutu 6000ms powinien zniknąć'
    matches = re.findall(r'_status_until\s*=\s*sdl2\.SDL_GetTicks\(\)\s*\+\s*(\d+)', _SRC)
    assert matches, 'brak przypisań _status_until w main.py'
    assert set(matches) == {'5000'}, f'timeouty statusu niespójne: {set(matches)}'


def test_status_bar_method_and_constants_removed(app_main):
    """Stary BŁĘDNY wariant paska statusu (_status_bar + ORANGE/ORANGE_TX/
    STATBAR_RED — pomarańczowy/czerwony, osobna metoda rysująca) MUSI zniknąć.
    Realny kanon AnberWM to WM_BAR (38,58,44) rysowany inline w _draw() +
    tekst SEL na nim — patrz test_status_message_has_background_bar."""
    assert not hasattr(app_main.VcApp, '_status_bar'), '_status_bar powinna być usunięta'
    for name in ('ORANGE', 'ORANGE_TX', 'STATBAR_RED'):
        assert not hasattr(app_main, name), f'{name} powinien być usunięty (stary pasek statusu)'


def test_sel_color_matches_wm_canon(app_main):
    assert app_main.SEL == (255, 210, 90, 255)


def test_wm_bar_color_constant_defined(app_main):
    assert app_main.WM_BAR == (38, 58, 44, 255)


# ── komunikaty statusu DYNAMICZNE ('✔ Zapisano: ...'/'✘ Błąd: ...') — oracle
#    NIEZALEŻNY od zgadywania treści: wołamy PRAWDZIWY _make_report() z
#    zamockowanym generate_pdf (zwraca realistyczną DŁUGĄ ścieżkę konsoli /
#    podnosi wyjątek z długim komunikatem), i mierzymy STATUS, JAKI APKA
#    NAPRAWDĘ USTAWIA — to właśnie łapie regresję długiej nazwy pliku
#    uciekającej poza 640×480. ─────────────────────────────────────────────
_LONG_REALISTIC_PATH = (
    '/mnt/data/sprawozdania/raporty/AnberVc/'
    'anbervc_szlifowanie_tarcza_125_D125mm_vc80ms_3000-12000rpm_N7_tn12500_'
    '20260712_235959.pdf')


def _run_make_report(app, monkeypatch, *, raise_exc=None, return_path=None):
    import vc_lib.report as report_mod

    def _fake_generate_pdf(params, rec, operacja):
        if raise_exc is not None:
            raise raise_exc
        return return_path

    monkeypatch.setattr(report_mod, 'generate_pdf', _fake_generate_pdf)
    # _make_report() woła self.render() (_draw + SDL _blit) w trakcie „Generuję
    # raport…” — w headless nie ma prawdziwego SDL (fake sdl2 ma tylko
    # SDL_GetTicks), więc podmieniamy render() na sam _draw() (bez blitu do
    # okna) — identyczny wzorzec jak reszta tego pliku testowego.
    monkeypatch.setattr(app, 'render', app._draw)
    app._make_report()
    return app._status


def test_real_make_report_success_status_fits_and_is_prefixed(app, app_main, monkeypatch):
    """R2 z sukcesem, konsolowa DŁUGA ścieżka zwrócona przez generate_pdf —
    _make_report() musi wystawić self._status zaczynający się od '✔ Zapisano: ',
    BEZ pełnej ścieżki (tylko w logu), zmierzalnie mieszczący się w całości na
    ekranie PO ewentualnym skróceniu nazwy wielokropkiem (_fit_status)."""
    status = _run_make_report(app, monkeypatch, return_path=_LONG_REALISTIC_PATH)
    assert status.startswith('✔ Zapisano: ')
    assert _LONG_REALISTIC_PATH not in status, (
        f'pełna ścieżka pliku wyciekła do self._status (poza log): {status!r}')
    w = app.draw.textlength(status, font=app.f_sm)
    assert w <= BUDGET_STATUS, (
        f'REALNY status po skróceniu {w:.0f}px > budżet {BUDGET_STATUS}px: {status!r}')


def test_real_make_report_error_status_fits_and_is_prefixed(app, app_main, monkeypatch):
    """R2 z wyjątkiem o DŁUGIM komunikacie (typowy PermissionError z pełną
    ścieżką) — realny self._status musi zaczynać się od '✘ Błąd: ', być
    ucięty do 42 znaków komunikatu wyjątku, i mieścić się na ekranie."""
    exc = PermissionError(f"[Errno 13] Permission denied: '{_LONG_REALISTIC_PATH}'")
    status = _run_make_report(app, monkeypatch, raise_exc=exc)
    assert status.startswith('✘ Błąd: ')
    w = app.draw.textlength(status, font=app.f_sm)
    assert w <= BUDGET_STATUS, (
        f'REALNY status błędu {w:.0f}px > budżet {BUDGET_STATUS}px: {status!r}')


# ═══════════════════════════════════════════════════════════════════════════
# (b) WYGLĄD — render pełnej klatki, inspekcja pikseli: komunikat statusu ma
#     ciemnozielony pasek tła (kanon REALNEGO AnberWM) pod żółtym tekstem.
# ═══════════════════════════════════════════════════════════════════════════

def _has_full_width_run(img, y_from, y_to, rgb, min_run=400):
    """True, jeśli w zakresie wierszy [y_from, y_to) istnieje CIĄGŁY poziomy
    bieg (≥min_run px) DOKŁADNIE koloru `rgb` — odcisk pełnoszerokościowego
    prostokąta tła (WM_BAR) rysowanego pod komunikatem statusu. Tekst na pasku
    zajmuje tylko lewą część, więc prawa część paska (bez glifów) daje długi
    jednolity bieg — to bezpiecznie wykrywa obecność paska niezależnie od
    treści komunikatu."""
    px = img.load()
    w = img.size[0]
    for y in range(y_from, y_to):
        run = maxrun = 0
        for x in range(w):
            if px[x, y][:3] == rgb:
                run += 1
            else:
                run = 0
            maxrun = max(maxrun, run)
        if maxrun >= min_run:
            return True
    return False


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


def test_status_message_has_background_bar(app_main, app):
    """Komunikat statusu (kanon REALNEGO AnberWM) ma pełnoszerokościowy
    ciemnozielony pasek tła (38,58,44) w pasie y∈[H-40, H-24) — narysowany
    PRZED tekstem, na całej szerokości ekranu."""
    img = _render_with_status(app_main, app, 'Generuję raport (chwila)...')
    wm_bar = app_main.WM_BAR[:3]
    assert _has_full_width_run(img, H - 40, H - 24, wm_bar), (
        'brak pełnoszerokościowego paska tła WM_BAR (38,58,44) pod komunikatem statusu — '
        'oczekiwano kanonu REALNEGO AnberWM (pasek + tekst na nim)')


def test_status_text_drawn_at_bottom_left_in_sel_color(app_main, app):
    """Tekst statusu narysowany blisko x=8, y=H-38, kolorem SEL (żółty
    255,210,90, kanon REALNEGO AnberWM), NA pasku tła — niezależnie od stanu
    (generowanie/sukces/błąd)."""
    sel = app_main.SEL[:3]
    for text in ('Generuję raport (chwila)...', '✔ Zapisano: raport.pdf',
                 '✘ Błąd: dysk pełny'):
        img = _render_with_status(app_main, app, text)
        assert _has_pixel(img, sel, range(H - 44, H - 24), x_range=(4, 300)), (
            f'brak tekstu statusu w kolorze SEL przy dolnej krawędzi dla: {text!r}')


def test_no_status_bar_or_text_when_status_expired(app_main, app):
    """Po wygaśnięciu timeoutu (status_until w przeszłości) komunikat NIE jest
    już rysowany — ani tekst, ani pasek tła — i self._status jest aktywnie
    czyszczony (nie zawiesza się 'po cichu' na ekranie mimo wygaśnięcia).
    Auto-znikanie po 5 s to świadomy wymóg usera (realny WM się nie chowa)."""
    app._status = 'Generuję raport (chwila)...'
    app._status_until = sys.modules['sdl2'].SDL_GetTicks() - 1000   # w przeszłości
    app._draw()
    assert app._status == '', 'self._status powinien być wyczyszczony po timeoucie'
    sel = app_main.SEL[:3]
    wm_bar = app_main.WM_BAR[:3]
    assert not _has_pixel(app.img, sel, range(H - 44, H - 24), x_range=(4, 300)), (
        'tekst statusu nie powinien być widoczny po timeoucie')
    assert not _has_full_width_run(app.img, H - 40, H - 24, wm_bar), (
        'pasek tła statusu nie powinien być widoczny po timeoucie')

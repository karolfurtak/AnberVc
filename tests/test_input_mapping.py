# -*- coding: utf-8 -*-
"""Testy mapowania wejścia AnberVc (pytest).

Dwie klasy regresji, które te testy pilnują:
  1. R2 nie generuje PDF-a  → zły evdev-kod R2 (było 313, martwe; realne 315).
  2. Wartości wejściowe „mrugają”/zmieniają się przy MENU / nawigacji / kroku / R2
     → wartość pola MUSI się zmieniać wyłącznie na jawną regulację usera.

Logika sterowania kroku żyje w vc_lib (czysta, bez SDL) — testowana wprost.
Reszta (obsługa evdev w app/main.py) walidowana statycznie przez AST (bez SDL).
"""
import ast
import pathlib

from vc_lib import STEP_MODES, clamp_step_idx

_MAIN = pathlib.Path(__file__).resolve().parent.parent / 'app' / 'main.py'
_SRC = _MAIN.read_text(encoding='utf-8')
_TREE = ast.parse(_SRC)


# ── rozmiar kroku: L1 (−1) mniejszy, L2 (+1) większy, z ograniczeniem ─────────
def test_clamp_step_idx_direction():
    # L2 (+1) → większy krok, L1 (−1) → mniejszy krok
    assert clamp_step_idx(2, +1) == 3
    assert clamp_step_idx(2, -1) == 1


def test_clamp_step_idx_bounds_no_wrap():
    last = len(STEP_MODES) - 1
    assert clamp_step_idx(last, +1) == last     # nie przekracza max (bez zawijania)
    assert clamp_step_idx(0, -1) == 0           # nie schodzi poniżej min
    # cała klasa: monotoniczne dojście do krańców
    idx = 0
    for _ in range(10):
        idx = clamp_step_idx(idx, +1)
    assert idx == last


# ── R2: właściwy kod evdev (regresja „R2 nie robi PDF-a”) ─────────────────────
def _const_value(name):
    """Wyłuskaj z AST wartość stałej modułu (obsługuje przypisania krotkowe)."""
    for node in _TREE.body:
        if isinstance(node, ast.Assign):
            targets = node.targets[0]
            names = ([t.id for t in targets.elts]
                     if isinstance(targets, ast.Tuple) else [getattr(targets, 'id', None)])
            if name in names:
                if isinstance(targets, ast.Tuple):
                    i = names.index(name)
                    return ast.literal_eval(node.value.elts[i])
                return ast.literal_eval(node.value)
    raise AssertionError(f'stała {name} nie znaleziona w app/main.py')


def test_r2_code_is_real_device_value():
    # realny kod R2 na RG40XX V = 315 (źródło: log/AnberWM); 313 było martwe
    assert _const_value('BTN_R2') == 315


def test_shoulder_step_codes():
    # L1 = 312 (krok−), L2 = 314 (krok+) — z realnej mapy egzemplarza
    assert _const_value('BTN_L1') == 312
    assert _const_value('BTN_L2') == 314


def test_dead_code_313_not_used_as_r2():
    # 313 nie może być już przypisane do R2 (martwy kod na tym urządzeniu)
    assert _const_value('BTN_R2') != 313


# ── odporność: MENU/krok/R2/nawigacja NIE zmieniają wartości pól ──────────────
def _func(name):
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'metoda {name} nie znaleziona w app/main.py')


def _assigns_self_vals(func):
    """True, jeśli w ciele metody jest przypisanie do self.vals[...]."""
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Attribute)
                        and tgt.value.attr == 'vals'):
                    return True
    return False


def test_step_change_does_not_touch_values():
    # zmiana ROZMIARU kroku (L1/L2) nie rusza self.vals
    assert not _assigns_self_vals(_func('_step_size'))


def test_make_report_does_not_touch_values():
    # R2 → PDF czyta stan, nie modyfikuje wartości pól
    assert not _assigns_self_vals(_func('_make_report'))


def test_only_adjust_and_presets_mutate_values():
    """Wartość pola (self.vals[...]=) wolno zmieniać WYŁĄCZNIE jawnym metodom
    regulacji/resetu — nie nawigacji/krokowi/raportowi/wyjściu."""
    allowed = {'_adjust', '_load_preset', '_reset_field', '_apply_saved_config',
               '__init__'}
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and _assigns_self_vals(node):
            assert node.name in allowed, (
                f'{node.name} nie powinno zmieniać self.vals (klasa błędu: '
                f'wartości mrugają)')


def test_exit_checked_before_regulation():
    """MENU/MODE (EXIT_KEYS) sprawdzane PRZED gałęziami regulacji — cała partia
    zdarzeń z przyciskiem wyjścia kończy się return, nim cokolwiek muśnie stan."""
    run = _func('run')
    src = ast.get_source_segment(_SRC, run)
    i_exit = src.find('EXIT_KEYS')
    i_adjust = src.find('self._adjust')
    i_step = src.find('self._step_size')
    assert 0 <= i_exit < i_adjust, 'wyjście musi być sprawdzane przed _adjust'
    assert 0 <= i_exit < i_step, 'wyjście musi być sprawdzane przed _step_size'

# -*- coding: utf-8 -*-
"""AnberVc — rdzeń doboru obrotów maszyny do średnicy narzędzia (limit v_c).

Bez zależności od SDL/PIL/evdev — czysta logika, w pełni testowalna (pytest, CI).

Zakres: szlifowanie/cięcie (tarcza), WIERCENIE (wiertło), FREZOWANIE (frez)
i SZLIFIERKA TAŚMOWA (koło kontaktowe → prędkość taśmy) —
ta sama fizyka prędkości skrawania/liniowej (obwodowej):

    v_c = π · D · n / 60          [v_c] = m/s, [D] = m, [n] = obr/min
    v_c = π · D · n / 1000        [v_c] = m/min, [D] = mm, [n] = obr/min

(oba zapisy są równoważne: v_c[m/min] = 60 · v_c[m/s]).

D — średnica NARZĘDZIA (tarcza / wiertło / frez). Dla tarczy zużywa się → maleje.
n — obroty wrzeciona maszyny.
v_c — dopuszczalna prędkość skrawania, ZALEŻNA od materiału i operacji:
      szlifowanie ~80 m/s; wiercenie/frezowanie w m/min (stal ~20–30, Al ~100–300).

Dobór bezpiecznych obrotów — nie przekroczyć limitu v_c ani obrotów znamionowych
narzędzia, ani maksymalnych obrotów maszyny:

    n_bezp = min( v_c·60/(π·D[m]),  narzędzie_max_rpm,  maszyna_max_rpm )

Maszyna ma N nastawień obrotów (liniowo min→max):

    rpm_k = rpm_min + (k-1)·(rpm_max - rpm_min)/(N-1),   k = 1..N

Rekomendujemy NAJWYŻSZE nastawienie k, którego rpm_k ≤ n_bezp
(najwyższa wydajność w granicy bezpieczeństwa).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# ── jednostki prędkości skrawania ────────────────────────────────────────────
VC_UNITS = ('m/s', 'm/min')

# ── rozmiary kroku regulacji wartości (D-pad ←/→) ────────────────────────────
# Sterowanie rozmiarem kroku: L1 = mniejszy (−1), L2 = większy (+1) — patrz app.
STEP_MODES = [0.1, 1, 10, 100, 1000]


def clamp_step_idx(idx: int, delta: int, n: int = len(STEP_MODES)) -> int:
    """Przesuń indeks rozmiaru kroku o delta z ograniczeniem do [0, n-1].

    delta<0 (L1) → mniejszy krok, delta>0 (L2) → większy krok. Bez zawijania."""
    return max(0, min(n - 1, idx + delta))


def _pl(x, nd=None) -> str:
    """Liczba z POLSKIM separatorem dziesiętnym (przecinek)."""
    s = f'{x:g}' if nd is None else f'{x:.{nd}f}'
    return s.replace('.', ',')


def vc_to_ms(vc: float, unit: str) -> float:
    """Prędkość skrawania na kanoniczne m/s (1 m/s = 60 m/min)."""
    if unit == 'm/min':
        return vc / 60.0
    if unit == 'm/s':
        return float(vc)
    raise ValueError(f'nieznana jednostka v_c: {unit!r} (dozwolone {VC_UNITS})')


def ms_to_unit(v_ms: float, unit: str) -> float:
    """Prędkość z m/s na wybraną jednostkę wyświetlania."""
    return v_ms * 60.0 if unit == 'm/min' else v_ms


# ── domyślny preset: przypadek szlifierki kątowej od usera ───────────────────
DEFAULTS = {
    'rpm_min':       3000,     # min obroty maszyny [obr/min]
    'rpm_max':       12000,    # max obroty maszyny [obr/min]
    'n_settings':    7,        # liczba nastawień pokrętła
    'tool_max_rpm':  12500,    # znamionowe max obroty narzędzia [obr/min]
    'vc':            80.0,     # limit prędkości skrawania
    'vc_unit':       'm/s',    # jednostka v_c
    'diameter_mm':   125.0,    # średnica narzędzia [mm] (typowa tarcza 125)
}


def setting_rpm(k: int, rpm_min: float, rpm_max: float, n: int) -> float:
    """Obroty [obr/min] dla nastawienia k∈1..n (liniowo min→max).

    Dla n==1 zwraca rpm_min (brak rozpiętości)."""
    if k < 1 or k > n:
        raise ValueError(f'nastawienie k={k} poza zakresem 1..{n}')
    if n == 1:
        return float(rpm_min)
    return rpm_min + (k - 1) * (rpm_max - rpm_min) / (n - 1)


def peripheral_speed(diameter_m: float, rpm: float) -> float:
    """Prędkość skrawania v_c = π·D·n/60 [m/s]; D w METRACH, n w obr/min."""
    return math.pi * diameter_m * rpm / 60.0


def v_from_mm(diameter_mm: float, rpm: float) -> float:
    """Prędkość skrawania [m/s] dla średnicy w MILIMETRACH."""
    return peripheral_speed(diameter_mm / 1000.0, rpm)


def rpm_for_v(v_ms: float, diameter_mm: float) -> float:
    """Obroty [obr/min] dające v_c = v_ms [m/s] przy średnicy D [mm].

    Z v = π·D·n/60  ⇒  n = v·60/(π·D)."""
    d_m = diameter_mm / 1000.0
    if d_m <= 0:
        return float('inf')
    return v_ms * 60.0 / (math.pi * d_m)


def n_safe(vc: float, vc_unit: str, diameter_mm: float,
           tool_max_rpm: float, rpm_max: float):
    """Maksymalne bezpieczne obroty n_bezp = min(z limitu v_c, narzędzie, maszyna).

    Zwraca (n_bezp, ograniczenie), ograniczenie ∈ {'vc', 'tool', 'machine'}."""
    n_v = rpm_for_v(vc_to_ms(vc, vc_unit), diameter_mm)
    candidates = [(n_v, 'vc'), (tool_max_rpm, 'tool'), (rpm_max, 'machine')]
    val, which = min(candidates, key=lambda t: t[0])
    return val, which


@dataclass
class Setting:
    k: int
    rpm: float
    v: float          # prędkość skrawania w jednostce vc_unit (do wyświetlenia)
    v_ms: float       # prędkość skrawania [m/s] (kanoniczna)
    safe: bool        # rpm ≤ n_bezp ?


@dataclass
class Recommendation:
    settings: list          # lista Setting (k=1..N)
    n_safe: float           # bezpieczne obroty [obr/min]
    binding: str            # które ograniczenie wiąże n_safe: vc/tool/machine
    vc_unit: str            # jednostka prędkości skrawania (do wyświetlenia)
    recommended_k: int | None
    rec_rpm: float | None
    rec_v: float | None           # w vc_unit
    margin_pct: float | None      # margines do v_c [%]
    warnings: list = field(default_factory=list)


def recommend(rpm_min: float = DEFAULTS['rpm_min'],
              rpm_max: float = DEFAULTS['rpm_max'],
              n_settings: int = DEFAULTS['n_settings'],
              tool_max_rpm: float = DEFAULTS['tool_max_rpm'],
              vc: float = DEFAULTS['vc'],
              vc_unit: str = DEFAULTS['vc_unit'],
              diameter_mm: float = DEFAULTS['diameter_mm']) -> Recommendation:
    """Pełny dobór: tabela N nastawień + rekomendacja + ostrzeżenia."""
    vc_ms = vc_to_ms(vc, vc_unit)
    nb, binding = n_safe(vc, vc_unit, diameter_mm, tool_max_rpm, rpm_max)

    settings = []
    for k in range(1, n_settings + 1):
        rpm = setting_rpm(k, rpm_min, rpm_max, n_settings)
        v_ms = v_from_mm(diameter_mm, rpm)
        settings.append(Setting(
            k=k, rpm=rpm,
            v=ms_to_unit(v_ms, vc_unit), v_ms=v_ms,
            safe=(rpm <= nb + 1e-9),          # tolerancja na równość
        ))

    safe_ks = [s for s in settings if s.safe]
    warnings: list[str] = []
    if safe_ks:
        rec = safe_ks[-1]
        rec_k, rec_rpm, rec_v = rec.k, rec.rpm, rec.v
        margin = (vc_ms - rec.v_ms) / vc_ms * 100.0 if vc_ms > 0 else None
    else:
        rec_k = rec_rpm = rec_v = margin = None
        warnings.append(
            f'Narzędzie za duże dla tej maszyny / przekroczenie {_pl(vc)} {vc_unit} '
            '— nawet nastawienie 1 jest niebezpieczne.')

    if rpm_max > tool_max_rpm:
        warnings.append(
            f'Maksymalne obroty maszyny ({_pl(rpm_max)}) przekraczają znamionowe narzędzia '
            f'({_pl(tool_max_rpm)}) — nie ustawiaj wyżej niż nastawienie bezpieczne.')

    top = settings[-1]
    if top.v_ms > vc_ms + 1e-9:
        warnings.append(
            f'Najwyższe nastawienie daje v_c={_pl(top.v, 1)} {vc_unit} > {_pl(vc)} '
            f'{vc_unit} — NIE używaj pełnych obrotów przy tej średnicy.')

    return Recommendation(
        settings=settings, n_safe=nb, binding=binding, vc_unit=vc_unit,
        recommended_k=rec_k, rec_rpm=rec_rpm, rec_v=rec_v,
        margin_pct=margin, warnings=warnings)


BINDING_PL = {
    'vc':      'limit prędkości skrawania',
    'tool':    'obroty znamionowe narzędzia',
    'machine': 'maksymalne obroty maszyny',
}

# ── presety operacji/materiału (opcjonalne skróty) ───────────────────────────
# Każdy preset nadpisuje część parametrów; brakujące pola brane z DEFAULTS.
PRESETS = [
    {
        'name': 'Szlifowanie tarcza 125',
        'rpm_min': 3000, 'rpm_max': 12000, 'n_settings': 7,
        'tool_max_rpm': 12500, 'vc': 80.0, 'vc_unit': 'm/s', 'diameter_mm': 125.0,
    },
    {
        'name': 'Wiercenie stal HSS',
        'rpm_min': 500, 'rpm_max': 3000, 'n_settings': 5,
        'tool_max_rpm': 100000, 'vc': 25.0, 'vc_unit': 'm/min', 'diameter_mm': 10.0,
    },
    {
        'name': 'Wiercenie Al HSS',
        'rpm_min': 500, 'rpm_max': 3000, 'n_settings': 5,
        'tool_max_rpm': 100000, 'vc': 120.0, 'vc_unit': 'm/min', 'diameter_mm': 10.0,
    },
    {
        'name': 'Frezowanie Al HSS',
        'rpm_min': 1000, 'rpm_max': 10000, 'n_settings': 6,
        'tool_max_rpm': 100000, 'vc': 150.0, 'vc_unit': 'm/min', 'diameter_mm': 8.0,
    },
    {
        'name': 'Frezowanie stal HSS',
        'rpm_min': 1000, 'rpm_max': 10000, 'n_settings': 6,
        'tool_max_rpm': 100000, 'vc': 25.0, 'vc_unit': 'm/min', 'diameter_mm': 8.0,
    },
    # Szlifierka taśmowa: ta sama fizyka v=π·D·n/60, ale D = średnica koła
    # napędowego/kontaktowego (nie taśmy), v = prędkość LINIOWA taśmy [m/s].
    # D = koło kontaktowe, v = prędkość taśmy.
    {
        'name': 'Szlifierka taśmowa',
        'rpm_min': 500, 'rpm_max': 4000, 'n_settings': 8,
        'tool_max_rpm': 5000, 'vc': 30.0, 'vc_unit': 'm/s', 'diameter_mm': 200.0,
    },
]


def preset_params(preset: dict) -> dict:
    """Zwraca komplet parametrów recommend() z presetu (uzupełniony z DEFAULTS)."""
    p = {k: DEFAULTS[k] for k in DEFAULTS}
    for k, v in preset.items():
        if k in p:
            p[k] = v
    return p


def _selftest() -> int:
    """Szybki self-test bez pytest (używany w CI i install.sh)."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f'[{"OK " if cond else "FAIL"}] {name}')
        ok = ok and cond

    r = recommend()   # domyślne: szlifierka, D=125, v_c=80 m/s
    check('n_safe=12000 (wiąże maszyna)',
          abs(r.n_safe - 12000) < 1e-6 and r.binding == 'machine')
    check('rekomendacja = nastawienie 7', r.recommended_k == 7)
    check('rpm rekomendowane = 12000', abs(r.rec_rpm - 12000) < 1e-6)
    check('v_c ~ 78,5 m/s', abs(r.rec_v - math.pi * 25) < 0.05)
    check('brak przekroczeń', r.recommended_k is not None)
    print(f'  [szlif] n_safe={r.n_safe:.1f}  k={r.recommended_k}  '
          f'v_c={r.rec_v:.1f} {r.vc_unit}  margines={r.margin_pct:.1f}%')

    # wiercenie stali (m/min)
    p = preset_params(PRESETS[1])
    rd = recommend(**p)
    print(f'  [wiert] n_safe={rd.n_safe:.1f}  k={rd.recommended_k}  '
          f'v_c={rd.rec_v:.1f} {rd.vc_unit}')
    check('wiercenie: jednostka m/min', rd.vc_unit == 'm/min')

    print('selftest:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(_selftest())

# -*- coding: utf-8 -*-
"""vc_lib — rdzeń logiki AnberVc: dobór obrotów maszyny do średnicy narzędzia.

v_c = π·D·n/60 — prędkość skrawania (obwodowa). Zakres: szlifowanie/cięcie,
wiercenie, frezowanie. Bez zależności od SDL/PIL/evdev — czysta logika (pytest, CI).
"""
from .core import (
    DEFAULTS,
    BINDING_PL,
    VC_UNITS,
    STEP_MODES,
    clamp_step_idx,
    PRESETS,
    Setting,
    Recommendation,
    setting_rpm,
    peripheral_speed,
    v_from_mm,
    rpm_for_v,
    vc_to_ms,
    ms_to_unit,
    n_safe,
    recommend,
    preset_params,
)

__all__ = [
    'DEFAULTS', 'BINDING_PL', 'VC_UNITS', 'STEP_MODES', 'clamp_step_idx',
    'PRESETS', 'Setting', 'Recommendation',
    'setting_rpm', 'peripheral_speed', 'v_from_mm', 'rpm_for_v',
    'vc_to_ms', 'ms_to_unit', 'n_safe', 'recommend', 'preset_params',
]

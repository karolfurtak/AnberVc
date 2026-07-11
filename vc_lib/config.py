# -*- coding: utf-8 -*-
"""AnberVc — trwała persystencja ostatnio użytych parametrów (JSON).

Zapis do TRWAŁEJ lokalizacji poza katalogiem aplikacji (deploy nadpisuje APPS),
domyślnie `/mnt/data/anbervc_config.json`. Ścieżka portowalna przez env
`ANBERVC_CONFIG` lub argument — dzięki temu testy/CI działają bez /mnt/data.

Uszkodzony/niekompletny/brak pliku → `load()` zwraca None (aplikacja bierze
domyślny preset). Zapis atomowy (tmp + os.replace).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_PATH = '/mnt/data/anbervc_config.json'


def config_path(path: str | None = None) -> str:
    """Ścieżka configu: argument > env ANBERVC_CONFIG > domyślna /mnt/data."""
    return path or os.environ.get('ANBERVC_CONFIG', DEFAULT_PATH)


def load(path: str | None = None):
    """Wczytaj słownik configu lub None (brak/uszkodzony/nie-dict)."""
    p = config_path(path)
    try:
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def save(data: dict, path: str | None = None) -> bool:
    """Zapisz słownik atomowo. Zwraca True/False (nie rzuca)."""
    p = config_path(path)
    try:
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, p)               # atomowa podmiana
        return True
    except Exception:
        return False

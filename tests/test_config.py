# -*- coding: utf-8 -*-
"""Testy persystencji AnberVc (vc_lib/config.py) — roundtrip / brak / uszkodzony.

Ścieżka portowalna (tmp_path / env ANBERVC_CONFIG) — bez /mnt/data, działa w CI.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from vc_lib import config  # noqa: E402


def test_roundtrip(tmp_path):
    p = str(tmp_path / 'cfg.json')
    data = {'vals': {'diameter_mm': 125.0, 'vc': 80.0, 'vc_unit': 0,
                     'preset': 0, 'rpm_min': 3000, 'rpm_max': 12000,
                     'n_settings': 7, 'tool_max_rpm': 12500},
            'field_idx': 2, 'step_idx': 3}
    assert config.save(data, p) is True
    got = config.load(p)
    assert got == data


def test_missing_returns_none(tmp_path):
    assert config.load(str(tmp_path / 'nie_ma.json')) is None


def test_corrupt_returns_none(tmp_path):
    p = tmp_path / 'bad.json'
    p.write_text('{ to nie jest json ]', encoding='utf-8')
    assert config.load(str(p)) is None


def test_non_dict_json_returns_none(tmp_path):
    p = tmp_path / 'list.json'
    p.write_text('[1, 2, 3]', encoding='utf-8')
    assert config.load(str(p)) is None


def test_save_atomic_no_partial_on_error(tmp_path):
    # zapis do istniejącego pliku podmienia atomowo (brak pliku .tmp po sukcesie)
    p = str(tmp_path / 'cfg.json')
    config.save({'a': 1}, p)
    config.save({'a': 2}, p)
    assert config.load(p) == {'a': 2}
    assert not (tmp_path / 'cfg.json.tmp').exists()


def test_env_path_override(tmp_path, monkeypatch):
    p = str(tmp_path / 'env_cfg.json')
    monkeypatch.setenv('ANBERVC_CONFIG', p)
    assert config.config_path() == p
    config.save({'x': 5})
    assert config.load() == {'x': 5}


def test_unicode_preserved(tmp_path):
    p = str(tmp_path / 'u.json')
    data = {'op': 'Szlifowanie tarcza 125 — Ø125'}
    config.save(data, p)
    assert config.load(p) == data

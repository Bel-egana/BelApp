"""Tests de core/config.py — carga y guardado de config.json."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import load_config, save_config


def test_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    assert save_config(p, {"base_path": "D:/Música", "discogs_token": "abc"}) is True
    data = load_config(p)
    assert data["base_path"] == "D:/Música"
    assert data["discogs_token"] == "abc"


def test_archivo_inexistente_devuelve_dict_vacio(tmp_path):
    assert load_config(tmp_path / "no_existe.json") == {}


def test_archivo_corrupto_devuelve_dict_vacio(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{esto no es json", encoding="utf-8")
    assert load_config(p) == {}


def test_json_que_no_es_dict_devuelve_dict_vacio(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_config(p) == {}

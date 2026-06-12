"""Tests de api.py — el puente PyWebView (instanciado sin ventana)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import Api


def test_get_config_sin_archivo_devuelve_defaults(tmp_path):
    api = Api(config_path=tmp_path / "config.json",
              history_path=tmp_path / "historial.json")
    cfg = api.get_config()
    assert cfg["discogs_token"] == ""
    assert cfg["base_path"]            # algún default no vacío


def test_save_y_get_config_roundtrip(tmp_path):
    api = Api(config_path=tmp_path / "config.json",
              history_path=tmp_path / "historial.json")
    assert api.save_config_values("D:/Mi Música", "tok123") is True
    cfg = api.get_config()
    assert cfg["base_path"] == "D:/Mi Música"
    assert cfg["discogs_token"] == "tok123"

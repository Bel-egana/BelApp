"""Tests de core/paths.py — resolución de rutas normal vs congelado (.exe)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import frozen_app_dir, resource_dir


def test_app_dir_normal_usa_carpeta_del_codigo():
    assert frozen_app_dir(False, r"C:\exe", r"C:\codigo") == Path(r"C:\codigo")


def test_app_dir_congelado_usa_carpeta_del_exe():
    assert frozen_app_dir(True, r"C:\exe", r"C:\codigo") == Path(r"C:\exe")


def test_resource_dir_normal_usa_carpeta_del_codigo():
    assert resource_dir(None, r"C:\codigo") == Path(r"C:\codigo")


def test_resource_dir_congelado_usa_meipass():
    assert resource_dir(r"C:\Temp\_MEI123", r"C:\codigo") == Path(r"C:\Temp\_MEI123")

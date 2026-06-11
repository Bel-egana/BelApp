"""
Tests de core/organizer.py

Verifican que build_path arme la ruta correcta y que use los
placeholders cuando falta género, sello o año.

Uso rutas relativas (ej. 'music') para que los tests funcionen igual
en Windows, Mac o Linux (importante para el CI).

Correr con:  pytest
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.organizer import build_path


def test_ruta_completa():
    p = build_path("music", "Trance", "Iboga Records", "2012", "track.mp3")
    assert p == Path("music") / "Trance" / "Iboga Records" / "2012" / "track.mp3"


def test_sin_genero_usa_placeholder():
    p = build_path("music", "", "Iboga", "2012", "t.mp3")
    assert p == Path("music") / "Sin Género" / "Iboga" / "2012" / "t.mp3"


def test_sin_sello_usa_placeholder():
    p = build_path("music", "Trance", "", "2012", "t.mp3")
    assert p == Path("music") / "Trance" / "Sin Sello" / "2012" / "t.mp3"


def test_sin_anio_usa_placeholder():
    p = build_path("music", "Trance", "Iboga", "", "t.mp3")
    assert p == Path("music") / "Trance" / "Iboga" / "Sin Año" / "t.mp3"


def test_todo_vacio_usa_los_tres_placeholders():
    p = build_path("music", "", "", "", "t.mp3")
    assert p == Path("music") / "Sin Género" / "Sin Sello" / "Sin Año" / "t.mp3"


def test_devuelve_un_objeto_path():
    p = build_path("music", "Trance", "Iboga", "2012", "t.mp3")
    assert isinstance(p, Path)

"""
Tests de core/playlists.py — armado de playlists .m3u8 por Género + Año.

Correr con:  pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.playlists import build_m3u8, group_by_genre_year, playlist_filename


# ── Nombre de archivo (saca caracteres ilegales de Windows) ──────────────────

def test_filename_simple():
    assert playlist_filename("Deep House", "2022") == "Deep House - 2022.m3u8"


def test_filename_sanitiza_barra():
    # "Ethereal / Melodic Techno" -> la / es ilegal en nombres de archivo.
    assert playlist_filename("Ethereal / Melodic Techno", "2023") == \
        "Ethereal _ Melodic Techno - 2023.m3u8"


def test_filename_saca_todos_los_ilegales():
    assert playlist_filename('A:B*C?', "2020") == "A_B_C_ - 2020.m3u8"


# ── Agrupación por (género, año) ─────────────────────────────────────────────

def test_group_agrupa_y_saltea_incompletos():
    tracks = [
        {"path": "a.mp3", "genre": "Deep House", "year": "2022"},
        {"path": "b.mp3", "genre": "Deep House", "year": "2022"},
        {"path": "c.mp3", "genre": "Techno", "year": "2023"},
        {"path": "d.mp3", "genre": "", "year": "2021"},        # sin género -> saltea
        {"path": "e.mp3", "genre": "Techno", "year": ""},       # sin año -> saltea
    ]
    g = group_by_genre_year(tracks)
    assert set(g.keys()) == {("Deep House", "2022"), ("Techno", "2023")}
    assert len(g[("Deep House", "2022")]) == 2
    assert len(g[("Techno", "2023")]) == 1


# ── Contenido del .m3u8 ──────────────────────────────────────────────────────

def test_build_m3u8_formato():
    tracks = [
        {"path": r"D:\M\a.mp3", "artist": "Adana Twins", "title": "Origo"},
        {"path": r"D:\M\b.mp3", "artist": "", "title": ""},
    ]
    txt = build_m3u8(tracks)
    lines = txt.splitlines()
    assert lines[0] == "#EXTM3U"
    assert "#EXTINF:-1,Adana Twins - Origo" in lines
    assert r"D:\M\a.mp3" in lines
    assert r"D:\M\b.mp3" in lines
    # sin artista/título -> usa el nombre del archivo como etiqueta
    assert "#EXTINF:-1,b.mp3" in lines

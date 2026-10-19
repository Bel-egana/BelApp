"""
Tests de core/playlists.py — armado de playlists .m3u8 por Género + Año.

Correr con:  pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.playlists import (append_tracks_to_nml, build_m3u8,
                            build_traktor_playlist_nml, group_by_genre_year,
                            nml_filename, playlist_filename, traktor_key)


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


# ── Export .nml estructurado (Género -> Año) para Traktor ────────────────────

def test_traktor_key_formato():
    assert traktor_key(r"D:\Bel\Música\Psy\x.mp3") == "D:/:Bel/:Música/:Psy/:x.mp3"
    # acepta / y saca segmentos vacíos
    assert traktor_key("D:/Bel/x.mp3") == "D:/:Bel/:x.mp3"


def test_nml_filename_sanitiza():
    assert nml_filename("Deep House", "2022") == "Deep House - 2022.nml"
    assert nml_filename("Ethereal / Melodic Techno", "2023") == \
        "Ethereal _ Melodic Techno - 2023.nml"


def test_build_traktor_playlist_nml_formato_nativo():
    tracks = [
        {"path": r"D:\M\Ethereal & Co\a.mp3", "genre": "Deep House",
         "artist": "Ar", "title": "Ti", "label": "Lab"},
        {"path": r"D:\M\b.mp3", "genre": "Deep House", "artist": "", "title": ""},
    ]
    nml = build_traktor_playlist_nml("Deep House - 2022", tracks)
    assert nml.startswith('<?xml')
    # una sola playlist plana (no árbol anidado)
    assert '<NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="1">' in nml
    assert '<NODE TYPE="PLAYLIST" NAME="Deep House - 2022">' in nml
    assert '<PLAYLIST ENTRIES="2"' in nml
    # COLLECTION con los 2 tracks + LOCATION en formato Traktor + & escapado
    assert '<COLLECTION ENTRIES="2">' in nml
    assert 'DIR="/:M/:Ethereal &amp; Co/:" FILE="a.mp3" VOLUME="D:"' in nml
    assert 'GENRE="Deep House"' in nml
    # PRIMARYKEY por referencia
    assert 'KEY="D:/:M/:Ethereal &amp; Co/:a.mp3"' in nml


# ── append_tracks_to_nml: anexar a una playlist existente sin duplicar ───────
def _trk(path, title="T", artist="A", genre="Deep House", label=""):
    return {'path': path, 'title': title, 'artist': artist,
            'genre': genre, 'label': label}


def test_append_crea_si_no_existe():
    text, added = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    assert added == 1
    assert 'A - Uno.mp3' in text
    assert '<PLAYLIST ENTRIES="1"' in text


def test_append_suma_a_existente():
    base, _ = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    text, added = append_tracks_to_nml(
        base, '2026', [_trk(r'D:\M\B - Dos.mp3', title="Dos", artist="B")])
    assert added == 1
    assert 'A - Uno.mp3' in text and 'B - Dos.mp3' in text
    assert '<PLAYLIST ENTRIES="2"' in text
    assert '<COLLECTION ENTRIES="2">' in text


def test_append_dedup_no_reagrega():
    base, _ = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    text, added = append_tracks_to_nml(base, '2026', [_trk(r'D:\M\A - Uno.mp3')])
    assert added == 0
    assert text == base


def test_append_mezcla_suma_solo_lo_nuevo():
    base, _ = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    mezcla = [_trk(r'D:\M\A - Uno.mp3'),
              _trk(r'D:\M\C - Tres.mp3', title="Tres", artist="C")]
    text, added = append_tracks_to_nml(base, '2026', mezcla)
    assert added == 1
    assert '<PLAYLIST ENTRIES="2"' in text


def test_append_formato_raro_no_toca():
    text, added = append_tracks_to_nml('esto no es un nml', '2026',
                                       [_trk(r'D:\M\A - Uno.mp3')])
    assert added == -1
    assert text == 'esto no es un nml'

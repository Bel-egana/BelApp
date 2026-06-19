"""
Tests de core/genres.py

Verifican que format_genre() traduzca bien los estilos de Discogs a las
categorías de Bel, incluyendo mayúsculas, substrings y casos sin match.

Correr con:  pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.genres import (BEL_GENRES, BEL_GENRES_SPECIFIC, GENRE_MAP,
                         format_genre, map_genre_specific)


# ── Taxonomía específica (normalizador de Traktor) ───────────────────────────

def test_specific_melodic_house_y_techno_va_a_melodic_techno():
    # Decisión de Bel: el combinado de Beatport -> Melodic Techno
    assert map_genre_specific("Melodic House & Techno") == "Melodic Techno"
    assert map_genre_specific("Deep House, Melodic House & Techno, Progressive House") == "Melodic Techno"


def test_specific_techno_variantes():
    assert map_genre_specific("Techno") == "Techno"
    assert map_genre_specific("Techno (Peak Time / Driving)") == "Techno"
    assert map_genre_specific("Minimal Techno") == "Techno"


def test_specific_psy_variantes():
    assert map_genre_specific("Psychedelic") == "Psytrance"
    assert map_genre_specific("Psy-Trance") == "Psytrance"
    assert map_genre_specific("Psychadelic") == "Psytrance"


def test_specific_acid_techno_antes_que_techno():
    assert map_genre_specific("Acid Techno") == "Acid Techno"


def test_specific_tech_house_antes_que_house():
    assert map_genre_specific("Tech House") == "Tech House"
    assert map_genre_specific("Deep House") == "Deep House"
    assert map_genre_specific("Indie Dance") == "Indie Dance"


def test_specific_trance_y_progresivos():
    assert map_genre_specific("Trance") == "Trance"
    assert map_genre_specific("Progressive Trance") == "Trance"   # unificado
    assert map_genre_specific("Dance / Trance") == "Trance"


def test_specific_basura_no_mapea():
    for junk in ("Blues", "Electro", "Dance", "www.sharingdb.org",
                 "Synthwave", "", "????"):
        assert map_genre_specific(junk) == ""


def test_specific_todo_lo_mapeado_esta_en_la_lista():
    from core.genres import SPECIFIC_RULES
    for _, canon in SPECIFIC_RULES:
        assert canon in BEL_GENRES_SPECIFIC


def test_techno_va_a_melodic_techno():
    assert format_genre("Melodic Techno") == "Melodic Techno & Techno"
    assert format_genre("Techno") == "Melodic Techno & Techno"


def test_variantes_de_house():
    assert format_genre("Deep House") == "Deep & Progressive House"
    assert format_genre("Tech House") == "Deep & Progressive House"
    assert format_genre("Progressive House") == "Deep & Progressive House"


def test_trance_y_psytrance():
    assert format_genre("Psytrance") == "Psychedelic Trance"
    assert format_genre("Goa Trance") == "Psychedelic Trance"
    assert format_genre("Uplifting Trance") == "Trance"


def test_no_distingue_mayusculas():
    assert format_genre("PROGRESSIVE HOUSE") == "Deep & Progressive House"
    assert format_genre("dEeP hOuSe") == "Deep & Progressive House"


def test_match_por_substring():
    # 'house' aparece dentro de 'Future House' -> mapea igual
    assert format_genre("Future House") == "Deep & Progressive House"


def test_vacio_devuelve_vacio():
    assert format_genre("") == ""
    assert format_genre(None) == ""


def test_genero_desconocido_devuelve_vacio():
    assert format_genre("Reggaeton") == ""
    assert format_genre("Jazz") == ""


def test_toda_categoria_del_map_es_valida():
    # Coherencia: todo lo que mapea GENRE_MAP debe ser una categoría de Bel
    for categoria in GENRE_MAP.values():
        assert categoria in BEL_GENRES

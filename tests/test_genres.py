"""
Tests de core/genres.py

Verifican que format_genre() traduzca bien los estilos de Discogs a las
categorías de Bel, incluyendo mayúsculas, substrings y casos sin match.

Correr con:  pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.genres import format_genre, BEL_GENRES, GENRE_MAP


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

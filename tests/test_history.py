"""Tests de core/history.py — historial persistente y detección de duplicados."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.history import (build_name_index, find_duplicate, load_history,
                          normalize_name, save_history)

HIST = [
    {'artista': 'CamelPhat', 'track': 'For A Feeling',
     'destino': r'D:\M\House\RCA\2020\CamelPhat - For A Feeling (Layton Giordani Remix).mp3'},
    {'artista': 'Atmos', 'track': 'Only for You',
     'destino': r'D:\M\Trance\Iboga\2012\Atmos - Only for You.mp3'},
]


def test_normalize_ignora_caso_espacios_simbolos():
    a = normalize_name("CamelPhat - For A Feeling (Remix)")
    b = normalize_name("camelphat   for a feeling remix")
    assert a == b
    assert normalize_name("") == ""


def test_index_y_duplicado_encontrado():
    idx = build_name_index(HIST)
    dup = find_duplicate(
        ["CamelPhat - For A Feeling (Layton Giordani Remix).mp3"], idx)
    assert dup is not None
    assert dup['artista'] == 'CamelPhat'


def test_normalize_ignora_orden_de_artistas():
    # "Pepe & Toto" y "Toto & Pepe" deben coincidir (mismo track, orden distinto).
    assert normalize_name("Pepe & Toto - Track") == normalize_name("Toto & Pepe - Track")
    # Y el dup con artistas al revés se detecta en el historial:
    hist = [{'artista': 'Pepe & Toto', 'track': 'X',
             'destino': r'D:\M\Melodic\Sello\2024\Pepe & Toto - X.mp3'}]
    idx = build_name_index(hist)
    assert find_duplicate(["Toto & Pepe - X.mp3"], idx) is not None


def test_normalize_ignora_conectores_de_artistas():
    # "&" vs "vs" vs "feat" no deben diferenciar (mismo track, distinto nombre).
    n = normalize_name
    assert n("Liquid Soul & Vini Vici - Universe Inside Me") == \
           n("Vini Vici vs Liquid Soul - Universe Inside Me")
    assert n("A feat B - X") == n("B & A - X")
    # Y el dup se detecta en el historial aunque cambie el conector/orden:
    hist = [{'artista': 'Vini Vici vs Liquid Soul', 'track': 'Universe Inside Me',
             'destino': r'D:\M\Psy\Iboga\2016\Vini Vici vs Liquid Soul - Universe Inside Me.mp3'}]
    idx = build_name_index(hist)
    assert find_duplicate(
        ["Liquid Soul & Vini Vici - Universe Inside Me.mp3"], idx) is not None


def test_duplicado_no_encontrado():
    idx = build_name_index(HIST)
    assert find_duplicate(["Stephan Bodzin - Strand.mp3"], idx) is None


def test_entrada_sin_destino_se_ignora():
    idx = build_name_index([{'artista': 'X', 'destino': ''}])
    assert idx == {}


def test_roundtrip_load_save(tmp_path):
    p = tmp_path / "historial.json"
    assert save_history(p, HIST) is True
    assert load_history(p) == HIST


def test_load_inexistente_o_corrupto_devuelve_lista_vacia(tmp_path):
    assert load_history(tmp_path / "no_existe.json") == []
    p = tmp_path / "roto.json"
    p.write_text("{no es json", encoding="utf-8")
    assert load_history(p) == []

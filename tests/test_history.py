"""Tests de core/history.py — historial persistente y detección de duplicados."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.history import (build_disk_index, build_name_index,
                          find_disk_duplicate, find_disk_duplicates_all,
                          find_duplicate, load_history,
                          normalize_name, save_history)


def _es_audio(name):
    return name.lower().endswith(('.mp3', '.wav', '.flac', '.aiff'))

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


def test_disk_index_detecta_dup_por_archivo_en_disco(tmp_path):
    # Un track físicamente en la biblioteca se detecta aunque NO esté en historial.
    lib = tmp_path / "Trance" / "Iboga" / "2016"
    lib.mkdir(parents=True)
    ordenado = lib / "Ace Ventura & Loud - Our Moment (Captain Hook Remix).mp3"
    ordenado.write_text("x")
    (lib / "portada.jpg").write_text("no audio")  # se ignora
    idx = build_disk_index(tmp_path, _es_audio)
    # Cargando una copia sin ordenar (otra ruta, orden de artistas distinto).
    sin_ordenar = tmp_path / "Loud & Ace Ventura - Our Moment (Captain Hook Remix).mp3"
    sin_ordenar.write_text("x")
    dup = find_disk_duplicate([sin_ordenar.name], idx, [sin_ordenar])
    assert dup is not None
    assert dup['origen'] == 'biblioteca'
    assert dup['destino'] == str(ordenado)


def test_disk_dup_excluye_el_mismo_archivo(tmp_path):
    # Si el único match es el propio archivo que se carga -> NO es duplicado.
    lib = tmp_path / "Trance"; lib.mkdir()
    f = lib / "A - Track.mp3"; f.write_text("x")
    idx = build_disk_index(tmp_path, _es_audio)
    assert find_disk_duplicate([f.name], idx, [f]) is None


def test_disk_dup_dos_copias_detecta_la_otra(tmp_path):
    # Dos copias del mismo tema en la biblioteca (una sin ordenar y otra
    # ordenada): cargando una, detecta la otra.
    ordenado = tmp_path / "Trance" / "Iboga" / "2016" / "A - Track.mp3"
    ordenado.parent.mkdir(parents=True)
    ordenado.write_text("x")
    sin_ordenar = tmp_path / "zzz" / "A - Track.mp3"
    sin_ordenar.parent.mkdir(parents=True)
    sin_ordenar.write_text("x")
    idx = build_disk_index(tmp_path, _es_audio)
    dup = find_disk_duplicate([sin_ordenar.name], idx, [sin_ordenar])
    assert dup is not None and dup['destino'] == str(ordenado)


def test_disk_dups_all_lista_todos_los_del_compilado(tmp_path):
    # Un compilado con VARIOS tracks ya en la biblioteca: los devuelve TODOS
    # (no solo el primero), para mostrarlos de una.
    lib = tmp_path / "Trance" / "Iboga" / "2016"
    lib.mkdir(parents=True)
    (lib / "A - Uno.mp3").write_text("x")
    (lib / "B - Dos.mp3").write_text("x")
    idx = build_disk_index(tmp_path, _es_audio)
    comp = tmp_path / "VA - Compilado"
    comp.mkdir()
    t1 = comp / "A - Uno.mp3"; t1.write_text("x")
    t2 = comp / "B - Dos.mp3"; t2.write_text("x")
    t3 = comp / "C - Nuevo.mp3"; t3.write_text("x")   # este NO está en la biblioteca
    names = [t1.name, t2.name, t3.name]
    dups = find_disk_duplicates_all(names, idx, [t1, t2, t3])
    assert len(dups) == 2                              # solo los dos que ya existen
    nombres = {d['nombre'] for d in dups}
    assert nombres == {"A - Uno.mp3", "B - Dos.mp3"}
    assert all(d['origen'] == 'biblioteca' for d in dups)
    destinos = {d['destino'] for d in dups}
    assert str(lib / "A - Uno.mp3") in destinos


def test_disk_dups_all_vacio_si_nada_repetido(tmp_path):
    lib = tmp_path / "Trance"; lib.mkdir()
    (lib / "A - Uno.mp3").write_text("x")
    idx = build_disk_index(tmp_path, _es_audio)
    nuevo = tmp_path / "zzz" / "Z - Otro.mp3"
    nuevo.parent.mkdir()
    nuevo.write_text("x")
    assert find_disk_duplicates_all([nuevo.name], idx, [nuevo]) == []


def test_disk_index_ignora_carpetas(tmp_path):
    # Una copia en un backup de Traktor NO debe contar como parte de la biblioteca.
    lib = tmp_path / "Trance"; lib.mkdir()
    (lib / "A - Track.mp3").write_text("x")
    backup = tmp_path / "Traktor playlist backup" / "lagger"; backup.mkdir(parents=True)
    (backup / "A - Track.mp3").write_text("x")
    key = normalize_name("A - Track")
    # sin ignorar: aparecen las dos rutas
    assert len(build_disk_index(tmp_path, _es_audio)[key]) == 2
    # ignorando el backup: queda solo la de la biblioteca
    idx = build_disk_index(tmp_path, _es_audio, ["Traktor playlist backup"])
    assert len(idx[key]) == 1 and "backup" not in idx[key][0].lower()


def test_disk_index_base_inexistente_es_vacio(tmp_path):
    assert build_disk_index(tmp_path / "no_existe", _es_audio) == {}

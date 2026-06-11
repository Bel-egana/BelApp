"""Tests de core/metadata.py — extensiones de audio/imagen y tags ID3/FLAC."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.metadata import (MUTAGEN_OK, is_audio, is_image, read_id3,
                           write_id3_tags)


def test_is_audio():
    assert is_audio("track.mp3")
    assert is_audio("track.FLAC")
    assert is_audio("track.wav")
    assert not is_audio("portada.jpg")
    assert not is_audio("notas.txt")


def test_is_image():
    assert is_image("portada.jpg")
    assert is_image("cover.PNG")
    assert not is_image("track.mp3")


def test_read_id3_archivo_invalido_devuelve_vacio(tmp_path):
    f = tmp_path / "no_es_audio.mp3"
    f.write_bytes(b"esto no es un mp3")
    assert read_id3(f) == {}


def test_write_extension_no_soportada_devuelve_false(tmp_path):
    f = tmp_path / "archivo.txt"
    f.write_text("hola")
    assert write_id3_tags(f, "A", "T", "Al", "L", "G", "2024") is False


@pytest.mark.skipif(not MUTAGEN_OK, reason="mutagen no instalado")
def test_roundtrip_escribir_y_leer_mp3(tmp_path):
    f = tmp_path / "track.mp3"
    f.write_bytes(b"")
    ok = write_id3_tags(f, "CamelPhat", "For A Feeling", "Single",
                        "RCA", "Deep & Progressive House", "2020")
    assert ok is True
    tags = read_id3(f)
    assert tags["artist"] == "CamelPhat"
    assert tags["title"] == "For A Feeling"
    assert tags["label"] == "RCA"
    assert tags["year"] == "2020"

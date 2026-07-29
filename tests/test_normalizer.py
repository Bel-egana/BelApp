"""Tests de core/normalizer.py — normalización a la taxonomía específica de Bel."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.metadata import MUTAGEN_OK, read_id3, write_id3_tags
from core.normalizer import normalize_folder

pytestmark = pytest.mark.skipif(not MUTAGEN_OK, reason="mutagen no instalado")


def _mp3(folder, name, genre):
    f = folder / name
    f.write_bytes(b"")
    write_id3_tags(f, "Artista", "Track", "", "Sello",
                   genre if genre is not None else "", "2020")
    return f


def test_preview_clasifica_bien(tmp_path):
    _mp3(tmp_path, "a.mp3", "Melodic House & Techno")     # -> Ethereal / Melodic / Techno (cambio)
    _mp3(tmp_path, "b.mp3", "Techno (Peak Time / Driving)")  # -> Techno (cambio)
    _mp3(tmp_path, "c.mp3", "Psychedelic")                # -> Psytrance (cambio)
    _mp3(tmp_path, "d.mp3", "Acid Techno")                # ya es categoría -> already_ok
    _mp3(tmp_path, "e.mp3", "Blues")                      # no mapea -> no_match
    _mp3(tmp_path, "f.mp3", None)                         # sin género -> no_genre

    r = normalize_folder(str(tmp_path), dry_run=True)
    assert r["total"] == 6
    assert len(r["changed"]) == 3
    assert r["already_ok"] == 1
    assert r["no_match"] == 1
    assert r["no_genre"] == 1
    cambios = {c["old"]: c["new"] for c in r["changed"]}
    assert cambios["Melodic House & Techno"] == "Ethereal / Melodic / Techno"
    assert cambios["Techno (Peak Time / Driving)"] == "Techno"
    assert cambios["Psychedelic"] == "Psytrance"


def test_dry_run_no_modifica(tmp_path):
    f = _mp3(tmp_path, "a.mp3", "Psychedelic")
    normalize_folder(str(tmp_path), dry_run=True)
    assert read_id3(f)["genre"] == "Psychedelic"   # sin cambios en dry-run


def test_apply_reescribe_preservando_lo_demas(tmp_path):
    f = _mp3(tmp_path, "a.mp3", "Progressive House, Techno")
    r = normalize_folder(str(tmp_path), dry_run=False)
    assert len(r["changed"]) == 1
    tags = read_id3(f)
    assert tags["genre"] == "Progressive House"   # normalizado
    assert tags["artist"] == "Artista"            # lo demás intacto
    assert tags["year"] == "2020"

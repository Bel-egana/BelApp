"""Tests de api.py — el puente PyWebView (instanciado sin ventana)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import Api


def test_get_config_sin_archivo_devuelve_defaults(tmp_path):
    api = Api(config_path=tmp_path / "config.json",
              history_path=tmp_path / "historial.json")
    cfg = api.get_config()
    assert cfg["discogs_token"] == ""
    assert cfg["base_path"]            # algún default no vacío


def test_save_y_get_config_roundtrip(tmp_path):
    api = Api(config_path=tmp_path / "config.json",
              history_path=tmp_path / "historial.json")
    assert api.save_config_values("D:/Mi Música", "tok123") is True
    cfg = api.get_config()
    assert cfg["base_path"] == "D:/Mi Música"
    assert cfg["discogs_token"] == "tok123"


# ── Vista Cargar ──────────────────────────────────────────────────────────────

def _api(tmp_path):
    return Api(config_path=tmp_path / "config.json",
               history_path=tmp_path / "historial.json")


def test_load_tracks_lee_y_parsea(tmp_path):
    api = _api(tmp_path)
    f = tmp_path / "CamelPhat - For A Feeling.mp3"
    f.write_bytes(b"")
    out = api.load_tracks([str(f)], [], 0)
    assert len(out["items"]) == 1
    it = out["items"][0]
    assert it["type"] == "track"
    assert it["artist"] == "CamelPhat"
    assert it["title"] == "For A Feeling"
    assert it["is_dup"] is False


def test_load_tracks_ignora_no_audio_y_repetidos(tmp_path):
    api = _api(tmp_path)
    a = tmp_path / "A - B.mp3"
    a.write_bytes(b"")
    t = tmp_path / "notas.txt"
    t.write_text("x")
    out = api.load_tracks([str(a), str(t), str(a)], [], 0)
    assert len(out["items"]) == 1
    assert out["skipped"] == 1   # el repetido (el .txt se ignora silencioso)


def test_load_tracks_respeta_tope(tmp_path):
    api = _api(tmp_path)
    paths = []
    for i in range(30):
        f = tmp_path / f"Artista - Track {i:02d}.mp3"
        f.write_bytes(b"")
        paths.append(str(f))
    out = api.load_tracks(paths, [], 0)
    assert len(out["items"]) == 25
    assert out["capped"] is True


def test_duplicado_contra_historial(tmp_path):
    from core.history import save_history
    hist = tmp_path / "historial.json"
    save_history(hist, [{"artista": "X", "track": "Y", "fecha": "01/01/2026",
                         "destino": r"D:\M\X - Y.mp3"}])
    api = Api(config_path=tmp_path / "c.json", history_path=hist)
    f = tmp_path / "X - Y.mp3"
    f.write_bytes(b"")
    out = api.load_tracks([str(f)], [], 0)
    assert out["items"][0]["is_dup"] is True
    assert out["items"][0]["dup_fecha"] == "01/01/2026"


def test_scan_folder_tracks_y_albums(tmp_path):
    api = _api(tmp_path)
    (tmp_path / "A - Uno.mp3").write_bytes(b"")
    alb = tmp_path / "Artista - Disco (2020)"
    alb.mkdir()
    (alb / "Artista - T1.mp3").write_bytes(b"")
    (alb / "Artista - T2.mp3").write_bytes(b"")
    out = api.scan_folder(str(tmp_path), [], 0)
    types = sorted(i["type"] for i in out["items"])
    assert types == ["album", "track"]
    album = [i for i in out["items"] if i["type"] == "album"][0]
    assert album["n_tracks"] == 2
    assert album["artist"] == "Artista"
    assert album["album"] == "Disco"


def test_load_album_folder_sin_audio_da_error(tmp_path):
    api = _api(tmp_path)
    vacia = tmp_path / "Carpeta Vacia"
    vacia.mkdir()
    out = api.load_album_folder(str(vacia), [], 0)
    assert "error" in out

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


# ── Vista Buscar ──────────────────────────────────────────────────────────────

def test_search_discogs_sin_token_da_error(tmp_path):
    api = _api(tmp_path)
    out = api.search_discogs("algo", "")
    assert "error" in out


def test_search_discogs_parsea_y_reporta_fallback(tmp_path, monkeypatch):
    import api as api_mod
    api = _api(tmp_path)
    api.save_config_values("D:/M", "tok")
    monkeypatch.setattr(
        api_mod.discogs_core, "search_with_fallback",
        lambda q, t, fallback="", limit=10: (
            [{"title": "Artista - Tema", "year": 2020,
              "label": ["Sello"], "style": ["Trance"]}], True))
    out = api.search_discogs("query completa", "Artista")
    assert out["used_fallback"] is True
    assert out["results"][0]["artist"] == "Artista"
    assert out["results"][0]["genre"] == "Trance"


def test_search_discogs_error_de_red_devuelve_error(tmp_path, monkeypatch):
    import api as api_mod
    api = _api(tmp_path)
    api.save_config_values("D:/M", "tok")

    def boom(*a, **k):
        raise RuntimeError("sin red")

    monkeypatch.setattr(api_mod.discogs_core, "search_with_fallback", boom)
    out = api.search_discogs("q", "")
    assert "sin red" in out["error"]


def test_preview_destination(tmp_path):
    api = _api(tmp_path)
    p = api.preview_destination("D:/M", "Trance", "Iboga", "2012", "t.mp3")
    assert "Trance" in p and "Iboga" in p and "2012" in p
    assert p.endswith("t.mp3")


def test_get_genres_devuelve_las_categorias(tmp_path):
    api = _api(tmp_path)
    genres = api.get_genres()
    assert "Trance" in genres
    assert "Melodic Techno & Techno" in genres


# ── Vista Resultado: mover + deshacer ─────────────────────────────────────────

def _track_item(path, **kw):
    from pathlib import Path as _P
    d = {'type': 'track', 'path': str(path), 'name': _P(path).name,
         'artist': 'A', 'title': 'T', 'album': '',
         'genre': 'Trance', 'label': 'Iboga', 'year': '2012'}
    d.update(kw)
    return d


def test_move_track_escribe_tags_historial_txt(tmp_path):
    from core.history import load_history
    api = _api(tmp_path)
    base = tmp_path / "Música"
    base.mkdir()
    src = tmp_path / "A - T.mp3"
    src.write_bytes(b"")
    res = api.move_items([_track_item(src)], str(base), "2026_06")
    assert res["moved"] == 1 and res["errors"] == 0
    dest = base / "Trance" / "Iboga" / "2012" / "A - T.mp3"
    assert dest.exists() and not src.exists()
    hist = load_history(tmp_path / "historial.json")
    assert any(h["destino"] == str(dest) for h in hist)
    txt = base / "belapp_2026_06.txt"
    assert str(dest) in txt.read_text(encoding="utf-8")


def test_move_no_pisa_destino_existente(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "M"
    dest = base / "Trance" / "Iboga" / "2012" / "A - T.mp3"
    dest.parent.mkdir(parents=True)
    dest.write_text("ya existe")
    src = tmp_path / "A - T.mp3"
    src.write_bytes(b"nuevo")
    res = api.move_items([_track_item(src)], str(base), "2026_06")
    assert res["moved"] == 0
    assert src.exists()                       # no se movió
    assert dest.read_text() == "ya existe"    # no se pisó


def test_undo_restaura_y_limpia(tmp_path):
    from core.history import load_history
    api = _api(tmp_path)
    base = tmp_path / "M"
    base.mkdir()
    src = tmp_path / "A - T.mp3"
    src.write_bytes(b"")
    api.move_items([_track_item(src)], str(base), "2026_06")
    dest = base / "Trance" / "Iboga" / "2012" / "A - T.mp3"
    assert dest.exists()
    out = api.undo_last_move()
    assert out["restored"] == 1
    assert src.exists() and not dest.exists()
    assert load_history(tmp_path / "historial.json") == []
    txt = base / "belapp_2026_06.txt"
    assert str(dest) not in txt.read_text(encoding="utf-8")


def test_undo_limpia_carpetas_destino_vacias(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "Música"
    base.mkdir()
    pack = tmp_path / "src"
    pack.mkdir()
    src = pack / "A - T.mp3"
    src.write_bytes(b"")
    api.move_items([_track_item(src)], str(base), "2026_06")
    genre_dir = base / "Trance"
    assert genre_dir.exists()           # se crearon las carpetas destino
    api.undo_last_move()
    assert src.exists()                 # el archivo volvió
    assert not genre_dir.exists()       # las carpetas destino vacías se limpiaron
    assert base.exists()                # la base queda intacta


def test_move_album_completo(tmp_path):
    from core.history import load_history
    api = _api(tmp_path)
    base = tmp_path / "M"
    base.mkdir()
    alb = tmp_path / "Artista - Disco"
    alb.mkdir()
    (alb / "Artista - T1.mp3").write_bytes(b"")
    (alb / "Artista - T2.mp3").write_bytes(b"")
    item = {'type': 'album', 'path': str(alb), 'name': 'Artista - Disco',
            'artist': 'Artista', 'title': '', 'album': 'Disco',
            'genre': 'Trance', 'label': 'Iboga', 'year': '2012'}
    res = api.move_items([item], str(base), "2026_06")
    assert res["moved_albums"] == 1
    ddir = base / "Trance" / "Iboga" / "2012" / "Artista - Disco"
    assert (ddir / "Artista - T1.mp3").exists()
    assert (ddir / "Artista - T2.mp3").exists()
    assert len(load_history(tmp_path / "historial.json")) == 2


def test_move_limpia_carpeta_origen_vacia(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "Música"
    base.mkdir()
    pack = tmp_path / "Pack descargado"
    pack.mkdir()
    src = pack / "A - T.mp3"
    src.write_bytes(b"")
    api.move_items([_track_item(src)], str(base), "2026_06")
    assert not pack.exists()        # la carpeta vacía se eliminó


def test_move_no_borra_carpeta_origen_con_otros_archivos(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "Música"
    base.mkdir()
    pack = tmp_path / "Pack"
    pack.mkdir()
    src = pack / "A - T.mp3"
    src.write_bytes(b"")
    (pack / "cover.jpg").write_bytes(b"img")   # queda otro archivo
    api.move_items([_track_item(src)], str(base), "2026_06")
    assert pack.exists()            # NO se borra: no estaba vacía


def test_move_no_borra_la_carpeta_base(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "Música"
    base.mkdir()
    src = base / "A - T.mp3"        # track suelto en la raíz de la base
    src.write_bytes(b"")
    api.move_items([_track_item(src)], str(base), "2026_06")
    assert base.exists()            # nunca se borra la carpeta base


def test_get_period_count(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "M"
    base.mkdir()
    src = tmp_path / "A - T.mp3"
    src.write_bytes(b"")
    api.move_items([_track_item(src)], str(base), "2026_06")
    assert api.get_period_count(str(base), "2026_06") == 1
    assert api.get_period_count(str(base), "2099_99") == 0


# ── Vista Historial ───────────────────────────────────────────────────────────

def test_get_history_devuelve_lo_guardado(tmp_path):
    from core.history import save_history
    hist = tmp_path / "historial.json"
    save_history(hist, [{"artista": "A", "track": "T", "destino": r"D:\M\A - T.mp3"}])
    api = Api(config_path=tmp_path / "c.json", history_path=hist)
    out = api.get_history()
    assert len(out) == 1 and out[0]["artista"] == "A"


def test_get_history_vacio_si_no_existe(tmp_path):
    assert _api(tmp_path).get_history() == []


def test_delete_history_entry_por_destino(tmp_path):
    from core.history import load_history, save_history
    hist = tmp_path / "historial.json"
    save_history(hist, [{"artista": "A", "destino": r"D:\M\A.mp3"},
                        {"artista": "B", "destino": r"D:\M\B.mp3"}])
    api = Api(config_path=tmp_path / "c.json", history_path=hist)
    assert api.delete_history_entry(r"D:\M\A.mp3") is True
    rest = load_history(hist)
    assert len(rest) == 1 and rest[0]["artista"] == "B"


def test_clear_history(tmp_path):
    from core.history import load_history, save_history
    hist = tmp_path / "historial.json"
    save_history(hist, [{"artista": "A", "destino": r"D:\M\A.mp3"}])
    api = Api(config_path=tmp_path / "c.json", history_path=hist)
    assert api.clear_history() is True
    assert load_history(hist) == []


def test_write_history_xlsx(tmp_path):
    from openpyxl import load_workbook
    api = _api(tmp_path)
    out = tmp_path / "h.xlsx"
    api._write_history_xlsx(str(out), [
        {"fecha": "01/01/2026", "artista": "A", "track": "T",
         "genero": "Trance", "sello": "S", "año": "2020", "destino": "D:/x.mp3"}])
    ws = load_workbook(out).active
    assert ws["A1"].value == "Fecha"      # encabezado
    assert ws["B2"].value == "A"          # artista de la 1ra fila
    assert ws["C2"].value == "T"

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
    assert it["search_query"] == "CamelPhat For A Feeling"   # desde el nombre del archivo


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


def test_load_tracks_dedup_por_ruta(tmp_path):
    api = _api(tmp_path)
    f = tmp_path / "A - B.mp3"
    f.write_bytes(b"")
    out1 = api.load_tracks([str(f)], [], 0)
    assert len(out1["items"]) == 1
    out2 = api.load_tracks([str(f)], [str(f)], 1)   # mismo archivo ya cargado
    assert len(out2["items"]) == 0 and out2["skipped"] == 1


def test_load_tracks_mismo_nombre_distinta_carpeta_entran_los_dos(tmp_path):
    api = _api(tmp_path)
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    f1 = tmp_path / "x" / "Track.mp3"
    f2 = tmp_path / "y" / "Track.mp3"
    f1.write_bytes(b"")
    f2.write_bytes(b"")
    out = api.load_tracks([str(f1), str(f2)], [], 0)
    assert len(out["items"]) == 2   # mismo nombre pero distinta ruta -> ambos


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


def test_get_genres_specific_devuelve_los_12(tmp_path):
    api = _api(tmp_path)
    g = api.get_genres_specific()
    assert len(g) == 13
    assert "Techno" in g and "Psytrance" in g and "Deep House" in g
    assert "Minimal Techno" in g and "House" in g


def test_get_specific_to_broad_mapea_12_a_4(tmp_path):
    api = _api(tmp_path)
    m = api.get_specific_to_broad()
    assert m["Techno"] == "Melodic Techno & Techno"
    assert m["Deep House"] == "Deep & Progressive House"
    assert m["Psytrance"] == "Psychedelic Trance"
    assert m["Minimal Techno"] == "Melodic Techno & Techno"
    assert m["House"] == "Deep & Progressive House"
    assert len(m) == 13


def test_load_tracks_detecta_genero_especifico_del_tag(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    f = tmp_path / "A - T.mp3"
    f.write_bytes(b"")
    # Beatport etiqueta así; debe detectarse como "Ethereal / Melodic Techno" (de los 12)
    write_id3_tags(f, "A", "T", "", "Lab", "Melodic House & Techno", "2020")
    out = api.load_tracks([str(f)], [], 0)
    assert out["items"][0]["genre_specific"] == "Ethereal / Melodic Techno"


def test_suggest_labels_detecta_parecidos(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "Musica"
    for sello in ("Stil Vor Talent", "Set About Music", "Steyoyoke", "Sin Sello"):
        (base / "Melodic Techno & Techno" / sello).mkdir(parents=True)
    # typo/transposición -> sugiere la existente
    assert "Stil Vor Talent" in api.suggest_labels(str(base), "Stir Vol Talent")
    # sufijo (Music) -> sugiere la existente
    assert "Set About Music" in api.suggest_labels(str(base), "Set About")
    # idéntico a una existente -> no avisa (es reuso, no duplicado)
    assert api.suggest_labels(str(base), "Steyoyoke") == []
    # sello nuevo y realmente distinto -> no avisa
    assert api.suggest_labels(str(base), "Anjunadeep") == []
    # base inexistente -> no rompe
    assert api.suggest_labels(str(tmp_path / "nope"), "X") == []


def test_scan_folder_skip_year_saltea_carpetas_de_anio(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "sello"; base.mkdir()
    (base / "A - Uno.mp3").write_bytes(b"")            # suelto
    (base / "B - Dos.mp3").write_bytes(b"")            # suelto
    ep = base / "Artista - EP"; ep.mkdir()             # álbum sin ordenar
    (ep / "C - EnEP.mp3").write_bytes(b"")
    yr = base / "2023"; yr.mkdir()                     # año ya organizado
    (yr / "D - EnAnio.mp3").write_bytes(b"")

    # skip_year=True -> 2 sueltos + el EP (álbum), pero NO la carpeta "2023"
    r = api.scan_folder(str(base), [], 0, skip_year=True)
    tipos = sorted(it["type"] for it in r["items"])
    assert tipos.count("track") == 2
    assert tipos.count("album") == 1
    assert r["skipped_years"] == 1          # salteó la carpeta "2023"

    # normal (skip_year=False) -> lo mismo + "2023" también como álbum
    r2 = api.scan_folder(str(base), [], 0)
    assert sorted(it["type"] for it in r2["items"]).count("album") == 2


def test_review_folder_genres_lista_todos(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    base = tmp_path / "sello"; base.mkdir()

    def mk(n, g):
        f = base / n; f.write_bytes(b"")
        if g is not None:
            write_id3_tags(f, "Ar", "Ti", "", "La", g, "2023")
        return f

    mk("a.mp3", "Melodic House & Techno")   # mapea -> Ethereal / Melodic Techno
    mk("b.mp3", "Blues")                     # no mapea -> suggested ''
    mk("c.mp3", None)                        # sin género

    r = api.review_folder_genres(str(base))
    assert r["total"] == 3
    assert r["sin_genero"] == 1
    byname = {os.path.basename(t["path"]): t for t in r["tracks"]}
    assert byname["a.mp3"]["suggested"] == "Ethereal / Melodic Techno"
    assert byname["b.mp3"]["current"] == "Blues"
    assert byname["b.mp3"]["suggested"] == ""
    assert byname["c.mp3"]["current"] == ""


def test_apply_normalize_selected_solo_los_elegidos(tmp_path):
    from core.metadata import read_id3, write_id3_tags
    api = _api(tmp_path)
    a = tmp_path / "a.mp3"; a.write_bytes(b"")
    write_id3_tags(a, "Ar", "Ti", "", "La", "Melodic House & Techno", "2023")
    b = tmp_path / "b.mp3"; b.write_bytes(b"")
    write_id3_tags(b, "Ar", "Ti", "", "La", "Techno", "2023")

    # Aplico solo 'a', con destino explícito; 'b' no lo paso -> queda intacto.
    res = api.apply_normalize_selected(
        [{"path": str(a), "new": "Ethereal / Melodic Techno"}])
    assert res["applied"] == 1
    assert res["errors"] == []
    assert read_id3(a).get("genre") == "Ethereal / Melodic Techno"
    assert read_id3(b).get("genre") == "Techno"          # sin tocar

    # Ítems sin path o sin destino se ignoran (no rompe).
    res2 = api.apply_normalize_selected(
        [{"path": "", "new": "Techno"}, {"path": str(b), "new": ""}])
    assert res2["applied"] == 0


def test_dests_existentes(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "Musica"
    dest_dir = base / "Melodic Techno & Techno" / "Afterlife" / "2023"
    dest_dir.mkdir(parents=True)
    (dest_dir / "A - X.mp3").write_bytes(b"12345")          # destino existe (5 bytes)
    src = tmp_path / "A - X.mp3"; src.write_bytes(b"1234567890")  # nuevo (10 bytes)
    items = [
        {"name": "A - X.mp3", "type": "track", "path": str(src),
         "genre": "Melodic Techno & Techno", "label": "Afterlife", "year": "2023"},
        {"name": "B - Y.mp3", "type": "track", "path": str(tmp_path / "B - Y.mp3"),
         "genre": "Melodic Techno & Techno", "label": "Afterlife", "year": "2023"},
    ]
    res = api.dests_existentes(items, str(base))
    assert len(res) == 1
    assert res[0]["name"] == "A - X.mp3"
    assert res[0]["size_nuevo"] == 10          # el que se movería
    assert res[0]["size_existente"] == 5       # el que ya está


def test_generate_playlists_crea_m3u8_por_genero_year(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    base = tmp_path / "Musica"
    (base / "g").mkdir(parents=True)

    def mk(name, genre, year):
        f = base / "g" / name
        f.write_bytes(b"")
        write_id3_tags(f, "Art", "Tit", "", "Lab", genre, year)
        return f

    mk("a.mp3", "Ethereal / Melodic Techno", "2023")
    mk("b.mp3", "Ethereal / Melodic Techno", "2023")
    mk("c.mp3", "Deep House", "2022")
    mk("d.mp3", "", "2021")   # sin género -> se saltea

    out = tmp_path / "Playlists"
    res = api.generate_playlists(str(base), str(out))
    assert res.get("ok") is True
    assert res["playlists"] == 2
    assert res["tracks"] == 3
    # la '/' del género se sanea a '_' en el nombre del archivo
    f1 = out / "Ethereal _ Melodic Techno - 2023.m3u8"
    assert f1.exists()
    assert (out / "Deep House - 2022.m3u8").exists()
    txt = f1.read_text(encoding="utf-8")
    assert txt.startswith("#EXTM3U")
    assert str(base / "g" / "a.mp3") in txt
    assert str(base / "g" / "b.mp3") in txt


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


def test_move_escribe_especifico_en_tag_y_amplio_en_carpeta(tmp_path):
    # Caso Shamanic Tales: tag con el género real, carpeta donde Bel decide.
    from core.metadata import read_id3
    api = _api(tmp_path)
    base = tmp_path / "M"
    base.mkdir()
    src = tmp_path / "A - T.mp3"
    src.write_bytes(b"")
    item = _track_item(src, genre="Psychedelic Trance",
                       genre_specific="Melodic Techno")
    res = api.move_items([item], str(base), "2026_06")
    assert res["moved"] == 1
    # La carpeta usa el amplio (genre):
    dest = base / "Psychedelic Trance" / "Iboga" / "2012" / "A - T.mp3"
    assert dest.exists()
    # El tag usa el específico (genre_specific):
    assert read_id3(dest).get("genre") == "Melodic Techno"


def test_move_sin_especifico_usa_el_amplio_en_el_tag(tmp_path):
    # Compatibilidad: si no hay género específico, el tag usa el amplio.
    from core.metadata import read_id3
    api = _api(tmp_path)
    base = tmp_path / "M"
    base.mkdir()
    src = tmp_path / "A - T.mp3"
    src.write_bytes(b"")
    api.move_items([_track_item(src)], str(base), "2026_06")
    dest = base / "Trance" / "Iboga" / "2012" / "A - T.mp3"
    assert read_id3(dest).get("genre") == "Trance"


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


def _setup_recat(tmp_path):
    from core.history import save_history
    base = tmp_path / "M"
    old = base / "Trance" / "Sello" / "2020" / "A - T.mp3"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"")
    hist = tmp_path / "historial.json"
    save_history(hist, [{"artista": "A", "track": "T", "genero": "Trance",
                         "sello": "Sello", "año": "2020", "destino": str(old)}])
    api = Api(config_path=tmp_path / "c.json", history_path=hist)
    api.save_config_values(str(base), "")
    return api, base, old, hist


def test_recategorize_mueve_actualiza_y_limpia(tmp_path):
    from core.history import load_history
    api, base, old, hist = _setup_recat(tmp_path)
    res = api.recategorize_entry(str(old), "Psychedelic Trance", "Sello", "2020", True)
    assert res.get("ok")
    new = base / "Psychedelic Trance" / "Sello" / "2020" / "A - T.mp3"
    assert new.exists() and not old.exists()
    h = load_history(hist)[0]
    assert h["genero"] == "Psychedelic Trance"
    assert h["destino"] == str(new)
    assert not (base / "Trance").exists()       # carpeta vieja vacía eliminada


def test_recategorize_sin_limpiar_deja_carpeta_vieja(tmp_path):
    api, base, old, hist = _setup_recat(tmp_path)
    api.recategorize_entry(str(old), "Psychedelic Trance", "Sello", "2020", False)
    assert (base / "Trance").exists()           # sin limpiar: queda la carpeta vieja


def test_recategorize_no_pisa_destino_existente(tmp_path):
    api, base, old, hist = _setup_recat(tmp_path)
    dest = base / "Psychedelic Trance" / "Sello" / "2020" / "A - T.mp3"
    dest.parent.mkdir(parents=True)
    dest.write_text("ya existe")
    res = api.recategorize_entry(str(old), "Psychedelic Trance", "Sello", "2020", True)
    assert "error" in res
    assert old.exists()                         # no se movió


def test_recategorize_archivo_inexistente(tmp_path):
    api, base, old, hist = _setup_recat(tmp_path)
    old.unlink()
    res = api.recategorize_entry(str(old), "Trance", "Sello", "2020", True)
    assert "error" in res


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

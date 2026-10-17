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


def test_tour_flag_y_config_no_lo_pisa(tmp_path):
    api = _api(tmp_path)
    api.save_config_values("D:/Musica", "tok")
    assert api.tour_visto() is False
    api.marcar_tour_visto()
    assert api.tour_visto() is True
    # guardar base/token NO debe borrar el flag del tour
    api.save_config_values("D:/Otra", "tok2")
    assert api.tour_visto() is True
    assert api.get_config()["base_path"] == "D:/Otra"


def test_save_y_get_config_roundtrip(tmp_path):
    api = Api(config_path=tmp_path / "config.json",
              history_path=tmp_path / "historial.json")
    assert api.save_config_values("D:/Mi Música", "tok123") is True
    cfg = api.get_config()
    assert cfg["base_path"] == "D:/Mi Música"
    assert cfg["discogs_token"] == "tok123"


# ── Vista Cargar ──────────────────────────────────────────────────────────────

def _api(tmp_path):
    api = Api(config_path=tmp_path / "config.json",
              history_path=tmp_path / "historial.json")
    # Base aislada y VACÍA: así el índice de duplicados en disco no escanea la
    # biblioteca real del usuario (DEFAULT_BASE) durante los tests.
    lib = tmp_path / "_biblioteca"
    lib.mkdir(exist_ok=True)
    api.save_config_values(str(lib), "")
    return api


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
    for i in range(110):
        f = tmp_path / f"Artista - Track {i:03d}.mp3"
        f.write_bytes(b"")
        paths.append(str(f))
    out = api.load_tracks(paths, [], 0)
    assert len(out["items"]) == 100   # tope por tanda (MAX_ITEMS)
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
    dest = tmp_path / "org" / "X - Y.mp3"; dest.parent.mkdir()
    dest.write_bytes(b"")          # el archivo ya ordenado tiene que EXISTIR
    save_history(hist, [{"artista": "X", "track": "Y", "fecha": "01/01/2026",
                         "destino": str(dest)}])
    api = Api(config_path=tmp_path / "c.json", history_path=hist)
    api.save_config_values(str(tmp_path / "org"), "")   # base aislada (no la real)
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


def test_load_album_folders_carga_varias(tmp_path):
    api = _api(tmp_path)
    paths = []
    for i in range(3):
        ep = tmp_path / f"EP {i}"; ep.mkdir()
        (ep / f"Artista{i} - Track.mp3").write_bytes(b"x")
        paths.append(str(ep))
    vacia = tmp_path / "sin audio"; vacia.mkdir()   # una sin audio
    paths.append(str(vacia))
    out = api.load_album_folders(paths, [], 0)
    assert len(out["items"]) == 3
    assert out["no_audio"] == ["sin audio"]
    assert out["capped"] is False


def test_load_album_folders_respeta_tope(tmp_path):
    api = _api(tmp_path)
    paths = []
    for i in range(120):
        ep = tmp_path / f"EP {i:03d}"; ep.mkdir()
        (ep / f"A{i} - T.mp3").write_bytes(b"x")
        paths.append(str(ep))
    out = api.load_album_folders(paths, [], 0)
    assert len(out["items"]) == 100 and out["capped"] is True   # tope por tanda


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


def test_generate_playlists_filtra_por_genero_y_anio(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    lib = tmp_path / "lib"; lib.mkdir()
    def mk(name, g, y):
        f = lib / name; f.write_bytes(b"")
        write_id3_tags(f, "Ar", "Ti", "", "La", g, y)
    mk("a.mp3", "Deep House", "2022")
    mk("b.mp3", "Deep House", "2023")
    mk("c.mp3", "Techno", "2022")

    # solo por género
    r = api.generate_playlists(str(lib), str(tmp_path / "o1"), "Deep House", "")
    assert r.get("tracks") == 2
    assert (tmp_path / "o1" / "Deep House" / "2022.nml").exists()
    assert not (tmp_path / "o1" / "Techno" / "2022.nml").exists()

    # por género + año
    r2 = api.generate_playlists(str(lib), str(tmp_path / "o2"), "Deep House", "2022")
    assert r2.get("tracks") == 1
    assert (tmp_path / "o2" / "Deep House" / "2022.nml").exists()
    assert not (tmp_path / "o2" / "Deep House" / "2023.nml").exists()

    # sin filtro -> todos
    r3 = api.generate_playlists(str(lib), str(tmp_path / "o3"), "", "")
    assert r3.get("tracks") == 3

    # la palabra "todos" en año NO se toma literal -> equivale a todos
    r3b = api.generate_playlists(str(lib), str(tmp_path / "o3b"), "", "todos")
    assert r3b.get("tracks") == 3

    # filtro sin coincidencias -> error claro
    r4 = api.generate_playlists(str(lib), str(tmp_path / "o4"), "Trance", "")
    assert "error" in r4


def test_generate_playlists_log_y_tracks_afuera(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    lib = tmp_path / "lib"; lib.mkdir()
    ok = lib / "a.mp3"; ok.write_bytes(b"")
    write_id3_tags(ok, "Ar", "Ti", "", "La", "Deep House", "2022")
    (lib / "b.mp3").write_bytes(b"")          # sin tags -> queda afuera
    out = tmp_path / "o"

    r1 = api.generate_playlists(str(lib), str(out), "", "")
    assert r1["ya_fecha"] == ""               # primera vez, sin aviso
    assert r1["sin_tag"] == 1                  # b.mp3 quedó afuera
    assert r1["sin_tag_file"] and (out / r1["sin_tag_file"]).exists()
    assert len(api.get_playlists_log()) == 1

    r2 = api.generate_playlists(str(lib), str(out), "", "")
    assert r2["ya_fecha"] != ""                # segunda vez igual -> avisa
    assert len(api.get_playlists_log()) == 2


def test_buscar_duplicados_carpeta(tmp_path):
    api = Api(config_path=tmp_path / "c.json", history_path=tmp_path / "h.json")
    base = tmp_path / "Musica"
    lib = base / "Trance" / "Iboga"; lib.mkdir(parents=True)
    (lib / "A - Track.mp3").write_bytes(b"x" * 500)      # copia en la biblioteca
    api.save_config_values(str(base), "")
    carpeta = tmp_path / "revisar"; carpeta.mkdir()
    (carpeta / "A - Track.mp3").write_bytes(b"y" * 800)  # otra copia (más grande)
    (carpeta / "B - Unico.mp3").write_bytes(b"z")         # sin duplicado

    out = api.buscar_duplicados_carpeta(str(carpeta))
    assert out["grupos"] == 1                             # solo A tiene duplicado
    rp = carpeta / out["report_file"]
    assert rp.exists()
    txt = rp.read_text(encoding="utf-8")
    assert "A - Track.mp3" in txt
    assert "B - Unico" not in txt

    # carpeta sin duplicados -> 0
    limpia = tmp_path / "limpia"; limpia.mkdir()
    (limpia / "C - Solo.mp3").write_bytes(b"w")
    assert api.buscar_duplicados_carpeta(str(limpia))["grupos"] == 0


def test_review_y_apply_years(tmp_path):
    from core.metadata import write_id3_tags, read_id3
    api = _api(tmp_path)
    d20 = tmp_path / "lib" / "2020"; d20.mkdir(parents=True)
    a = d20 / "A - X.mp3"; a.write_bytes(b"")
    write_id3_tags(a, "Ar", "X", "", "La", "Deep House", "")     # sin año, en carpeta 2020
    b = tmp_path / "lib" / "B - Y.mp3"; b.write_bytes(b"")
    write_id3_tags(b, "Ar", "Y", "", "La", "Deep House", "2019")  # ya tiene año

    r = api.review_folder_years(str(tmp_path / "lib"))
    assert r["total"] == 2 and r["sin_anio"] == 1
    ta = [t for t in r["tracks"] if "A - X" in t["path"]][0]
    assert ta["current"] == "" and ta["suggested"] == "2020"     # sugiere de la carpeta

    out = api.apply_years_selected([{"path": str(a), "year": "2020"},
                                    {"path": str(b), "year": "0202"}])  # uno inválido
    assert out["applied"] == 1 and len(out["errors"]) == 1
    assert read_id3(a).get("year") == "2020"


def test_generate_playlists_ignora_anio_invalido(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    lib = tmp_path / "lib"; lib.mkdir()   # sin carpeta de año en el path
    f = lib / "a.mp3"; f.write_bytes(b"")
    write_id3_tags(f, "Ar", "Ti", "", "La", "Deep House", "0202")  # año basura
    r = api.generate_playlists(str(lib), str(tmp_path / "o"), "", "")
    assert "error" in r or r.get("tracks") == 0    # no arma playlist "0202"
    assert not (tmp_path / "o" / "Deep House" / "0202.nml").exists()


def test_generate_playlists_saca_anio_del_path_si_falta_tag(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    d = tmp_path / "lib" / "2019"; d.mkdir(parents=True)
    f = d / "a.mp3"; f.write_bytes(b"")
    write_id3_tags(f, "Ar", "Ti", "", "La", "Deep House", "")   # género sí, año NO
    r = api.generate_playlists(str(tmp_path / "lib"), str(tmp_path / "o"), "", "")
    assert r.get("tracks") == 1
    assert (tmp_path / "o" / "Deep House" / "2019.nml").exists()   # año del path


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


def test_dup_solo_si_el_archivo_del_historial_sigue_existiendo(tmp_path):
    import json
    api = _api(tmp_path)
    f = tmp_path / "A - X.mp3"; f.write_bytes(b"")          # el que se carga
    org = tmp_path / "org"; org.mkdir()
    dest = org / "A - X.mp3"; dest.write_bytes(b"")          # el ya ordenado (existe)
    hist = [{"artista": "A", "track": "X", "destino": str(dest)}]
    (tmp_path / "historial.json").write_text(json.dumps(hist), encoding="utf-8")

    # con el archivo del historial presente -> se marca dup
    assert api.load_tracks([str(f)], [], 0)["items"][0]["is_dup"] is True

    # lo borro -> la entrada quedó obsoleta -> NO se marca dup
    dest.unlink()
    assert api.load_tracks([str(f)], [], 0)["items"][0]["is_dup"] is False


def test_dup_detectado_por_biblioteca_en_disco_sin_historial(tmp_path):
    # Un track ya ordenado (físicamente en la biblioteca) se detecta desde la
    # primera pantalla AUNQUE no esté en el historial.
    api = Api(config_path=tmp_path / "c.json",
              history_path=tmp_path / "h.json")
    base = tmp_path / "Musica"
    ya = base / "Trance" / "Iboga" / "2016"
    ya.mkdir(parents=True)
    (ya / "Ace Ventura & Loud - Our Moment (Captain Hook Remix).mp3").write_bytes(b"x")
    api.save_config_values(str(base), "")

    # Lo cargo desde otra carpeta (Downloads), con el orden de artistas cambiado
    dl = tmp_path / "Downloads"; dl.mkdir()
    f = dl / "Loud & Ace Ventura - Our Moment (Captain Hook Remix).mp3"
    f.write_bytes(b"x")
    out = api.load_tracks([str(f)], [], 0)
    assert out["items"][0]["is_dup"] is True
    assert out["items"][0]["dup_info"]["origen"] == "biblioteca"


def test_dup_dos_copias_en_biblioteca_carga_la_sin_ordenar(tmp_path):
    # Caso real: la misma canción está DOS veces bajo la base (una ordenada en
    # Género/Sello/Año y otra en una carpeta 'zzz' sin ordenar). Al cargar la
    # de 'zzz', tiene que avisar que YA está ordenada (no excluirla como self).
    api = Api(config_path=tmp_path / "c.json", history_path=tmp_path / "h.json")
    base = tmp_path / "Musica"
    ordenada = base / "Psychedelic Trance" / "Iboga Records" / "2016" / \
        "Ace Ventura & Loud - Our Moment (Captain Hook Remix).mp3"
    ordenada.parent.mkdir(parents=True)
    ordenada.write_bytes(b"x")
    zzz = base / "Psychedelic Trance" / "zzz ace ventura" / \
        "Ace Ventura & Loud - Our Moment (Captain Hook Remix).mp3"
    zzz.parent.mkdir(parents=True)
    zzz.write_bytes(b"x")
    api.save_config_values(str(base), "")

    out = api.load_tracks([str(zzz)], [], 0)   # cargo la copia sin ordenar
    assert out["items"][0]["is_dup"] is True
    assert out["items"][0]["dup_info"]["destino"] == str(ordenada)


def test_dedup_ignora_backup_de_traktor_por_defecto(tmp_path):
    # La carpeta "Traktor playlist backup" se ignora POR DEFECTO (sin config):
    # una copia ahí adentro NO marca el track como duplicado.
    api = Api(config_path=tmp_path / "c.json", history_path=tmp_path / "h.json")
    base = tmp_path / "Musica"
    bkp = base / "Traktor playlist backup" / "lagger"; bkp.mkdir(parents=True)
    (bkp / "Aktyum - Monkey Island.mp3").write_bytes(b"x")
    api.save_config_values(str(base), "")

    dl = tmp_path / "Downloads"; dl.mkdir()
    f = dl / "Aktyum - Monkey Island.mp3"; f.write_bytes(b"x")
    assert api.load_tracks([str(f)], [], 0)["items"][0]["is_dup"] is False

    # pero una copia en una carpeta NORMAL de la biblioteca sí se detecta
    normal = base / "Trance" / "Iboga" / "2016"; normal.mkdir(parents=True)
    (normal / "Aktyum - Monkey Island.mp3").write_bytes(b"x")
    api._invalidate_disk_index()
    assert api.load_tracks([str(f)], [], 0)["items"][0]["is_dup"] is True


def test_dedup_ignore_configurable_por_config(tmp_path):
    # El mecanismo de ignorados por config sigue andando para otras carpetas.
    api = Api(config_path=tmp_path / "c.json", history_path=tmp_path / "h.json")
    base = tmp_path / "Musica"
    carpeta = base / "mis respaldos"; carpeta.mkdir(parents=True)
    (carpeta / "X - Y.mp3").write_bytes(b"x")
    dl = tmp_path / "dl"; dl.mkdir()
    f = dl / "X - Y.mp3"; f.write_bytes(b"x")

    api.save_config_values(str(base), "", "mis respaldos")
    assert api.load_tracks([str(f)], [], 0)["items"][0]["is_dup"] is False
    api.save_config_values(str(base), "", "")   # sin ignorarla -> se detecta
    assert api.load_tracks([str(f)], [], 0)["items"][0]["is_dup"] is True


def test_tamano_archivos_resuelve_carpeta_de_album(tmp_path):
    # Si el ítem es una CARPETA (EP/Album), tamano_archivos debe buscar adentro
    # el track que coincide por nombre y devolver SU tamaño (no -1).
    api = _api(tmp_path)
    ep = tmp_path / "Ghost Rider - Shamanic EP"; ep.mkdir()
    (ep / "Ghost Rider - Shamanic.mp3").write_bytes(b"x" * 500)
    dest = tmp_path / "org" / "Ghost Rider - Shamanic.mp3"
    dest.parent.mkdir(); dest.write_bytes(b"y" * 800)
    out = api.tamano_archivos(str(ep), str(dest))
    assert out["a"] == 500 and out["b"] == 800


def test_disk_index_listo_cambia_tras_primera_carga(tmp_path):
    api = Api(config_path=tmp_path / "c.json", history_path=tmp_path / "h.json")
    base = tmp_path / "Musica"; base.mkdir()
    api.save_config_values(str(base), "")
    assert api.disk_index_listo() is False        # todavía no escaneó
    f = tmp_path / "A - B.mp3"; f.write_bytes(b"x")
    api.load_tracks([str(f)], [], 0)
    assert api.disk_index_listo() is True          # ya cacheado
    # tras mover, se invalida y vuelve a False
    api._invalidate_disk_index()
    assert api.disk_index_listo() is False


def test_re_escanear_carpeta_ya_ordenada_no_marca_self_match(tmp_path):
    # Cargar un archivo que YA está en la biblioteca (el mismo, no una copia)
    # NO debe marcarse como duplicado de sí mismo.
    api = Api(config_path=tmp_path / "c.json",
              history_path=tmp_path / "h.json")
    base = tmp_path / "Musica"
    ya = base / "Trance" / "Iboga" / "2016"; ya.mkdir(parents=True)
    f = ya / "A - Track.mp3"; f.write_bytes(b"x")
    api.save_config_values(str(base), "")

    out = api.load_tracks([str(f)], [], 0)
    assert out["items"][0]["is_dup"] is False   # es él mismo, no un duplicado


def test_tamano_archivos(tmp_path):
    api = _api(tmp_path)
    a = tmp_path / "a.mp3"; a.write_bytes(b"12345")           # 5
    b = tmp_path / "b.mp3"; b.write_bytes(b"1234567890")      # 10
    assert api.tamano_archivos(str(a), str(b)) == {"a": 5, "b": 10}
    # inexistente -> -1
    r = api.tamano_archivos(str(a), str(tmp_path / "nope.mp3"))
    assert r["a"] == 5 and r["b"] == -1


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


def test_generate_playlists_crea_nml_por_genero_year(tmp_path):
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
    # la '/' del género se sanea a '_' en el nombre del archivo .nml
    f1 = out / "Ethereal _ Melodic Techno" / "2023.nml"
    assert f1.exists()
    assert (out / "Deep House" / "2022.nml").exists()
    txt = f1.read_text(encoding="utf-8")
    assert txt.startswith("<?xml")                       # .nml nativo de Traktor
    assert '<NODE TYPE="PLAYLIST" NAME="2023">' in txt
    assert 'FILE="a.mp3"' in txt and 'FILE="b.mp3"' in txt


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


def test_move_compilado_conserva_artista_por_track(tmp_path):
    from core.metadata import read_id3
    api = _api(tmp_path)
    base = tmp_path / "M"; base.mkdir()
    comp = tmp_path / "VA - Best Sets"; comp.mkdir()
    (comp / "Rocky Tilbor - Uno.mp3").write_bytes(b"")
    (comp / "Otro Dj - Dos.mp3").write_bytes(b"")
    (comp / "SinArtista.mp3").write_bytes(b"")      # sin artista en el nombre
    item = {'type': 'album', 'path': str(comp), 'name': 'VA - Best Sets',
            'artist': 'Best of my sets', 'title': '', 'album': 'Best Sets',
            'genre': 'Trance', 'label': 'Iboga', 'year': '2018'}
    api.move_items([item], str(base), "2026_06")
    ddir = base / "Trance" / "Iboga" / "2018" / "VA - Best Sets"
    # cada track conserva SU artista real
    assert read_id3(ddir / "Rocky Tilbor - Uno.mp3").get("artist") == "Rocky Tilbor"
    assert read_id3(ddir / "Otro Dj - Dos.mp3").get("artist") == "Otro Dj"
    # el que no trae artista en el nombre -> usa el del campo como respaldo
    assert read_id3(ddir / "SinArtista.mp3").get("artist") == "Best of my sets"
    # el año va igual para todos
    assert read_id3(ddir / "Otro Dj - Dos.mp3").get("year") == "2018"


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


# ── Config de playlists (auto-append) ────────────────────────────────────────
def test_playlists_dir_config_get_set(tmp_path):
    api = _api(tmp_path)
    assert api.get_playlists_dir() == ""
    api.set_playlists_dir(str(tmp_path / "pl"))
    assert api.get_playlists_dir() == str(tmp_path / "pl")


def test_playlists_auto_config_default_on(tmp_path):
    api = _api(tmp_path)
    assert api.get_playlists_auto() is True
    api.set_playlists_auto(False)
    assert api.get_playlists_auto() is False


def test_generate_playlists_persiste_dir(tmp_path):
    from core.metadata import write_id3_tags
    api = _api(tmp_path)
    lib = tmp_path / "lib"; lib.mkdir()
    f = lib / "a.mp3"; f.write_bytes(b"")
    write_id3_tags(f, "Ar", "Ti", "", "La", "Deep House", "2026")
    out = tmp_path / "pl"
    api.generate_playlists(str(lib), str(out), "", "")
    assert api.get_playlists_dir() == str(out)


# ── _append_to_playlists (agrupa por género/año y anexa) ──────────────────────
def test_append_to_playlists_crea_y_dedup(tmp_path):
    api = _api(tmp_path)
    out = tmp_path / "pl"
    api.set_playlists_dir(str(out))
    tracks = [{'path': str(tmp_path / "A - Uno.mp3"), 'title': 'Uno',
               'artist': 'A', 'genre': 'Deep House', 'label': 'L', 'year': '2026'}]
    upd = api._append_to_playlists(tracks)
    assert len(upd) == 1 and upd[0]['added'] == 1
    assert (out / "Deep House" / "2026.nml").exists()
    upd2 = api._append_to_playlists(tracks)
    assert upd2 == []


def test_append_to_playlists_sin_dir_no_hace_nada(tmp_path):
    api = _api(tmp_path)
    tracks = [{'path': str(tmp_path / "A - Uno.mp3"), 'title': 'Uno',
               'artist': 'A', 'genre': 'Deep House', 'label': 'L', 'year': '2026'}]
    assert api._append_to_playlists(tracks) == []


def test_append_to_playlists_ignora_anio_invalido(tmp_path):
    api = _api(tmp_path)
    api.set_playlists_dir(str(tmp_path / "pl"))
    tracks = [{'path': str(tmp_path / "A - Uno.mp3"), 'title': 'Uno',
               'artist': 'A', 'genre': 'Deep House', 'label': 'L', 'year': '0202'}]
    assert api._append_to_playlists(tracks) == []


# ── move_items actualiza las playlists ───────────────────────────────────────
def test_move_actualiza_playlists(tmp_path):
    api = _api(tmp_path)
    api.set_playlists_dir(str(tmp_path / "pl"))
    base = tmp_path / "M"; base.mkdir()
    src = tmp_path / "A - T.mp3"; src.write_bytes(b"")
    item = _track_item(src, genre="Deep House", year="2026")
    res = api.move_items([item], str(base), "2026_06")
    assert res["moved"] == 1
    assert any(p["name"] == "Deep House - 2026" and p["added"] == 1
               for p in res["playlists_updated"])
    assert (tmp_path / "pl" / "Deep House" / "2026.nml").exists()


def test_move_sin_playlists_dir_no_rompe(tmp_path):
    api = _api(tmp_path)
    base = tmp_path / "M"; base.mkdir()
    src = tmp_path / "A - T.mp3"; src.write_bytes(b"")
    res = api.move_items([_track_item(src)], str(base), "")
    assert res["moved"] == 1
    assert res["playlists_updated"] == []


# ── Abrir en carpeta: sube a la primera carpeta que exista ───────────────────
def test_open_target_archivo_existe(tmp_path):
    from pathlib import Path
    api = _api(tmp_path)
    folder = tmp_path / "Genero" / "Sello" / "2026"
    folder.mkdir(parents=True)
    f = folder / "x.mp3"; f.write_bytes(b"")
    # Devuelve la CARPETA que contiene al archivo.
    assert Path(api._open_target(str(f))) == folder


def test_open_target_archivo_falta_usa_carpeta_existente(tmp_path):
    from pathlib import Path
    api = _api(tmp_path)
    folder = tmp_path / "Genero" / "Sello" / "2026"
    folder.mkdir(parents=True)
    faltante = folder / "nombre-mal.mp3"   # el archivo no existe
    assert Path(api._open_target(str(faltante))) == folder


# ── Backfill del género del tag en el historial ──────────────────────────────
def test_backfill_history_genres(tmp_path):
    from core.metadata import write_id3_tags
    from core.history import save_history, load_history
    api = _api(tmp_path)
    f = tmp_path / "a.mp3"; f.write_bytes(b"")
    write_id3_tags(f, "Ar", "Ti", "", "La", "Deep House", "2026")
    save_history(tmp_path / "historial.json", [
        {'destino': str(f), 'genero': 'Deep & Progressive House'},
        {'destino': str(tmp_path / "no-existe.mp3"), 'genero': 'Trance'},
    ])
    r = api.backfill_history_genres()
    assert r['updated'] == 2
    hist = load_history(tmp_path / "historial.json")
    assert hist[0]['genero_especifico'] == 'Deep House'      # del tag
    assert hist[1]['genero_especifico'] == 'Trance'          # fallback al amplio
    # idempotente: segunda corrida no cambia nada
    assert api.backfill_history_genres()['updated'] == 0


def test_history_needs_genre_backfill(tmp_path):
    from core.history import save_history
    api = _api(tmp_path)
    save_history(tmp_path / "historial.json", [{'destino': 'x', 'genero': 'T'}])
    assert api.history_needs_genre_backfill() is True
    api.backfill_history_genres()
    assert api.history_needs_genre_backfill() is False


def test_move_guarda_genero_especifico(tmp_path):
    from core.history import load_history
    api = _api(tmp_path)
    base = tmp_path / "M"; base.mkdir()
    src = tmp_path / "A - T.mp3"; src.write_bytes(b"")
    item = _track_item(src, genre="Psychedelic Trance",
                       genre_specific="Melodic Techno", year="2026")
    api.move_items([item], str(base), "2026_06")
    hist = load_history(tmp_path / "historial.json")
    assert any(h.get('genero_especifico') == 'Melodic Techno' for h in hist)

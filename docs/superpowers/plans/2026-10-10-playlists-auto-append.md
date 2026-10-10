# Auto-append de playlists al ordenar — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que al ordenar música con BelApp, cada track nuevo se sume automáticamente a su playlist de género/año (`.nml`) sin duplicar, y que la app reporte qué playlists cambiaron para reimportar en Traktor.

**Architecture:** Un motor puro `append_tracks_to_nml` en `core/playlists.py` anexa tracks a un `.nml` existente (o lo crea). `move_items` junta los tracks recién ordenados y, al final, llama a un helper de api que agrupa por (género, año) y anexa a `<playlists_dir>\<Género>\<Año>.nml`. La carpeta de playlists se guarda en config.

**Tech Stack:** Python 3.13, pytest, PyWebView (UI web vanilla JS), PyInstaller.

**Spec:** `docs/superpowers/specs/2026-10-10-playlists-auto-append-design.md`

---

## File Structure

- `core/playlists.py` — motor de playlists. Se agregan helpers `_collection_entry`, `_playlist_entry` (refactor DRY) y `append_tracks_to_nml` (nuevo).
- `api.py` — `get/set_playlists_dir`, `get/set_playlists_auto`, `_append_to_playlists`, y el enganche en `move_items`. `generate_playlists` persiste la carpeta como `playlists_dir`.
- `web/index.html`, `web/app.js` — checkbox "Actualizar playlists al ordenar" y reporte en el log de resultado.
- `tests/test_playlists.py`, `tests/test_api.py` — tests nuevos.

---

## Task 1: Refactor del builder a helpers (DRY, sin cambiar output)

**Files:**
- Modify: `core/playlists.py` (función `build_traktor_playlist_nml`, ~líneas 98-135)

- [ ] **Step 1: Agregar los dos helpers antes de `build_traktor_playlist_nml`**

En `core/playlists.py`, justo antes de `def build_traktor_playlist_nml`, agregar:

```python
def _collection_entry(t):
    """Una <ENTRY> de la sección COLLECTION para un track (DRY)."""
    vol, dir_t, file = _split_traktor(t.get('path', ''))
    return (
        f'<ENTRY TITLE="{_xml_attr(t.get("title", ""))}" '
        f'ARTIST="{_xml_attr(t.get("artist", ""))}">'
        f'<LOCATION DIR="{_xml_attr(dir_t)}" FILE="{_xml_attr(file)}" '
        f'VOLUME="{_xml_attr(vol)}"></LOCATION>'
        f'<INFO GENRE="{_xml_attr(t.get("genre", ""))}" '
        f'LABEL="{_xml_attr(t.get("label", ""))}"></INFO></ENTRY>')


def _playlist_entry(t):
    """Una <ENTRY><PRIMARYKEY> de la sección PLAYLIST para un track (DRY)."""
    return (
        f'<ENTRY><PRIMARYKEY TYPE="TRACK" '
        f'KEY="{_xml_attr(traktor_key(t.get("path", "")))}">'
        f'</PRIMARYKEY></ENTRY>')
```

- [ ] **Step 2: Reescribir `build_traktor_playlist_nml` usando los helpers**

Reemplazar el cuerpo de `build_traktor_playlist_nml` (desde `import uuid` hasta el `return`) por:

```python
    import uuid
    usados = {}
    for t in tracks:
        usados.setdefault(t.get('path', ''), t)
    col = ''.join(_collection_entry(t) for t in usados.values())
    pk = ''.join(_playlist_entry(t) for t in tracks)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        '<NML VERSION="19"><HEAD COMPANY="www.native-instruments.com" PROGRAM="Traktor"></HEAD>\n'
        '<MUSICFOLDERS></MUSICFOLDERS>\n'
        f'<COLLECTION ENTRIES="{len(usados)}">' + col + '</COLLECTION>\n'
        '<PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="1">'
        f'<NODE TYPE="PLAYLIST" NAME="{_xml_attr(name)}">'
        f'<PLAYLIST ENTRIES="{len(tracks)}" TYPE="LIST" UUID="{uuid.uuid4().hex}">'
        + pk +
        '</PLAYLIST></NODE></SUBNODES></NODE></PLAYLISTS>\n</NML>\n')
```

- [ ] **Step 3: Correr toda la suite para verificar que el output no cambió**

Run: `cd /d/Belapp && python -m pytest -q`
Expected: PASS (154 passed) — el refactor no debe romper ningún test existente.

- [ ] **Step 4: Commit**

```bash
cd /d/Belapp && git add core/playlists.py && git commit -m "refactor: extraer _collection_entry/_playlist_entry del builder de .nml

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Motor `append_tracks_to_nml`

**Files:**
- Modify: `core/playlists.py` (agregar función después de `build_traktor_playlist_nml`)
- Test: `tests/test_playlists.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_playlists.py` (asegurar el import `from core.playlists import append_tracks_to_nml` arriba, junto a los otros imports de core.playlists):

```python
def _trk(path, title="T", artist="A", genre="Deep House", label=""):
    return {'path': path, 'title': title, 'artist': artist,
            'genre': genre, 'label': label}


def test_append_crea_si_no_existe():
    text, added = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    assert added == 1
    assert 'A - Uno.mp3' in text
    assert '<PLAYLIST ENTRIES="1"' in text


def test_append_suma_a_existente():
    base, _ = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    text, added = append_tracks_to_nml(base, '2026', [_trk(r'D:\M\B - Dos.mp3', title="Dos", artist="B")])
    assert added == 1
    assert 'A - Uno.mp3' in text and 'B - Dos.mp3' in text
    assert '<PLAYLIST ENTRIES="2"' in text
    assert '<COLLECTION ENTRIES="2">' in text


def test_append_dedup_no_reagrega():
    base, _ = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    text, added = append_tracks_to_nml(base, '2026', [_trk(r'D:\M\A - Uno.mp3')])
    assert added == 0
    assert text == base


def test_append_mezcla_suma_solo_lo_nuevo():
    base, _ = append_tracks_to_nml('', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    mezcla = [_trk(r'D:\M\A - Uno.mp3'), _trk(r'D:\M\C - Tres.mp3', title="Tres", artist="C")]
    text, added = append_tracks_to_nml(base, '2026', mezcla)
    assert added == 1
    assert '<PLAYLIST ENTRIES="2"' in text


def test_append_formato_raro_no_toca():
    text, added = append_tracks_to_nml('esto no es un nml', '2026', [_trk(r'D:\M\A - Uno.mp3')])
    assert added == -1
    assert text == 'esto no es un nml'
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd /d/Belapp && python -m pytest tests/test_playlists.py -q`
Expected: FAIL con `ImportError: cannot import name 'append_tracks_to_nml'`.

- [ ] **Step 3: Implementar `append_tracks_to_nml`**

En `core/playlists.py`, después de `build_traktor_playlist_nml`, agregar (asegurar que `import re` esté al tope del archivo — ya se usa en `nml_filename`):

```python
def append_tracks_to_nml(existing, name, new_tracks):
    """Anexa new_tracks a un .nml existente SIN pisar lo que ya tiene ni duplicar.
    'existing' = texto del .nml actual, o '' / None si no existe.
    Devuelve (texto, agregados). agregados == -1 si el .nml existe pero su formato
    no es reconocible (en ese caso NO se modifica)."""
    if not existing or not existing.strip():
        text = build_traktor_playlist_nml(name, new_tracks)
        keys = {traktor_key(t.get('path', '')) for t in new_tracks if t.get('path')}
        return text, len(keys)

    m_col = re.search(r'<COLLECTION ENTRIES="(\d+)">', existing)
    m_pl = re.search(r'<PLAYLIST ENTRIES="(\d+)" TYPE="LIST"', existing)
    if not (m_col and m_pl and '</COLLECTION>' in existing
            and '</PLAYLIST>' in existing):
        return existing, -1   # formato no reconocido: no tocar

    presentes = set(re.findall(r'PRIMARYKEY TYPE="TRACK" KEY="([^"]*)"', existing))
    nuevos, vistos = [], set(presentes)
    for t in new_tracks:
        k = traktor_key(t.get('path', ''))
        if not k or k in vistos:
            continue
        vistos.add(k)
        nuevos.append(t)
    if not nuevos:
        return existing, 0

    col_add = ''.join(_collection_entry(t) for t in nuevos)
    pk_add = ''.join(_playlist_entry(t) for t in nuevos)
    n = len(nuevos)
    text = existing
    text = text.replace('</COLLECTION>', col_add + '</COLLECTION>', 1)
    text = text.replace('</PLAYLIST>', pk_add + '</PLAYLIST>', 1)
    text = text.replace(m_col.group(0),
                        f'<COLLECTION ENTRIES="{int(m_col.group(1)) + n}">', 1)
    text = text.replace(m_pl.group(0),
                        f'<PLAYLIST ENTRIES="{int(m_pl.group(1)) + n}" TYPE="LIST"', 1)
    return text, n
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd /d/Belapp && python -m pytest tests/test_playlists.py -q`
Expected: PASS (todos los nuevos verdes).

- [ ] **Step 5: Commit**

```bash
cd /d/Belapp && git add core/playlists.py tests/test_playlists.py && git commit -m "feat: append_tracks_to_nml — anexar a playlist existente sin duplicar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Config de playlists (dir + toggle) y persistencia en generate_playlists

**Files:**
- Modify: `api.py` (métodos de config, cerca de `tour_visto`/`marcar_tour_visto`, ~líneas 84-91; y `generate_playlists`, dentro del bloque de éxito antes del `return`, ~línea 327)
- Test: `tests/test_api.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_api.py` (el helper `_api` ya existe):

```python
def test_playlists_dir_config_get_set(tmp_path):
    api = _api(tmp_path)
    assert api.get_playlists_dir() == ""        # default vacío
    api.set_playlists_dir(str(tmp_path / "pl"))
    assert api.get_playlists_dir() == str(tmp_path / "pl")


def test_playlists_auto_config_default_on(tmp_path):
    api = _api(tmp_path)
    assert api.get_playlists_auto() is True      # default: activado
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
    assert api.get_playlists_dir() == str(out)   # quedó guardada la carpeta
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd /d/Belapp && python -m pytest tests/test_api.py -q -k "playlists_dir or playlists_auto or persiste_dir"`
Expected: FAIL con `AttributeError: 'Api' object has no attribute 'get_playlists_dir'`.

- [ ] **Step 3: Agregar los métodos de config**

En `api.py`, después de `marcar_tour_visto` (~línea 91), agregar:

```python
    def get_playlists_dir(self):
        """Carpeta fija del árbol de playlists (.nml) para el auto-append."""
        return (load_config(self._config_path).get('playlists_dir') or '').strip()

    def set_playlists_dir(self, path):
        data = load_config(self._config_path)
        data['playlists_dir'] = (path or '').strip()
        return save_config(self._config_path, data)

    def get_playlists_auto(self):
        """¿Actualizar playlists automáticamente al ordenar? (default: sí)."""
        return bool(load_config(self._config_path).get('playlists_auto', True))

    def set_playlists_auto(self, on):
        data = load_config(self._config_path)
        data['playlists_auto'] = bool(on)
        return save_config(self._config_path, data)
```

- [ ] **Step 4: Persistir la carpeta en `generate_playlists`**

En `api.py`, dentro de `generate_playlists`, en el bloque de éxito, justo antes de `self._last_dir = str(out_p)` (~línea 327), agregar:

```python
            # Recordar esta carpeta para el auto-append al ordenar.
            try:
                cfg_pl = load_config(self._config_path)
                cfg_pl['playlists_dir'] = str(out_p)
                save_config(self._config_path, cfg_pl)
            except Exception:
                pass
```

Verificar que `save_config` esté importado en `api.py` (ya lo está: se usa en `save_config_values`).

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run: `cd /d/Belapp && python -m pytest tests/test_api.py -q -k "playlists_dir or playlists_auto or persiste_dir"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /d/Belapp && git add api.py tests/test_api.py && git commit -m "feat: config playlists_dir/playlists_auto + generate_playlists recuerda la carpeta

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Helper `_append_to_playlists` en api

**Files:**
- Modify: `api.py` (nuevo método privado; import de `append_tracks_to_nml`)
- Test: `tests/test_api.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_api.py`:

```python
def test_append_to_playlists_crea_y_dedup(tmp_path):
    api = _api(tmp_path)
    out = tmp_path / "pl"
    api.set_playlists_dir(str(out))
    tracks = [{'path': str(tmp_path / "A - Uno.mp3"), 'title': 'Uno',
               'artist': 'A', 'genre': 'Deep House', 'label': 'L', 'year': '2026'}]
    upd = api._append_to_playlists(tracks)
    assert len(upd) == 1 and upd[0]['added'] == 1
    nml = out / "Deep House" / "2026.nml"
    assert nml.exists()
    # Segunda vez el mismo track -> no duplica, no reporta cambios
    upd2 = api._append_to_playlists(tracks)
    assert upd2 == []


def test_append_to_playlists_sin_dir_no_hace_nada(tmp_path):
    api = _api(tmp_path)   # sin playlists_dir
    tracks = [{'path': str(tmp_path / "A - Uno.mp3"), 'title': 'Uno',
               'artist': 'A', 'genre': 'Deep House', 'label': 'L', 'year': '2026'}]
    assert api._append_to_playlists(tracks) == []


def test_append_to_playlists_ignora_anio_invalido(tmp_path):
    api = _api(tmp_path)
    api.set_playlists_dir(str(tmp_path / "pl"))
    tracks = [{'path': str(tmp_path / "A - Uno.mp3"), 'title': 'Uno',
               'artist': 'A', 'genre': 'Deep House', 'label': 'L', 'year': '0202'}]
    assert api._append_to_playlists(tracks) == []
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd /d/Belapp && python -m pytest tests/test_api.py -q -k "append_to_playlists"`
Expected: FAIL con `AttributeError: ... '_append_to_playlists'`.

- [ ] **Step 3: Agregar el import y el método**

En `api.py`, línea 27, el import actual es:

```python
from core.playlists import build_traktor_playlist_nml, group_by_genre_year
```

Cambiarlo a:

```python
from core.playlists import (append_tracks_to_nml, build_traktor_playlist_nml,
                            group_by_genre_year)
```

Luego, agregar el método (por ejemplo justo después de `_pl_log_path`, ~línea 336):

```python
    def _append_to_playlists(self, pl_new):
        """Anexa los tracks recién ordenados a sus .nml de género/año en la
        carpeta de playlists configurada. Devuelve [{'name','file','added'}] de
        las que cambiaron. Nunca frena el ordenado si algo falla."""
        data = load_config(self._config_path)
        pdir = (data.get('playlists_dir') or '').strip()
        if not pdir or not data.get('playlists_auto', True):
            return []
        out_p = Path(pdir)
        try:
            out_p.mkdir(parents=True, exist_ok=True)
        except OSError:
            return []
        grupos = {}
        for t in pl_new:
            year = (t.get('year') or '').strip()
            genre = (t.get('genre') or '').strip()
            if not genre or not re.fullmatch(r'(19|20)\d\d', year):
                continue
            grupos.setdefault((genre, year), []).append(t)
        updated = []
        for (genre, year), items in grupos.items():
            try:
                safe = re.sub(r'[<>:"/\\|?*]', '_', genre).strip() or 'Sin género'
                gdir = out_p / safe
                gdir.mkdir(parents=True, exist_ok=True)
                fp = gdir / f'{year}.nml'
                existing = fp.read_text(encoding='utf-8') if fp.exists() else ''
                text, added = append_tracks_to_nml(existing, str(year), items)
                if added > 0:
                    fp.write_text(text, encoding='utf-8')
                    updated.append({'name': f'{safe} - {year}',
                                    'file': f'{safe}/{year}.nml', 'added': added})
            except Exception:
                continue
        return updated
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `cd /d/Belapp && python -m pytest tests/test_api.py -q -k "append_to_playlists"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /d/Belapp && git add api.py tests/test_api.py && git commit -m "feat: _append_to_playlists — agrupa por genero/anio y anexa a los .nml

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Enganche en `move_items`

**Files:**
- Modify: `api.py` (`move_items`, ~líneas 652-764)
- Test: `tests/test_api.py`

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_api.py` (usa el helper `_track_item` ya existente):

```python
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
    api = _api(tmp_path)   # sin playlists_dir
    base = tmp_path / "M"; base.mkdir()
    src = tmp_path / "A - T.mp3"; src.write_bytes(b"")
    res = api.move_items([_track_item(src)], str(base), "")
    assert res["moved"] == 1
    assert res["playlists_updated"] == []
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `cd /d/Belapp && python -m pytest tests/test_api.py -q -k "move_actualiza_playlists or sin_playlists_dir"`
Expected: FAIL con `KeyError: 'playlists_updated'`.

- [ ] **Step 3: Inicializar la lista `pl_new` en `move_items`**

En `api.py`, en `move_items`, en la línea que inicializa acumuladores (`folders, log, new_hist, txt_paths = set(), [], [], []`, ~línea 654), agregar `pl_new` justo después:

```python
        folders, log, new_hist, txt_paths = set(), [], [], []
        pl_new = []   # tracks para anexar a las playlists de género/año
```

- [ ] **Step 4: Juntar el track suelto en `pl_new`**

En el bloque `if it['type'] == 'track':`, después de `txt_paths.append(str(dest))` (~línea 696), agregar:

```python
                    pl_new.append({'path': str(dest), 'title': title,
                                   'artist': it['artist'], 'genre': tag_genre,
                                   'label': it['label'], 'year': it['year']})
```

(`tag_genre` ya está definido más arriba en ese bloque como el género específico escrito al tag.)

- [ ] **Step 5: Juntar cada track del compilado en `pl_new`**

En el bloque `else:` (álbum), dentro del `for tf in sorted(dest.iterdir()):`, después de `txt_paths.append(str(tf))` (~línea 730), agregar:

```python
                        pl_new.append({'path': str(tf),
                                       'title': ap.get('title') or tf.stem,
                                       'artist': tf_artist, 'genre': tag_genre,
                                       'label': it['label'], 'year': it['year']})
```

- [ ] **Step 6: Llamar al helper y devolver el reporte**

En `move_items`, después de `self._invalidate_disk_index()` (~línea 757) y antes del `L(f"✓ Listo! ...")`, agregar:

```python
        playlists_updated = self._append_to_playlists(pl_new)
```

Y en el `return` final, agregar la clave `'playlists_updated': playlists_updated`:

```python
        return {'log': log, 'moved': moved_t, 'moved_albums': moved_a,
                'errors': errors, 'new_folders': len(folders),
                'txt_count': txt_count, 'moved_sources': moved_sources,
                'open_dir': last_dir, 'playlists_updated': playlists_updated}
```

- [ ] **Step 7: Correr los tests nuevos y la suite completa**

Run: `cd /d/Belapp && python -m pytest -q`
Expected: PASS (todo verde, incluidos los nuevos).

- [ ] **Step 8: Commit**

```bash
cd /d/Belapp && git add api.py tests/test_api.py && git commit -m "feat: move_items anexa a las playlists y reporta cuales cambiaron

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: UI — checkbox y reporte en el log

**Files:**
- Modify: `web/index.html` (panel de Mantenimiento; agregar checkbox)
- Modify: `web/app.js` (cargar/guardar el toggle; mostrar `playlists_updated` tras ordenar)

- [ ] **Step 1: Agregar el checkbox en el HTML**

En `web/index.html`, en el panel de Mantenimiento (cerca de `btn-playlists`), agregar un checkbox. Buscar el botón `id="btn-playlists"` y agregar, en la misma zona de Mantenimiento:

```html
<label class="chk" title="Al ordenar, suma los tracks nuevos a las playlists de género/año existentes">
  <input type="checkbox" id="chk-pl-auto" checked>
  Actualizar playlists al ordenar
</label>
```

- [ ] **Step 2: Cargar y guardar el estado del checkbox en app.js**

En `web/app.js`, en la inicialización (donde se cargan otros valores de config al arrancar; buscar `api().get_config` o el arranque `DOMContentLoaded`), agregar:

```javascript
  // Estado del auto-append de playlists
  try {
    const on = await api().get_playlists_auto();
    const c = $('#chk-pl-auto');
    if (c) {
      c.checked = on;
      c.addEventListener('change', () => api().set_playlists_auto(c.checked));
    }
  } catch (e) { /* si falla, queda el default del HTML */ }
```

- [ ] **Step 3: Mostrar el reporte tras ordenar**

En `web/app.js`, donde se procesa el resultado de `api().move_items(...)` (buscar `move_items` o donde se arma el log de resultado), después de mostrar el log, agregar:

```javascript
  if (res.playlists_updated && res.playlists_updated.length) {
    const detalle = res.playlists_updated
      .map((p) => `${p.name} (+${p.added})`).join(', ');
    flashMsg(`🎵 Playlists actualizadas: ${detalle}. Reimportá solo esas en Traktor.`, 600000);
  }
```

(Si ya hay un `flashMsg` de cierre en ese flujo, poner este después para que quede visible; usa 600000 ms como los otros mensajes largos.)

- [ ] **Step 4: Verificación manual**

No hay harness de JS. Verificar a ojo que:
- El HTML del checkbox quedó dentro del panel de Mantenimiento.
- Los nombres de ids coinciden (`chk-pl-auto`).
- El bloque de `playlists_updated` está en el flujo correcto del resultado de ordenar.

- [ ] **Step 5: Commit**

```bash
cd /d/Belapp && git add web/index.html web/app.js && git commit -m "feat(ui): checkbox de auto-append + reporte de playlists actualizadas

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Rebuild del .exe y smoke test manual

**Files:** ninguno (build + prueba)

- [ ] **Step 1: Cerrar BelApp si está abierta**

Run (PowerShell): `Stop-Process -Name BelApp -Force -ErrorAction SilentlyContinue`
Nota: avisar a Belén antes, porque pierde lo que tenga cargado en la app.

- [ ] **Step 2: Recompilar**

Run: `cd /d/Belapp && python -m PyInstaller BelApp.spec --noconfirm --clean`
Expected: `Build complete! The results are available in: D:\Belapp\dist`

- [ ] **Step 3: Relanzar**

Run (PowerShell): `Start-Process -FilePath "D:\Belapp\dist\BelApp.exe"`

- [ ] **Step 4: Smoke test manual (con Belén)**

1. Configurar/confirmar la carpeta de playlists (generar una vez si hace falta, para que quede en config).
2. Ordenar un track nuevo de un género/año que ya tenga playlist.
3. Verificar el mensaje "🎵 Playlists actualizadas: … (+1)".
4. Abrir el `.nml` de ese género/año y confirmar que el track nuevo se sumó y lo viejo sigue.
5. Reordenar lo mismo → no debe reportar cambios (dedup).
6. En Traktor, reimportar esa playlist y confirmar que aparece completa.

- [ ] **Step 5: Commit final (si hubo ajustes del smoke test)**

```bash
cd /d/Belapp && git add -A && git commit -m "chore: ajustes de smoke test del auto-append de playlists

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas de verificación del plan (self-review)

- **Cobertura del spec:** config `playlists_dir`/toggle (Task 3), motor append+dedup+formato raro (Task 2), agrupado por género/año y escritura (Task 4), enganche en move + reporte (Task 5), UI checkbox + reporte (Task 6), rebuild (Task 7). ✅
- **Consistencia de tipos:** `append_tracks_to_nml(existing, name, new_tracks) -> (text, added)` usado igual en Tasks 2/4; `_append_to_playlists(pl_new) -> [{name,file,added}]` usado en Tasks 4/5; clave `playlists_updated` en Task 5 y UI Task 6. ✅
- **Formato de carpeta/nombre:** `<safe_genre>/<year>.nml`, nombre de playlist `str(year)` — idéntico a `generate_playlists`. ✅

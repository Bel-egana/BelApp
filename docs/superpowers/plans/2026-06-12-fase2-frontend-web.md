# BelApp Fase 2 — Frontend web + puente api.py

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Este plan se ejecuta INLINE con Belén (validación visual por vista). El contrato de la API y la arquitectura están completos acá; el código HTML/CSS/JS de cada vista se escribe en ejecución contra los criterios de aceptación de cada tarea y se valida con Belén antes de avanzar.

**Goal:** Construir la interfaz web-style (opción C del spec) sobre PyWebView, vista por vista, hasta paridad funcional con la app tkinter.

**Architecture:** 3 capas: `web/` (HTML/CSS/JS, una página con 4 vistas) ↔ `api.py` (clase puente `js_api`) ↔ `core/` (lógica testeada, 41 tests). El estado de UI (lista de ítems, selección, status por ítem) vive en JS; el estado operacional (config, historial, undo) vive en Python. Las llamadas `pywebview.api.*` devuelven JSON y corren en hilos propios de PyWebView (no bloquean la UI).

**Tech Stack:** pywebview 6.2.1 (WebView2), HTML/CSS/JS vanilla sin build, pytest.

**Spec:** `docs/superpowers/specs/2026-06-11-webstyle-ui-design.md` (checklist de paridad en sección 4).

---

## Design tokens (del mockup C aprobado)

```css
--bg:#0c0c10; --sidebar:#121218; --surface:#15151c; --surface2:#1d1d26;
--border:#24242c; --accent:#e8ff00; --accent2:#ff3c6e; --text:#e8e8e8;
--muted:#8a8a98; --success:#00ffa3; --warning:#ffaa00; --info:#5599ff; --purple:#a78bfa;
```
Radius: 14px cards / 10px botones / 999px pills. Font: `'Segoe UI', system-ui, sans-serif`. Sidebar 200px con íconos SVG inline (sin CDN: la UI no depende de internet).

## Contrato de datos JS ↔ Python

**Item** (Python→JS al cargar): `{id, type:'track'|'album', name, folder_name, path, artist, title, album, genre, label, year, has_id3, n_tracks, is_dup, dup_fecha}`

**Estado JS por ítem** (solo frontend): `status:'pending'|'confirmed'|'skipped'`, `flag:''|'noresult'|'review'`, `conf:{genre,label,year}`, `destination`.

**move_items** (JS→Python): lista de confirmados `{type, path, name, artist, title, album, genre, label, year}` + `base_path` + `period` → devuelve `{log:[{text,kind}], moved, moved_albums, errors, new_folders, txt_count}` y deja registrado el undo.

**Errores:** toda función de api devuelve `{error: 'mensaje'}` en fallas esperables (sin red, sin permisos); JS las muestra en la vista, nunca crashea.

## api.py — contrato completo

```python
class Api:
    def __init__(self, config_path=CONFIG_PATH, history_path=HISTORY_PATH)
    def set_window(self, window)                  # para diálogos nativos

    # Config (Task 1)
    def get_config(self) -> dict                  # {base_path, discogs_token}
    def save_config_values(self, base_path, discogs_token) -> bool

    # Cargar (Task 2)
    def pick_folder(self) -> str | None           # FOLDER_DIALOG
    def pick_tracks(self) -> list[str]            # OPEN_DIALOG múltiple, filtro audio
    def load_tracks(self, paths, existing_names) -> {items, skipped}
    def load_album_folder(self, path, existing) -> {item} | {error}
    def scan_folder(self, path, existing, count) -> {items, skipped, capped}
    # MAX_ITEMS=25 se aplica en scan/load (capped=True al llegar al tope)
    # is_dup se calcula contra core.history.build_name_index(historial)

    # Buscar (Task 3)
    def search_discogs(self, query, artist_fallback) -> {results, used_fallback} | {error}
    def preview_destination(self, base, genre, label, year, name) -> str
    def open_beatport(self, query); def open_token_page(self)

    # Mover (Task 4)
    def move_items(self, items, base_path, period) -> dict   # ver contrato arriba
    def undo_last_move(self) -> {restored, skipped, errors, problems}
    def get_period_count(self, base_path, period) -> int

    # Historial (Task 5)
    def get_history(self) -> list                 # completo; filtra JS
    def delete_history_entry(self, destino) -> bool
    def clear_history(self) -> bool
    def export_history_csv(self) -> {path} | {error} | None   # SAVE_DIALOG
    def open_in_explorer(self, path)
```

Reusa de `core/`: config, metadata (read/write tags, is_audio, is_image), discogs (search_with_fallback, parse), history (load/save/index/find_duplicate), organizer (build_path), parsing, genres (BEL_GENRES para el combo). La lógica de mover/undo/TXT replica el comportamiento de `belapp.py` (mismos guards: origen inexistente, destino existe, permisos).

---

### Task 1: Esqueleto — main.py + api.py (config) + shell web con sidebar

**Files:** Create `main.py`, `api.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_api.py`

- [ ] Tests de config de Api (tmp_path) → fallan → crear `api.py` con `__init__/set_window/get_config/save_config_values` → pasan
- [ ] `main.py`: crea ventana 1200x760 sobre `web/index.html`, `js_api=api`, bg `#0c0c10`
- [ ] Shell web: sidebar (logo BelApp + 4 navs con íconos SVG: Cargar/Buscar/Resultado/Historial) + 4 `<section>` vacías + footer de estado; `pywebviewready` → `get_config()` y muestra base_path en footer (prueba el puente)
- [ ] **Validación Belén:** ventana moderna abre, navegación entre vistas funciona, footer muestra su carpeta (= puente vivo)
- [ ] `pytest -q` verde → commit `feat(web): esqueleto PyWebView + api config + shell con sidebar`

**Aceptación:** look = mockup C (sidebar oscura, ítem activo resaltado, hover); sin errores en consola.

### Task 2: Vista Cargar

**Files:** Modify `api.py` (+pick/load/scan), `web/*`; Test `tests/test_api.py` (+load_tracks con mp3 temporales, scan con tope, duplicado flagueado vs historial temporal)

- [ ] Tests → código api → verdes
- [ ] UI: fila config (carpeta base editable + Cambiar, token con ojo + Obtener token), botones (+ Tracks / + Carpeta EP/Album / Escanear / Limpiar), tabla de ítems (tipo, nombre, artista, tags ✓, dup ⚠ en warning), contador, botón Continuar (deshabilitado sin ítems; guarda config al avanzar)
- [ ] **Validación Belén** con sus archivos reales → commit

**Aceptación:** paridad con tab 01 tkinter incl. tope 25 con aviso, dups en naranja "⚠ YA EN HISTORIAL".

### Task 3: Vista Buscar & Confirmar

**Files:** Modify `api.py` (+search/preview/beatport), `web/*`; Test (+search_discogs con monkeypatch)

- [ ] Tests → código → verdes
- [ ] UI: panel izquierdo de ítems (✓ verde / ⧖ naranja / ✗ rojo / — gris, click navega, contador "X/Y confirmados · ✗ N para revisar"), búsqueda editable con auto-search al cargar ítem, botón Beatport, tabla resultados (auto-selecciona 1°, llena Datos para mover), Datos para mover (combo BEL_GENRES + sello + año + preview de ruta), botones Saltar / ✗ Sin match (toggle) / ✓ Usar / ✓ Confirmar / ▶ Mover
- [ ] Lógica de flags en JS: noresult automático (se limpia si aparecen resultados), review manual persistente, confirmar limpia flag y auto-avanza al próximo pendiente
- [ ] **Validación Belén** con búsqueda real (red) → commit

**Aceptación:** paridad con tab 02 incl. fallback por artista con aviso "reintentando solo con…".

### Task 4: Vista Resultado + mover + deshacer

**Files:** Modify `api.py` (+move_items/undo/period), `web/*`; Test (+move e undo roundtrip con archivos y carpetas temporales — los tests más valiosos de la fase)

- [ ] Tests: mover track escribe tags y aparece en historial+TXT; destino existente → warn sin pisar; undo restaura y limpia registros; álbum completo
- [ ] UI: confirmación con aviso de dups, spinner "Moviendo…", cards resumen (tracks/albums/salteados/carpetas), log coloreado, período activo editable + Nuevo período, botón ⮌ Deshacer (habilitado tras mover), contador TXT
- [ ] JS: tras mover OK, quitar movidos de la lista de ítems (fallidos/salteados quedan)
- [ ] **Validación Belén:** mover de verdad + deshacer de verdad → commit

**Aceptación:** paridad con tab 03 incl. `[tags ✓]` en log y TXT por período.

### Task 5: Vista Historial

**Files:** Modify `api.py` (+history ops), `web/*`; Test (+delete_entry/clear con historial temporal)

- [ ] Tests → código → verdes
- [ ] UI: buscador live (filtra en JS), tabla (fecha/artista/track/género/sello/año/destino, reciente primero), doble-click y botón Abrir en carpeta, click derecho → menú (abrir/copiar ruta/eliminar con confirmación), Exportar CSV (diálogo nativo), Limpiar historial, contador
- [ ] **Validación Belén** → commit

**Aceptación:** paridad con tab 04; historial SIEMPRE accesible desde la sidebar.

### Task 6: Paridad final y cierre de fase

- [ ] Recorrer con Belén el checklist completo de paridad (spec sección 4) en la app nueva, flujo real de punta a punta
- [ ] Arreglar lo que salga; suite completa verde; actualizar README (cómo correr `python main.py`)
- [ ] Commit `chore: cierre fase 2 — frontend web con paridad completa`
- [ ] La app tkinter (`belapp.py`) NO se borra todavía — se retira recién al cerrar Fase 3 (exe) estable

**Fuera de este plan:** Fase 3 (PyInstaller → belapp.exe, smoke en máquina limpia).

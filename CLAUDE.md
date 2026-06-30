# CLAUDE.md — BelApp

Organizador de música para DJs (de Belén). Busca metadata en **Discogs**, deja
validar/editar, escribe tags ID3/FLAC y **mueve** archivos a `Género/Sello/Año/`.
Incluye un **normalizador** que limpia los géneros sucios de la biblioteca de Traktor.

## Correr / buildear
- Dev:   `python main.py`
- Tests: `python -m pytest tests/ -q`   (~89, deben quedar verdes)
- Build: `pyinstaller --noconfirm --onefile --windowed --name BelApp --icon assets/icon.ico --add-data "web;web" main.py` → `dist/BelApp.exe`
- ⚠️ Cerrar `BelApp.exe` antes de buildear (si está abierto → "Acceso denegado": `Get-Process BelApp | Stop-Process -Force`).
- Deps: requests, mutagen, pywebview, openpyxl (+ pyinstaller, pillow para build/ícono).

## Arquitectura (3 capas)
- `web/` (index.html + style.css + app.js): UI moderna, 4 vistas. Estado de UI en JS.
- `api.py`: clase `Api` = puente PyWebView (`pywebview.api.metodo()` desde JS). Pegamento fino.
- `core/`: LÓGICA PURA y testeada (sin UI). Acá va todo lo importante.
- `belapp.py`: versión vieja en **tkinter**, se mantiene SOLO de referencia (no es la app actual).
- Datos escribibles (`config.json`, `historial.json`) viven **al lado del .exe** (o del código en dev), vía `core/paths.py`. `web/` se empaqueta dentro del exe (`sys._MEIPASS`).

## core/ (qué hace cada módulo)
- `parsing.py`  — `parse_filename` ("Artista - Título.mp3"→dict), `parse_folder_name` ("Artista - Album (2020)"→dict).
- `genres.py`   — mapeos de género (ver abajo).
- `organizer.py`— `build_path(base, genre, label, year, name)`.
- `metadata.py` — `is_audio/is_image`, `read_id3`, `write_id3_tags` (mp3/wav/aiff + flac); `MUTAGEN_OK`.
- `discogs.py`  — `discogs_search` (rate-limit 1.1s), `search_with_fallback` (reintenta solo con artista), `parse_discogs_result`.
- `history.py`  — `load/save_history`, `build_name_index`, `find_duplicate`, `normalize_name`.
- `config.py`   — `load_config`/`save_config`.
- `normalizer.py`— `normalize_folder(folder, dry_run)` (usa `map_genre_specific`).
- `paths.py`    — rutas compatibles con PyInstaller (frozen vs dev).

## Géneros — DOS taxonomías (no confundir)
**1) Para ORGANIZAR (move flow + carpetas en disco) → 4 categorías.**
`BEL_GENRES` = Deep & Progressive House · Melodic Techno & Techno · Psychedelic Trance · Trance.
`GENRE_MAP` (dict, `genres.py`) y `format_genre(raw)`: substring case-insensitive, **gana la 1ª clave** que aparece (las específicas van primero). Mapea estilos de Discogs → una de las 4. '' si no matchea.

**2) Para el NORMALIZADOR (limpia tags de la biblioteca Traktor) → 12 categorías.**
`BEL_GENRES_SPECIFIC` = Melodic Techno, Techno, Acid Techno, Deep House, Melodic House,
Progressive House, Tech House, Afro / Organic House, Indie Dance, Trance, Psytrance, Progressive Psy.
`SPECIFIC_RULES` (lista ORDENADA) + `map_genre_specific(raw)`: misma idea (substring, 1ª que matchea).
Decisiones: "Melodic House & Techno" (Beatport) → **Melodic Techno**; prog+uplifting trance unificados → **Trance**. Lo que no matchea → '' (se deja sin tocar).

## Convención de carpetas (en disco)
`build_path` → `BASE / Género / Sello / Año / archivo`. Si falta un dato usa placeholder:
`Sin Género`, `Sin Sello`, `Sin Año`. (Windows: nombres de carpeta NO son case-sensitive).

## Convenciones de código / reglas importantes
- Comentarios y UI en **español**.
- Lógica testeable en `core/` (funciones puras); `api.py` y `web/` son finos.
- **NUNCA se borran archivos de audio.** Solo se MUEVE (`shutil.move`) y se borran carpetas VACÍAS (`rmdir`). "Eliminar" del historial borra solo el registro JSON, no el archivo.
- Operaciones de archivo con guardas: no pisa destino existente, captura permisos. Hay "Deshacer" (último movimiento) y "Corregir ubicación".
- Dedup de carga: por **ruta completa** del archivo (dos archivos distintos con igual nombre sí entran).
- Búsqueda en Discogs: arranca del **nombre del archivo** (no de los tags ID3, que suelen venir sucios).
- Campos Artista/Título (en "Datos para mover"): arrancan de la data del **nombre del archivo**; elegir un resultado de Discogs llena Sello/Año (y la Carpeta solo si está vacía) pero **NO** pisa Artista/Título (el "título" de Discogs es el del álbum, no el del track). Para un EP/álbum el campo se llama "Álbum".
- **Dos géneros, separados** (al mover): el campo **"Género (va al tag)"** usa los **12 específicos** (sale del tag que el archivo ya trae, vía `map_genre_specific`, editable) y es lo que se **escribe en el tag ID3/FLAC** (para las playlists de Traktor). El campo **"Carpeta (en disco)"** usa los **4 amplios** y define la carpeta física; se **deduce** del específico con `broad_from_specific`/`SPECIFIC_TO_BROAD` pero es editable (caso Shamanic Tales: tag real ≠ carpeta elegida). Si no hay específico, el tag cae en el amplio. `item['genre']`=carpeta, `item['genre_specific']`=tag.
- Tope `MAX_ITEMS = 25` ítems por tanda.
- Diálogos de archivo arrancan en la carpeta base (Música) y recuerdan la última usada.

## Contexto entorno
- Proyecto real: **`D:\Belapp`** (fuera de OneDrive). Acceso directo del Escritorio → `dist\BelApp.exe`.
- Biblioteca de música: `D:\Bel\Música` (~18k tracks; ~10k sin género = pendiente auto-tagging).
- Belén: DJ aprendiendo dev. Hablar en español/criollo, explicar el porqué, validar visualmente.

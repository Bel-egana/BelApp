# Auto-append de playlists al ordenar

**Fecha:** 2026-10-10
**Estado:** Diseño aprobado

## Problema

El generador de playlists actual (`generate_playlists`) **reescribe** el `.nml` de cada
(Género + Año) desde cero a partir de la carpeta que analiza. La biblioteca vieja ya está
ordenada y con sus playlists por género/año armadas en Traktor. De acá en más, Belén solo
agrega música nueva y necesita que esos tracks se **sumen** a las playlists que ya existen
(ej. `Deep House / 2026.nml`) sin pisar lo anterior ni regenerar todo.

Las playlists por género/año son **un espejo de toda la música** (para visibilidad). No hay
curaduría manual dentro de Traktor: los sets para tocar se arman en playlists aparte. Por eso
"reemplazar vs. conservar orden" no es un problema; lo que importa es **agregar lo nuevo sin
duplicar**.

## Solución elegida

**Auto-append al ordenar.** Dentro de `move_items`, mientras BelApp mueve y taguea cada track,
ya conoce su género específico, año y ruta final. Con esa info arma la lista de lo nuevo y, al
terminar, **anexa** cada track a su `.nml` de género/año (creándolo si no existe), sin duplicar,
y reporta qué playlists cambiaron para que Belén reimporte solo esas en Traktor.

Se descartó:
- **Regenerar todo desde la biblioteca:** re-escanea 17k tracks y obliga a reimportar todo.
- **Solo los tracks nuevos para arrastrar a mano:** paso manual por género, innecesario porque
  no hay curaduría que proteger.

## Arquitectura y flujo

1. **Config:** nuevo campo `playlists_dir` (carpeta fija del árbol `<Género>\<Año>.nml`). Se
   setea reusando la carpeta destino que ya se elige en el modal de "Generar playlists": al
   elegirla, se guarda en config. Si `playlists_dir` está vacío, el auto-append no corre y
   `move_items` se comporta exactamente como hoy.

2. **Interruptor:** checkbox "Actualizar playlists al ordenar" en el panel de Mantenimiento,
   tildado por defecto cuando hay `playlists_dir`. Permite desactivar el auto-append puntualmente.

3. **Durante `move_items`:** por cada track movido/tagueado se junta un dict de playlist
   `{path: ruta_final, title, artist, genre: genre_específico, label, year}` en una lista
   `pl_new`. Solo entran los tracks con **año válido** (`(19|20)\d\d`) y **género no vacío**.
   Compilados: cada track usa el género/año del álbum (mismo mecanismo).

4. **Al terminar el loop de movimiento:** si hay `playlists_dir` (y el toggle está activo),
   se agrupa `pl_new` por (género, año) y para cada grupo:
   - Se calcula la ruta `<playlists_dir>\<safe_genre>\<year>.nml` con **la misma** regla de
     carpeta/nombre que usa `generate_playlists` hoy (nombre de playlist = `str(year)`).
   - Se lee el `.nml` si existe y se llama al motor `append_tracks_to_nml`.
   - Si hubo agregados, se escribe el `.nml` y se registra el cambio.

5. **Reporte:** `move_items` devuelve `playlists_updated`: lista de
   `{name, file, added}`. La UI lo muestra en el log:
   > 🎵 Playlists actualizadas: Deep House – 2026 (+18), Techno – 2026 (+5). Reimportá solo esas.

   Si no se actualizó ninguna, no se muestra nada.

## Motor: `append_tracks_to_nml`

Función pura en `core/playlists.py`:

```
append_tracks_to_nml(existing, name, new_tracks) -> (nuevo_texto, cantidad_agregada)
```

- `existing`: texto del `.nml` actual, o `''`/`None` si no existe.
- `name`: nombre de la playlist (ej. `"2026"`), usado solo al crear de cero.
- `new_tracks`: lista de dicts `{path, title, artist, genre, label}`.

Comportamiento:

1. **Sin `existing`** → devuelve `build_traktor_playlist_nml(name, new_tracks)` y la cantidad de
   KEYs únicas.
2. **Con `existing`:**
   - Extrae las KEYs ya presentes con regex sobre `PRIMARYKEY TYPE="TRACK" KEY="..."`.
   - Filtra `new_tracks`: descarta los que su `traktor_key(path)` ya esté presente (dedup).
   - Si no queda nada nuevo → devuelve `(existing, 0)` **sin reescribir**.
   - Si hay nuevos: inserta una entrada de `COLLECTION` y una de `PLAYLIST` por cada track nuevo,
     y actualiza los dos contadores `ENTRIES` (COLLECTION y PLAYLIST) sumando la cantidad nueva.
3. **Red de seguridad:** si el formato no es reconocible (no se encuentran los contadores o los
   cierres `</COLLECTION>` / `</PLAYLIST>`), **no modifica** el archivo y lo señala (cantidad `-1`
   o similar sentinela) para que la capa de api lo reporte como "no tocada".

**Anti-duplicados:** la KEY es la ruta del archivo → identifica unívocamente al track. Reordenar
lo mismo o correr dos veces nunca duplica.

**Refactor DRY:** se extraen dos helpers de `build_traktor_playlist_nml`:
`_collection_entry(track)` y `_playlist_entry(track)`, usados por el builder y por el append.

## Componentes y responsabilidades

- `core/playlists.py`
  - `_collection_entry(track)` / `_playlist_entry(track)`: arman un bloque XML (nuevos, DRY).
  - `append_tracks_to_nml(existing, name, new_tracks)`: anexa sin duplicar (nuevo).
  - `build_traktor_playlist_nml`: sin cambios de output; usa los helpers por dentro.
- `api.py`
  - `move_items`: junta `pl_new` y, al final, llama al helper de playlists; agrega
    `playlists_updated` al resultado.
  - `_append_to_playlists(pl_new)` (nuevo helper privado): agrupa por (género, año), resuelve
    rutas, lee/escribe `.nml`, devuelve la lista de cambios.
  - lectura de `playlists_dir` desde config.
- `web/` (UI)
  - Guardar `playlists_dir` en config al elegir carpeta destino de playlists.
  - Checkbox "Actualizar playlists al ordenar".
  - Mostrar `playlists_updated` en el log de resultado.

## Manejo de errores

- `playlists_dir` inexistente o no escribible → se omite el auto-append y se avisa en el log;
  el ordenado NO falla.
- `.nml` de formato no reconocible → no se toca, se reporta como "no actualizada".
- Track sin año/género válido → se mueve y taguea igual; no entra a ninguna playlist.
- Un error anexando a UNA playlist no debe frenar las demás ni el ordenado.

## Testing (TDD)

`tests/test_playlists.py`:
- Append a `.nml` inexistente → crea completo (igual que el builder).
- Append de nuevos a existente → quedan viejos + nuevos; contadores `ENTRIES` correctos.
- Dedup: append de un track ya presente → `0` agregados, archivo sin cambios.
- Mezcla (algunos presentes, otros no) → suma solo los que faltan.
- Formato irreconocible → no modifica, devuelve sentinela.
- Helpers `_collection_entry`/`_playlist_entry` → el builder mantiene su output (154 tests verdes).

`tests/test_api.py`:
- `move_items` con `playlists_dir` → crea/actualiza los `.nml` correctos; `playlists_updated`
  con nombre + cantidad.
- Reordenar lo mismo dos veces → no duplica (segunda pasada = 0 agregados).
- Sin `playlists_dir` → ordena igual, no toca playlists (comportamiento actual intacto).
- Track sin año válido → se mueve, no entra a playlist.

## Fuera de alcance (YAGNI)

- Botón manual de "resincronizar toda la biblioteca con las playlists" (red de seguridad; se
  agrega más adelante solo si hace falta).
- Quitar de las playlists tracks borrados de la biblioteca (entradas obsoletas son raras y
  Traktor las marca como faltantes; no molesta para "visibilidad").

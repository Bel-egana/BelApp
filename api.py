"""
Puente PyWebView: la clase que el frontend JS puede invocar.

Cada método público es llamable desde JS como
`pywebview.api.metodo(args)` y devuelve datos serializables a JSON.
Toda la lógica real vive en core/ — esto es pegamento fino y testeable
(se instancia sin ventana; los diálogos nativos requieren set_window).
"""
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from core import discogs as discogs_core
from core.config import load_config, save_config
from core.paths import frozen_app_dir
from core.genres import (BEL_GENRES, BEL_GENRES_SPECIFIC, SPECIFIC_TO_BROAD,
                         format_genre, map_genre_specific)
from core.history import (build_name_index, find_duplicate, load_history,
                          save_history)
from core.labels import sellos_parecidos
from core.playlists import build_m3u8, group_by_genre_year, playlist_filename
from core.metadata import is_audio, read_id3, write_id3_tags
from core.normalizer import normalize_folder
from core.organizer import build_path
from core.parsing import parse_filename, parse_folder_name

# Datos escribibles: al lado del .exe si está congelado, si no al lado del código.
APP_DIR = frozen_app_dir(getattr(sys, 'frozen', False),
                         Path(sys.executable).parent, Path(__file__).parent)
CONFIG_PATH = APP_DIR / 'config.json'
HISTORY_PATH = APP_DIR / 'historial.json'

DEFAULT_BASE = r'D:\Bel\Música'
MAX_ITEMS = 25   # Tope de ítems por tanda (mismo criterio que la app tkinter)


class Api:
    def __init__(self, config_path=CONFIG_PATH, history_path=HISTORY_PATH):
        self._config_path = Path(config_path)
        self._history_path = Path(history_path)
        self._window = None
        self._last_move = []
        self._last_txt = None
        self._last_base = None
        self._last_dir = None   # última carpeta usada en los diálogos
        self._lbl_cache_base = None   # cache de carpetas de sello (por base)
        self._lbl_cache = None

    def set_window(self, window):
        """La ventana se inyecta después de crearla (para diálogos nativos)."""
        self._window = window

    # ── Config ────────────────────────────────────────────────────────────────
    def get_config(self):
        data = load_config(self._config_path)
        return {'base_path': data.get('base_path', DEFAULT_BASE),
                'discogs_token': data.get('discogs_token', '')}

    def save_config_values(self, base_path, discogs_token):
        return save_config(self._config_path,
                           {'base_path': base_path,
                            'discogs_token': discogs_token})

    # ── Diálogos nativos ──────────────────────────────────────────────────────
    def _dialog(self, kind, **kw):
        import webview
        try:
            dlg = {'folder': webview.FileDialog.FOLDER,
                   'open': webview.FileDialog.OPEN,
                   'save': webview.FileDialog.SAVE}[kind]
        except AttributeError:   # API vieja de pywebview
            dlg = {'folder': webview.FOLDER_DIALOG,
                   'open': webview.OPEN_DIALOG,
                   'save': webview.SAVE_DIALOG}[kind]
        return self._window.create_file_dialog(dlg, **kw)

    def _start_dir(self):
        """Carpeta donde abrir el diálogo: la última usada, si no la base (Música)."""
        if self._last_dir and Path(self._last_dir).is_dir():
            return self._last_dir
        base = load_config(self._config_path).get('base_path', DEFAULT_BASE)
        return base if Path(base).is_dir() else ''

    def pick_folder(self):
        # Arranca en la carpeta PADRE de la última usada (ej. el género, que
        # muestra la lista de sellos), para ir de un sello al siguiente sin
        # re-navegar. Si no hay última válida, arranca en la base (Música).
        base = load_config(self._config_path).get('base_path', DEFAULT_BASE)
        start = base
        if self._last_dir:
            parent = Path(self._last_dir).parent
            if parent.is_dir():
                start = str(parent)
        if not Path(start).is_dir():
            start = base
        result = self._dialog('folder', directory=start)
        if result:
            self._last_dir = result[0]
            return result[0]
        return None

    def pick_tracks(self):
        result = self._dialog(
            'open', directory=self._start_dir(), allow_multiple=True,
            file_types=('Audio (*.mp3;*.wav;*.aiff;*.flac;*.m4a)',
                        'Todos los archivos (*.*)'))
        if result:
            self._last_dir = str(Path(result[0]).parent)
            return list(result)
        return []

    def confirm(self, title, message):
        """Diálogo nativo Sí/No (window.confirm no anda en WebView2)."""
        if self._window is None:
            return True
        return bool(self._window.create_confirmation_dialog(title, message))

    def open_token_page(self):
        webbrowser.open('https://www.discogs.com/settings/developers')
        return True

    # ── Vista Buscar ──────────────────────────────────────────────────────────
    def get_genres(self):
        return list(BEL_GENRES)

    def get_genres_specific(self):
        return list(BEL_GENRES_SPECIFIC)

    def get_specific_to_broad(self):
        """Mapa género específico (12) -> carpeta (4), para que el front
        deduzca sola la carpeta a partir del género del tag."""
        return dict(SPECIFIC_TO_BROAD)

    def search_discogs(self, query, artist_fallback=''):
        """Busca en Discogs con reintento por artista. Nunca lanza: {error} en fallas."""
        token = load_config(self._config_path).get('discogs_token', '')
        if not token:
            return {'error': 'Falta el token de Discogs.'}
        fallback = ''
        if artist_fallback and artist_fallback.lower() != query.lower():
            fallback = artist_fallback
        try:
            results, used = discogs_core.search_with_fallback(
                query, token, fallback=fallback)
            return {'results': [discogs_core.parse_discogs_result(r)
                                for r in results],
                    'used_fallback': used}
        except Exception as e:
            return {'error': str(e)}

    def preview_destination(self, base, genre, label, year, name):
        return str(build_path(base, genre, label, year, name))

    def suggest_labels(self, base, label):
        """Sellos ya existentes en disco parecidos a 'label' (para avisar de
        duplicados tipo 'Set About' vs 'Set About Music'). Nunca lanza."""
        try:
            return sellos_parecidos(label, self._label_folders(base))
        except Exception:
            return []

    def _label_folders(self, base):
        """Nombres de carpetas de sello bajo base/Género/Sello (cacheado por base)."""
        base = str(base or '')
        if self._lbl_cache is not None and self._lbl_cache_base == base:
            return self._lbl_cache
        labels = set()
        p = Path(base)
        if p.is_dir():
            for genero in p.iterdir():
                if not genero.is_dir():
                    continue
                for sello in genero.iterdir():
                    if sello.is_dir() and sello.name != 'Sin Sello':
                        labels.add(sello.name)
        self._lbl_cache_base = base
        self._lbl_cache = sorted(labels)
        return self._lbl_cache

    def generate_playlists(self, base, out_dir):
        """Genera un .m3u8 por (Género tag + Año) leyendo los tags de la
        biblioteca. Las playlists son por REFERENCIA: no mueve ni copia audio.
        Devuelve un resumen o {'error': ...}."""
        try:
            base_p, out_p = Path(base), Path(out_dir)
            if not base_p.is_dir():
                return {'error': f'No existe la carpeta base: {base}'}
            out_p.mkdir(parents=True, exist_ok=True)
            tracks, sin_tag, total = [], 0, 0
            for f in base_p.rglob('*'):
                if not (f.is_file() and is_audio(f.name)):
                    continue
                total += 1
                id3 = read_id3(f)
                genre = (id3.get('genre') or '').strip()
                year = (id3.get('year') or '').strip()
                if not genre or not year:
                    sin_tag += 1
                    continue
                tracks.append({'path': str(f), 'genre': genre, 'year': year,
                               'artist': id3.get('artist', ''),
                               'title': id3.get('title', '')})
            escritas = 0
            for (genre, year), items in group_by_genre_year(tracks).items():
                (out_p / playlist_filename(genre, year)).write_text(
                    build_m3u8(items), encoding='utf-8')
                escritas += 1
            self._last_dir = str(out_p)
            return {'ok': True, 'playlists': escritas, 'tracks': len(tracks),
                    'sin_tag': sin_tag, 'total': total, 'folder': str(out_p)}
        except Exception as e:
            return {'error': str(e)}

    def open_beatport(self, query):
        webbrowser.open('https://www.beatport.com/search?q=' + quote(query))
        return True

    # ── Vista Cargar ──────────────────────────────────────────────────────────
    def _dup_index(self):
        return build_name_index(load_history(self._history_path))

    def _track_item(self, path, dup_index):
        p = Path(path)
        id3 = read_id3(p)
        parsed = parse_filename(p.name)
        dup = find_duplicate([p.name], dup_index)
        query = f"{parsed.get('artist', '')} {parsed.get('title', '')}".strip() or Path(p.name).stem
        return {'type': 'track', 'name': p.name, 'path': str(p),
                'folder_name': '', 'search_query': query,
                'name_artist': parsed.get('artist', ''),
                'name_title': parsed.get('title', ''),
                'artist': id3.get('artist') or parsed.get('artist', ''),
                'title': id3.get('title') or parsed.get('title', ''),
                'album': '',
                'genre': format_genre(id3.get('genre', '')),
                'genre_specific': map_genre_specific(id3.get('genre', '')),
                'label': id3.get('label', ''), 'year': id3.get('year', ''),
                'has_id3': bool(id3), 'n_tracks': 1,
                'is_dup': dup is not None,
                'dup_fecha': (dup or {}).get('fecha', ''),
                'dup_info': dup}

    def _album_item(self, folder, dup_index):
        fp = Path(folder)
        audio = sorted(f for f in fp.iterdir()
                       if f.is_file() and is_audio(f.name))
        if not audio:
            return None
        parsed = parse_folder_name(fp.name)
        id3 = read_id3(audio[0])
        dup = find_duplicate([f.name for f in audio], dup_index)
        query = f"{parsed.get('artist', '')} {parsed.get('album', '')}".strip() or fp.name
        return {'type': 'album', 'name': fp.name, 'path': str(fp),
                'folder_name': fp.name, 'search_query': query,
                'name_artist': parsed.get('artist', ''),
                'name_title': parsed.get('album', ''),
                'artist': id3.get('artist') or parsed.get('artist', ''),
                'title': '',
                'album': id3.get('album') or parsed.get('album', ''),
                'genre': format_genre(id3.get('genre', '')),
                'genre_specific': map_genre_specific(id3.get('genre', '')),
                'label': id3.get('label', ''), 'year': id3.get('year', ''),
                'has_id3': bool(id3), 'n_tracks': len(audio),
                'is_dup': dup is not None,
                'dup_fecha': (dup or {}).get('fecha', ''),
                'dup_info': dup}

    def load_tracks(self, paths, existing_paths, current_count):
        idx = self._dup_index()
        existing = set(existing_paths)            # rutas ya cargadas
        items, skipped, capped = [], 0, False
        for p in paths:
            if current_count + len(items) >= MAX_ITEMS:
                capped = True
                break
            key = str(Path(p))
            if not is_audio(Path(p).name):
                continue
            if key in existing:                   # mismo archivo ya cargado
                skipped += 1
                continue
            items.append(self._track_item(p, idx))
            existing.add(key)
        return {'items': items, 'skipped': skipped, 'capped': capped}

    def load_album_folder(self, path, existing_paths, current_count):
        if current_count >= MAX_ITEMS:
            return {'error': f'Llegaste al máximo de {MAX_ITEMS} ítems por tanda.'}
        key = str(Path(path))
        if key in set(existing_paths):
            return {'error': f'"{Path(path).name}" ya está cargada.'}
        item = self._album_item(path, self._dup_index())
        if item is None:
            return {'error': f'No hay archivos de audio en "{Path(path).name}".'}
        return {'item': item}

    def scan_folder(self, path, existing_paths, current_count, skip_year=False):
        """Carga los archivos sueltos (como tracks) y las subcarpetas inmediatas
        (como álbumes). Si skip_year=True, saltea las subcarpetas con nombre de
        año (ej. '2022'): son las que ya están organizadas."""
        fp = Path(path)
        if not fp.is_dir():
            return {'error': 'Carpeta inválida.'}
        idx = self._dup_index()
        existing = set(existing_paths)
        items, skipped, capped, skipped_years = [], 0, False, 0

        def full():
            return current_count + len(items) >= MAX_ITEMS

        for f in sorted(fp.iterdir()):
            if not (f.is_file() and is_audio(f.name)):
                continue
            if full():
                capped = True
                break
            if str(f) in existing:
                skipped += 1
                continue
            items.append(self._track_item(str(f), idx))
            existing.add(str(f))

        if not capped:
            for sub in sorted(fp.iterdir()):
                if not sub.is_dir():
                    continue
                if skip_year and sub.name.isdigit() and len(sub.name) == 4:
                    skipped_years += 1           # carpeta de año ya organizada
                    continue
                if full():
                    capped = True
                    break
                if str(sub) in existing:
                    skipped += 1
                    continue
                item = self._album_item(str(sub), idx)
                if item:
                    items.append(item)
                    existing.add(str(sub))

        return {'items': items, 'skipped': skipped, 'capped': capped,
                'skipped_years': skipped_years}

    # ── Vista Resultado: mover / deshacer / período ───────────────────────────
    def _txt_path(self, base_path, period):
        name = f"belapp_{(period or 'playlist').strip()}.txt"
        return Path(base_path) / name

    @staticmethod
    def _is_path_line(line):
        return len(line) > 3 and line[1:3] in (':\\', ':/')

    def _append_txt(self, base_path, period, paths):
        txt = self._txt_path(base_path, period)
        try:
            txt.parent.mkdir(parents=True, exist_ok=True)
            nuevo = not txt.exists() or txt.stat().st_size == 0
            with open(txt, 'a', encoding='utf-8') as fp:
                if nuevo:
                    fp.write(f"BelApp — Período {period}\n")
                    fp.write('─' * 60 + '\n')
                for p in paths:
                    fp.write(p + '\n')
        except Exception:
            pass
        return self.get_period_count(base_path, period)

    def get_period_count(self, base_path, period):
        txt = self._txt_path(base_path, period)
        if not txt.exists():
            return 0
        try:
            return sum(1 for ln in txt.read_text(encoding='utf-8').splitlines()
                       if self._is_path_line(ln))
        except Exception:
            return 0

    def dests_existentes(self, items, base_path):
        """Ítems cuyo destino YA existe en disco (se saltearían al mover, para no
        pisar). Sirve para avisar ANTES de mover. Para los tracks devuelve el
        tamaño del archivo nuevo y el existente, para recomendar cuál conservar
        (más grande ≈ mejor calidad). NUNCA borra nada."""
        existentes = []
        for it in items or []:
            try:
                dest = build_path(base_path, it['genre'], it['label'],
                                  it['year'], it['name'])
                if not dest.exists():
                    continue
                info = {'name': it['name']}
                src = Path(it.get('path', ''))
                if dest.is_file() and src.is_file():   # comparación solo para tracks
                    info['size_nuevo'] = src.stat().st_size
                    info['size_existente'] = dest.stat().st_size
                existentes.append(info)
            except Exception:
                continue
        return existentes

    def move_items(self, items, base_path, period=''):
        now = datetime.now().strftime('%d/%m/%Y %H:%M')
        folders, log, new_hist, txt_paths = set(), [], [], []
        moved_sources, src_parents = [], set()
        last_dir = str(base_path)
        moved_t = moved_a = errors = 0
        self._last_move = []
        self._last_txt = str(self._txt_path(base_path, period)) if period else None
        self._last_base = str(base_path)
        self._lbl_cache = None   # se crearán carpetas: invalidar cache de sellos

        def L(text, kind):
            log.append({'text': text, 'kind': kind})

        for it in items:
            nm = it['name']
            dest = build_path(base_path, it['genre'], it['label'], it['year'], nm)
            dest_dir = dest.parent
            try:
                if not dest_dir.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    folders.add(str(dest_dir))
                    L(f"📁 Carpeta creada: {dest_dir}", 'info')
                else:
                    folders.add(str(dest_dir))

                if it['type'] == 'track':
                    src = Path(it['path'])
                    if not src.exists():
                        L(f"✗ No encontrado: {nm}", 'error'); errors += 1; continue
                    if dest.exists():
                        L(f"⚠ Ya existe: {nm}", 'warn'); continue
                    shutil.move(str(src), str(dest))
                    title = it.get('title') or dest.stem
                    tag_genre = it.get('genre_specific') or it['genre']
                    ok = write_id3_tags(dest, it['artist'], title, '',
                                        it['label'], tag_genre, it['year'])
                    L(f"✓ {nm}{' [tags ✓]' if ok else ''}", 'success')
                    self._last_move.append(
                        {'type': 'file', 'src': str(src), 'dest': str(dest)})
                    new_hist.append({'fecha': now, 'artista': it['artist'] or '—',
                                     'track': title, 'genero': it['genre'],
                                     'sello': it['label'], 'año': it['year'],
                                     'destino': str(dest)})
                    txt_paths.append(str(dest))
                    moved_sources.append(it['path'])
                    src_parents.add(str(src.parent))
                    last_dir = str(dest_dir)
                    moved_t += 1
                else:
                    src_f = Path(it['path'])
                    if not src_f.exists():
                        L(f"✗ No encontrada: {nm}", 'error'); errors += 1; continue
                    if dest.exists():
                        L(f"⚠ Ya existe: {nm}", 'warn'); continue
                    shutil.move(str(src_f), str(dest))
                    self._last_move.append(
                        {'type': 'folder', 'src': str(src_f), 'dest': str(dest)})
                    tagged = total = 0
                    tag_genre = it.get('genre_specific') or it['genre']
                    for tf in sorted(dest.iterdir()):
                        if not (tf.is_file() and is_audio(tf.name)):
                            continue
                        total += 1
                        ap = parse_filename(tf.name)
                        if write_id3_tags(tf, it['artist'] or ap.get('artist', ''),
                                          ap.get('title', tf.stem), it.get('album') or nm,
                                          it['label'], tag_genre, it['year']):
                            tagged += 1
                        new_hist.append({
                            'fecha': now,
                            'artista': ap.get('artist') or it['artist'] or '—',
                            'track': ap.get('title') or tf.stem,
                            'genero': it['genre'], 'sello': it['label'],
                            'año': it['year'], 'destino': str(tf)})
                        txt_paths.append(str(tf))
                    L(f"📁 {nm} ({total} tracks) [tags {tagged}✓]", 'album')
                    moved_sources.append(it['path'])
                    src_parents.add(str(src_f.parent))
                    last_dir = str(dest_dir)
                    moved_a += 1
            except PermissionError:
                L(f"✗ Sin permisos: {nm}", 'error'); errors += 1
            except Exception as e:
                L(f"✗ Error: {e}", 'error'); errors += 1

        # Limpiar carpetas de origen que quedaron vacías (nunca la base ni raíces)
        base_norm = str(Path(base_path)).rstrip('\\/').lower()
        for d in src_parents:
            try:
                p = Path(d)
                if (p.exists() and p.is_dir() and len(p.parts) > 1
                        and str(p).rstrip('\\/').lower() != base_norm
                        and not any(p.iterdir())):
                    p.rmdir()
                    L(f"🗑 Carpeta vacía eliminada: {p}", 'info')
            except Exception:
                pass

        if new_hist:
            save_history(self._history_path,
                         load_history(self._history_path) + new_hist)
        txt_count = self._append_txt(base_path, period, txt_paths) if period else 0
        L(f"✓ Listo! {moved_t} tracks, {moved_a} albums, "
          f"{len(folders)} carpetas nuevas, {errors} errores.", 'warn')
        return {'log': log, 'moved': moved_t, 'moved_albums': moved_a,
                'errors': errors, 'new_folders': len(folders),
                'txt_count': txt_count, 'moved_sources': moved_sources,
                'open_dir': last_dir}

    def _cleanup_empty_dirs(self, start, base):
        """Elimina carpetas vacías subiendo desde 'start' hasta (sin incluir) 'base'."""
        base_norm = str(Path(base)).rstrip('\\/').lower() if base else None
        try:
            p = Path(start)
            while p.exists() and p.is_dir():
                if len(p.parts) <= 1:
                    break
                if base_norm and str(p).rstrip('\\/').lower() == base_norm:
                    break
                if any(p.iterdir()):
                    break
                parent = p.parent
                p.rmdir()
                p = parent
        except Exception:
            pass

    def _purge_records(self, dests):
        norm = [str(d).rstrip('\\/').lower() for d in dests]

        def under(p):
            p = str(p).lower()
            return any(p == d or p.startswith(d + '\\') or p.startswith(d + '/')
                       for d in norm)

        hist = [h for h in load_history(self._history_path)
                if not under(h.get('destino', ''))]
        save_history(self._history_path, hist)
        if self._last_txt and Path(self._last_txt).exists():
            txt = Path(self._last_txt)
            lines = txt.read_text(encoding='utf-8').splitlines()
            kept = [ln for ln in lines
                    if not (self._is_path_line(ln) and under(ln))]
            txt.write_text('\n'.join(kept) + '\n', encoding='utf-8')

    def undo_last_move(self):
        if not self._last_move:
            return {'restored': 0, 'skipped': 0, 'errors': 0,
                    'problems': ['No hay ningún movimiento reciente para deshacer.']}
        restored = skipped = errors = 0
        problems, undone = [], []
        for entry in reversed(self._last_move):
            src, dest = Path(entry['src']), Path(entry['dest'])
            try:
                if not dest.exists():
                    skipped += 1; problems.append(f"Ya no está: {dest.name}"); continue
                if src.exists():
                    skipped += 1; problems.append(f"El origen ya existe: {src.name}"); continue
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(src))
                undone.append(str(dest))
                restored += 1
            except Exception as e:
                errors += 1; problems.append(f"{dest.name}: {e}")
        if undone:
            self._purge_records(undone)
            for d in undone:
                self._cleanup_empty_dirs(Path(d).parent, self._last_base)
        self._last_move = []
        return {'restored': restored, 'skipped': skipped,
                'errors': errors, 'problems': problems}

    def open_in_explorer(self, path):
        """Abre el Explorador: selecciona el archivo, o abre la carpeta."""
        import subprocess
        p = Path(path)
        try:
            if p.is_file():
                subprocess.Popen(['explorer', '/select,', str(p)])
            elif p.exists():
                subprocess.Popen(['explorer', str(p)])
            else:
                subprocess.Popen(['explorer', str(p.parent)])
        except Exception:
            pass
        return True

    # ── Vista Historial ───────────────────────────────────────────────────────
    def get_history(self):
        return load_history(self._history_path)

    def delete_history_entry(self, destino):
        hist = [h for h in load_history(self._history_path)
                if h.get('destino', '') != destino]
        return save_history(self._history_path, hist)

    def clear_history(self):
        return save_history(self._history_path, [])

    def _replace_in_txts(self, base, old, new):
        """Reemplaza una ruta vieja por la nueva en cualquier belapp_*.txt."""
        try:
            for txt in Path(base).glob('belapp_*.txt'):
                lines = txt.read_text(encoding='utf-8').splitlines()
                if old in lines:
                    lines = [new if ln == old else ln for ln in lines]
                    txt.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except Exception:
            pass

    def recategorize_entry(self, old_destino, genre, label, year, clean_empty=True):
        """Corrige género/sello/año de un track ya organizado: mueve el archivo
        a la carpeta correcta, reescribe tags y actualiza historial + TXT."""
        src = Path(old_destino)
        if not src.exists():
            return {'error': 'El archivo ya no está en su ubicación registrada.'}
        base = load_config(self._config_path).get('base_path', '')
        if not base:
            return {'error': 'No hay carpeta base configurada.'}
        dest = build_path(base, genre, label, year, src.name)
        moved = dest != src
        if moved:
            if dest.exists():
                return {'error': f'Ya existe un archivo en el destino:\n{dest}'}
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

        # Actualizar la entrada en el historial + reescribir tags
        hist = load_history(self._history_path)
        artist = track = ''
        for h in hist:
            if h.get('destino') == old_destino:
                artist, track = h.get('artista', ''), h.get('track', '')
                h.update({'genero': genre, 'sello': label, 'año': year,
                          'destino': str(dest)})
        write_id3_tags(dest, artist, track, '', label, genre, year)
        save_history(self._history_path, hist)

        self._replace_in_txts(base, old_destino, str(dest))
        if clean_empty and moved:
            self._cleanup_empty_dirs(src.parent, base)
        return {'ok': True, 'dest': str(dest)}

    # ── Normalizador de géneros (mantenimiento) ───────────────────────────────
    def preview_normalize(self, folder):
        """Dry-run: reporta qué géneros se normalizarían, sin tocar nada."""
        if not folder or not Path(folder).is_dir():
            return {'error': 'Carpeta inválida.'}
        return normalize_folder(folder, dry_run=True)

    def apply_normalize(self, folder):
        """Aplica la normalización: reescribe los tags de género."""
        if not folder or not Path(folder).is_dir():
            return {'error': 'Carpeta inválida.'}
        return normalize_folder(folder, dry_run=False)

    def review_folder_genres(self, folder):
        """Lista TODOS los tracks de audio de la carpeta con su género actual y
        el sugerido (map_genre_specific; '' si no tiene género o no mapea).
        Para la revisión/edición manual, track por track."""
        if not folder or not Path(folder).is_dir():
            return {'error': 'Carpeta inválida.'}
        tracks, con_sug, sin_genero = [], 0, 0
        for f in Path(folder).rglob('*'):
            if not (f.is_file() and is_audio(f.name)):
                continue
            g = (read_id3(f).get('genre') or '').strip()
            sug = map_genre_specific(g)
            if not g:
                sin_genero += 1
            if sug:
                con_sug += 1
            tracks.append({'path': str(f), 'current': g, 'suggested': sug})
        tracks.sort(key=lambda t: t['path'])
        return {'tracks': tracks, 'total': len(tracks),
                'con_sugerencia': con_sug, 'sin_genero': sin_genero}

    def apply_normalize_selected(self, items):
        """Aplica SOLO los cambios de género elegidos en la revisión.

        items = [{'path': str, 'new': str}]. Reescribe únicamente el tag de
        género (con el destino elegido, que puede diferir del sugerido),
        preservando artista/título/álbum/sello/año. No mueve archivos.
        Devuelve {'applied': n, 'errors': [{path, error}]}."""
        applied, errors = 0, []
        for it in items or []:
            path = it.get('path') or ''
            new = (it.get('new') or '').strip()
            if not path or not new:
                continue
            try:
                f = Path(path)
                tags = read_id3(f)
                write_id3_tags(f, tags.get('artist', ''), tags.get('title', ''),
                               tags.get('album', ''), tags.get('label', ''),
                               new, tags.get('year', ''))
                applied += 1
            except Exception as e:
                errors.append({'path': path, 'error': str(e)})
        return {'applied': applied, 'errors': errors}

    def _write_history_xlsx(self, path, hist):
        """Escribe el historial como Excel prolijo (encabezados, anchos, fila fija)."""
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        ws = wb.active
        ws.title = 'Historial'
        ws.append(['Fecha', 'Artista', 'Track', 'Género', 'Sello', 'Año', 'Destino'])
        for h in hist:
            ws.append([h.get('fecha', ''), h.get('artista', ''), h.get('track', ''),
                       h.get('genero', ''), h.get('sello', ''), h.get('año', ''),
                       h.get('destino', '')])
        for i, w in enumerate([16, 24, 34, 24, 18, 7, 60], start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = 'A2'
        wb.save(path)

    def export_history(self):
        hist = load_history(self._history_path)
        if not hist:
            return {'error': 'No hay historial para exportar.'}
        result = self._dialog('save', save_filename='belapp_historial.xlsx',
                              file_types=('Excel (*.xlsx)',))
        if not result:
            return None
        path = result if isinstance(result, str) else result[0]
        if not path.lower().endswith('.xlsx'):
            path += '.xlsx'
        try:
            self._write_history_xlsx(path, hist)
            return {'path': path}
        except Exception as e:
            return {'error': str(e)}

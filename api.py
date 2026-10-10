"""
Puente PyWebView: la clase que el frontend JS puede invocar.

Cada método público es llamable desde JS como
`pywebview.api.metodo(args)` y devuelve datos serializables a JSON.
Toda la lógica real vive en core/ — esto es pegamento fino y testeable
(se instancia sin ventana; los diálogos nativos requieren set_window).
"""
import json
import re
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
from core.history import (build_disk_index, build_name_index, find_disk_duplicate,
                          find_disk_duplicates_all, find_duplicate, load_history,
                          normalize_name, save_history)
from core.labels import sellos_parecidos
from core.playlists import (append_tracks_to_nml, build_traktor_playlist_nml,
                            group_by_genre_year)
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
MAX_ITEMS = 100   # Tope de ítems por tanda (permite cargar muchos EP/Album juntos)

# Carpetas que NUNCA cuentan como duplicado (aunque estén dentro de la base):
# son backups/copias que no forman parte de la biblioteca ordenada. Se suman a
# lo que haya en config['dedup_ignore']. Match por subcadena, sin mayúsculas.
DEFAULT_DEDUP_IGNORE = ['Traktor playlist backup']


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
        self._disk_idx_base = None    # cache del índice de duplicados en disco
        self._disk_idx = None

    def set_window(self, window):
        """La ventana se inyecta después de crearla (para diálogos nativos)."""
        self._window = window

    # ── Config ────────────────────────────────────────────────────────────────
    def get_config(self):
        data = load_config(self._config_path)
        return {'base_path': data.get('base_path', DEFAULT_BASE),
                'discogs_token': data.get('discogs_token', ''),
                'dedup_ignore': data.get('dedup_ignore', [])}

    def save_config_values(self, base_path, discogs_token, ignore_dirs=None):
        # Merge: preserva otras claves (ej. tour_visto) al guardar base/token.
        data = load_config(self._config_path)
        data['base_path'] = base_path
        data['discogs_token'] = discogs_token
        if ignore_dirs is not None:   # None = no tocar; string = actualizar
            data['dedup_ignore'] = [s.strip() for s in ignore_dirs.split(',')
                                    if s.strip()]
        self._invalidate_disk_index()   # cambió base o ignorados: re-escanear
        return save_config(self._config_path, data)

    def tour_visto(self):
        """¿Ya se mostró la guía de bienvenida? (para mostrarla solo la 1ª vez)."""
        return bool(load_config(self._config_path).get('tour_visto'))

    def marcar_tour_visto(self):
        data = load_config(self._config_path)
        data['tour_visto'] = True
        return save_config(self._config_path, data)

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

    def pick_folders(self):
        """Como pick_folder pero permite elegir VARIAS carpetas a la vez
        (para cargar muchos EP/Album de una). Devuelve una lista de rutas."""
        base = load_config(self._config_path).get('base_path', DEFAULT_BASE)
        start = base
        if self._last_dir:
            parent = Path(self._last_dir).parent
            if parent.is_dir():
                start = str(parent)
        if not Path(start).is_dir():
            start = base
        result = self._dialog('folder', directory=start, allow_multiple=True)
        if result:
            self._last_dir = result[0]
            return list(result)
        return []

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

    def generate_playlists(self, source, out_dir, genre_filter='', year_filter=''):
        """Genera un .m3u8 por (Género + Año) por REFERENCIA (no mueve audio).
        'source' es la carpeta a analizar (una sola, no toda la biblioteca).
        El GÉNERO sale del tag (por eso arma por género específico, ej. Deep
        House). El AÑO sale del tag y, si falta, de una subcarpeta de 4 dígitos
        en la ruta (ej. .../2022/...). genre_filter/year_filter (vacío = todos).
        Devuelve un resumen o {'error': ...}."""
        try:
            src_p, out_p = Path(source), Path(out_dir)
            if not src_p.is_dir():
                return {'error': f'No existe la carpeta a analizar: {source}'}
            out_p.mkdir(parents=True, exist_ok=True)
            # "todos"/"todas"/"all"/vacío = sin filtro (evita tomar la palabra literal)
            def _es_todos(s):
                return s.strip().lower() in (
                    '', 'todos', 'todas', 'todo', 'all',
                    'todos los años', 'todos los anios', 'todos los anos',
                    'todos los géneros', 'todos los generos')
            gf = '' if _es_todos(genre_filter or '') else (genre_filter or '').strip().lower()
            yf = '' if _es_todos(year_filter or '') else (year_filter or '').strip()
            tracks, afuera, total, filtrados = [], [], 0, 0
            for f in src_p.rglob('*'):
                if not (f.is_file() and is_audio(f.name)):
                    continue
                total += 1
                id3 = read_id3(f)
                genre = (id3.get('genre') or '').strip()
                year = (id3.get('year') or '').strip()
                # Año válido = 19xx/20xx. Si el tag trae basura (ej. "0202") o
                # está vacío, lo descartamos y probamos con la carpeta de año.
                if not re.fullmatch(r'(19|20)\d\d', year):
                    year = ''
                    for part in f.parts:
                        if re.fullmatch(r'(19|20)\d\d', part):
                            year = part
                            break
                if not genre or not year:
                    falta = 'sin género y año' if (not genre and not year) else \
                            ('sin género' if not genre else 'sin año')
                    afuera.append((falta, f.name))
                    continue
                if (gf and genre.lower() != gf) or (yf and year != yf):
                    filtrados += 1
                    continue
                tracks.append({'path': str(f), 'genre': genre, 'year': year,
                               'artist': id3.get('artist', ''),
                               'title': id3.get('title', '')})
            if not tracks:
                cual = []
                if gf:
                    cual.append(f'género "{genre_filter}"')
                if yf:
                    cual.append(f'año {yf}')
                detalle = ' y '.join(cual) if cual else 'esos filtros'
                return {'error': f'No hay tracks con {detalle} (revisá el '
                                 f'filtro o que los tags estén completos).'}
            # Estructura: una SUBCARPETA por género, y adentro un .nml por año
            # nombrado solo con el año (2013.nml). Así en Traktor hacés
            # "Import Playlist Directory" sobre la carpeta del género y te entran
            # todos los años de una, nombrados por año.
            escritas, generos = 0, set()
            for (genre, year), items in group_by_genre_year(tracks).items():
                safe = re.sub(r'[<>:"/\\|?*]', '_', genre).strip() or 'Sin género'
                gdir = out_p / safe
                gdir.mkdir(parents=True, exist_ok=True)
                (gdir / f'{year}.nml').write_text(
                    build_traktor_playlist_nml(str(year), items), encoding='utf-8')
                escritas += 1
                generos.add(safe)

            # Reporte de los tracks que quedaron AFUERA (sin género/año).
            sin_tag_file = ''
            if afuera:
                lines = [f'{falta:16}  {name}' for falta, name
                         in sorted(afuera, key=lambda x: (x[0], x[1].lower()))]
                rp = out_p / '_tracks que NO entraron (sin tag).txt'
                rp.write_text(
                    'TRACKS QUE NO ENTRARON EN NINGUNA PLAYLIST\n'
                    '(les falta el tag de género y/o año — completalos y volvé a generar)\n'
                    + '=' * 64 + f'\n\n{len(afuera)} tracks:\n\n' + '\n'.join(lines) + '\n',
                    encoding='utf-8')
                sin_tag_file = rp.name

            # Log de playlists generadas + detectar si ya se había hecho igual.
            log = self.get_playlists_log()
            prev = [e for e in log
                    if e.get('source') == str(src_p)
                    and e.get('genre', '') == (genre_filter or '')
                    and e.get('year', '') == (year_filter or '')]
            ya_fecha = prev[-1]['fecha'] if prev else ''
            log.append({'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
                        'source': str(src_p), 'dest': str(out_p),
                        'genre': genre_filter or '', 'year': year_filter or '',
                        'playlists': escritas, 'tracks': len(tracks),
                        'sin_tag': len(afuera)})
            try:
                self._pl_log_path().write_text(
                    json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                pass

            # Recordar esta carpeta para el auto-append al ordenar.
            try:
                cfg_pl = load_config(self._config_path)
                cfg_pl['playlists_dir'] = str(out_p)
                save_config(self._config_path, cfg_pl)
            except Exception:
                pass

            self._last_dir = str(out_p)
            return {'ok': True, 'playlists': escritas, 'tracks': len(tracks),
                    'generos': len(generos), 'sin_tag': len(afuera),
                    'sin_tag_file': sin_tag_file, 'ya_fecha': ya_fecha,
                    'total': total, 'folder': str(out_p)}
        except Exception as e:
            return {'error': str(e)}

    def _pl_log_path(self):
        return self._config_path.parent / 'playlists_generadas.json'

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

    def get_playlists_log(self):
        """Lista de playlists generadas (para verlas desde Historial)."""
        p = self._pl_log_path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    def open_beatport(self, query):
        webbrowser.open('https://www.beatport.com/search?q=' + quote(query))
        return True

    # ── Vista Cargar ──────────────────────────────────────────────────────────
    def _disk_dup_index(self):
        """Índice {nombre: [rutas]} de los archivos que YA están en la biblioteca
        (base_path), salteando las carpetas a ignorar. Cacheado por (base,
        ignorados): escanear 18k+ archivos es caro, así que solo se reconstruye
        si cambia la carpeta base, la lista de ignorados, o después de mover."""
        cfg = self.get_config()
        key = (cfg['base_path'], self._dedup_ignore(cfg))
        if self._disk_idx is not None and self._disk_idx_base == key:
            return self._disk_idx
        self._disk_idx = build_disk_index(
            key[0], lambda n: is_audio(Path(n).name), key[1])
        self._disk_idx_base = key
        return self._disk_idx

    def _dedup_ignore(self, cfg=None):
        """Carpetas a ignorar en duplicados: las fijas por defecto (backup de
        Traktor) + las que haya en config. Devuelve una tupla (para cachear)."""
        cfg = cfg or self.get_config()
        return tuple(DEFAULT_DEDUP_IGNORE) + tuple(cfg.get('dedup_ignore', []))

    def _invalidate_disk_index(self):
        """La biblioteca cambió (mover/deshacer/recategorizar): forzar re-escaneo."""
        self._disk_idx = None
        self._disk_idx_base = None

    def _dup_index(self):
        return build_name_index(load_history(self._history_path))

    def disk_index_listo(self):
        """¿El índice de duplicados en disco ya está en caché para la carpeta
        base actual? Sirve para avisar 'Analizando música…' solo la primera vez
        que hay que escanear la biblioteca (después queda cacheado)."""
        cfg = self.get_config()
        return (self._disk_idx is not None
                and self._disk_idx_base == (cfg['base_path'],
                                            self._dedup_ignore(cfg)))

    def _dup_real(self, dup, src_path=None):
        """Un duplicado solo cuenta si el archivo que YA existe sigue en disco.
        Si lo borraste, la entrada quedó obsoleta y NO marca dup. Y si el 'dup'
        es el MISMO archivo que estás cargando (re-escaneo de una carpeta ya
        ordenada), tampoco: no es un duplicado, es él mismo."""
        if not (dup and dup.get('destino')):
            return None
        dest = Path(dup['destino'])
        if not dest.exists():
            return None
        if src_path is not None:
            try:
                if dest.resolve() == Path(src_path).resolve():
                    return None
            except OSError:
                pass
        return dup

    def _track_item(self, path, dup_index):
        p = Path(path)
        id3 = read_id3(p)
        parsed = parse_filename(p.name)
        dup = self._dup_real(find_duplicate([p.name], dup_index), p)
        if dup is None:   # no está en historial: ¿existe físicamente en la biblioteca?
            dup = find_disk_duplicate([p.name], self._disk_dup_index(), [p])
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
        names = [f.name for f in audio]
        dup = self._dup_real(find_duplicate(names, dup_index))
        if dup:  # no marcar como dup si el match es un archivo del propio álbum
            try:
                if Path(dup['destino']).resolve() in {a.resolve() for a in audio}:
                    dup = None
            except OSError:
                pass
        dup_all = []
        if dup is None:   # ¿alguno de los tracks ya existe físicamente en la biblioteca?
            dup_all = find_disk_duplicates_all(names, self._disk_dup_index(), audio)
            if dup_all:
                dup = {'destino': dup_all[0]['destino'], 'fecha': '',
                       'origen': 'biblioteca'}
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
                'dup_info': dup,
                'dup_all': dup_all}

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

    def load_album_folders(self, paths, existing_paths, current_count):
        """Carga VARIAS carpetas EP/Album de una. Respeta el tope por tanda,
        saltea las ya cargadas y reporta las que no tienen audio."""
        idx = self._dup_index()
        existing = set(existing_paths)
        items, skipped, capped, no_audio = [], 0, False, []
        for p in paths:
            if current_count + len(items) >= MAX_ITEMS:
                capped = True
                break
            key = str(Path(p))
            if key in existing:
                skipped += 1
                continue
            item = self._album_item(p, idx)
            if item is None:
                no_audio.append(Path(p).name)
                continue
            items.append(item)
            existing.add(key)
        return {'items': items, 'skipped': skipped, 'capped': capped,
                'no_audio': no_audio}

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

    def tamano_archivos(self, path_a, path_b):
        """Tamaños en bytes de dos archivos, para comparar calidad. -1 si no se
        encuentra. Si un path es una CARPETA (ítem EP/Album), busca adentro el
        audio que coincide por nombre con el otro (o el único si hay uno solo),
        así la comparación también funciona con álbumes. No toca nada."""
        def sz(p, match_name=None):
            try:
                pp = Path(p)
                if pp.is_file():
                    return pp.stat().st_size
                if pp.is_dir():
                    audio = [f for f in pp.iterdir()
                             if f.is_file() and is_audio(f.name)]
                    if match_name:
                        key = normalize_name(Path(match_name).stem)
                        for f in audio:
                            if normalize_name(f.stem) == key:
                                return f.stat().st_size
                    if len(audio) == 1:      # EP de 1 track: usar ese
                        return audio[0].stat().st_size
                return -1
            except OSError:
                return -1
        return {'a': sz(path_a, path_b), 'b': sz(path_b, path_a)}

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
                        # Artista de CADA archivo si el nombre es "Artista - Título"
                        # real (clave en compilados); si no, el del campo.
                        tf_artist = ap['artist'] if ap.get('title') else it['artist']
                        if write_id3_tags(tf, tf_artist,
                                          ap.get('title', tf.stem), it.get('album') or nm,
                                          it['label'], tag_genre, it['year']):
                            tagged += 1
                        new_hist.append({
                            'fecha': now,
                            'artista': tf_artist or '—',
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
        self._invalidate_disk_index()   # la biblioteca cambió: re-escanear la próxima
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
            self._invalidate_disk_index()   # se sacaron archivos de la biblioteca
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
        if moved:
            self._invalidate_disk_index()   # el archivo cambió de lugar en la biblioteca
            if clean_empty:
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

    def review_folder_years(self, folder):
        """Lista los tracks de la carpeta con su AÑO actual (vacío si falta o es
        inválido) y un sugerido (de una subcarpeta de año en la ruta). Para
        completar años en lote, sin ir uno por uno."""
        if not folder or not Path(folder).is_dir():
            return {'error': 'Carpeta inválida.'}
        tracks, sin_anio = [], 0
        for f in Path(folder).rglob('*'):
            if not (f.is_file() and is_audio(f.name)):
                continue
            y = (read_id3(f).get('year') or '').strip()
            if not re.fullmatch(r'(19|20)\d\d', y):   # año inválido/basura -> vacío
                y = ''
            sug = ''
            if not y:
                sin_anio += 1
                for part in f.parts:                  # ¿carpeta de año en la ruta?
                    if re.fullmatch(r'(19|20)\d\d', part):
                        sug = part
                        break
            tracks.append({'path': str(f), 'current': y, 'suggested': sug})
        tracks.sort(key=lambda t: t['path'])
        return {'tracks': tracks, 'total': len(tracks), 'sin_anio': sin_anio}

    def apply_years_selected(self, items):
        """Escribe el AÑO elegido en cada track (items=[{path, year}]),
        preservando artista/título/álbum/sello/género. Solo acepta 19xx/20xx."""
        applied, errors = 0, []
        for it in items or []:
            path = it.get('path') or ''
            year = (it.get('year') or '').strip()
            if not path:
                continue
            if not re.fullmatch(r'(19|20)\d\d', year):
                errors.append({'path': Path(path).name,
                               'error': f'año inválido: "{year}"'})
                continue
            try:
                f = Path(path)
                tags = read_id3(f)
                ok = write_id3_tags(f, tags.get('artist', ''), tags.get('title', ''),
                                    tags.get('album', ''), tags.get('label', ''),
                                    tags.get('genre', ''), year)
                if ok:
                    applied += 1
                else:
                    errors.append({'path': f.name, 'error': 'no se pudo escribir'})
            except Exception as e:
                errors.append({'path': Path(path).name, 'error': str(e)})
        return {'applied': applied, 'errors': errors}

    def buscar_duplicados_carpeta(self, folder):
        """Busca tracks de la carpeta que tienen OTRA copia (en la misma carpeta
        o en tu biblioteca). Escribe un reporte .txt con las rutas y el tamaño
        de cada copia (para elegir cuál conservar). NO borra ni mueve nada."""
        from core.history import normalize_name
        fp = Path(folder)
        if not fp.is_dir():
            return {'error': 'Carpeta inválida.'}

        disk = self._disk_dup_index()            # biblioteca (ignora backups)
        carpeta_idx = {}
        for f in fp.rglob('*'):
            if f.is_file() and is_audio(f.name):
                k = normalize_name(f.stem)
                if k:
                    carpeta_idx.setdefault(k, []).append(f)

        def mb(b):
            return b / 1048576

        grupos = []
        for key, en_carpeta in carpeta_idx.items():
            rutas = {}                            # ruta_resuelta -> Path (únicas)
            for p in list(en_carpeta) + [Path(x) for x in disk.get(key, [])]:
                try:
                    if p.is_file():
                        rutas[str(p.resolve()).lower()] = p
                except OSError:
                    pass
            if len(rutas) < 2:
                continue
            copias = []
            for p in rutas.values():
                try:
                    size = p.stat().st_size
                except OSError:
                    size = -1
                copias.append((size, p))
            copias.sort(key=lambda x: -x[0])
            grupos.append((en_carpeta[0].name, copias))
        grupos.sort(key=lambda g: g[0].lower())

        # Reporte .txt en la carpeta
        report_file = ''
        if grupos:
            L = [f'DUPLICADOS ENCONTRADOS EN: {fp}',
                 '(tracks con más de una copia — en esta carpeta o en tu biblioteca)',
                 '=' * 66, '', f'{len(grupos)} grupos:', '']
            for i, (nombre, copias) in enumerate(grupos, 1):
                L.append(f'{i}. {nombre}')
                mayor = copias[0][0]
                for size, p in copias:
                    L.append(f'   [{mb(size):6.1f} MB]  {p}')
                # recomendación por tamaño (tolerancia 100KB / 1%)
                menor = copias[-1][0]
                if mayor > 0 and (mayor - menor) <= max(102400, 0.01 * mayor):
                    L.append('   → prácticamente idénticos: borrá cualquiera.')
                else:
                    L.append(f'   → conservá el más grande ({mb(mayor):.1f} MB), borrá el/los más chicos.')
                L.append('')
            rp = fp / '_duplicados encontrados.txt'
            rp.write_text('\n'.join(L) + '\n', encoding='utf-8')
            report_file = rp.name

        return {'grupos': len(grupos), 'report_file': report_file,
                'folder': str(fp)}

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

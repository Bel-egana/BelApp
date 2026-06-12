"""
Puente PyWebView: la clase que el frontend JS puede invocar.

Cada método público es llamable desde JS como
`pywebview.api.metodo(args)` y devuelve datos serializables a JSON.
Toda la lógica real vive en core/ — esto es pegamento fino y testeable
(se instancia sin ventana; los diálogos nativos requieren set_window).
"""
import webbrowser
from pathlib import Path

from core.config import load_config, save_config
from core.genres import format_genre
from core.history import build_name_index, find_duplicate, load_history
from core.metadata import is_audio, read_id3
from core.parsing import parse_filename, parse_folder_name

APP_DIR = Path(__file__).parent
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

    def pick_folder(self):
        result = self._dialog('folder')
        return result[0] if result else None

    def pick_tracks(self):
        result = self._dialog(
            'open', allow_multiple=True,
            file_types=('Audio (*.mp3;*.wav;*.aiff;*.flac;*.m4a)',
                        'Todos los archivos (*.*)'))
        return list(result) if result else []

    def confirm(self, title, message):
        """Diálogo nativo Sí/No (window.confirm no anda en WebView2)."""
        if self._window is None:
            return True
        return bool(self._window.create_confirmation_dialog(title, message))

    def open_token_page(self):
        webbrowser.open('https://www.discogs.com/settings/developers')
        return True

    # ── Vista Cargar ──────────────────────────────────────────────────────────
    def _dup_index(self):
        return build_name_index(load_history(self._history_path))

    def _track_item(self, path, dup_index):
        p = Path(path)
        id3 = read_id3(p)
        parsed = parse_filename(p.name)
        dup = find_duplicate([p.name], dup_index)
        return {'type': 'track', 'name': p.name, 'path': str(p),
                'folder_name': '',
                'artist': id3.get('artist') or parsed.get('artist', ''),
                'title': id3.get('title') or parsed.get('title', ''),
                'album': '',
                'genre': format_genre(id3.get('genre', '')),
                'label': id3.get('label', ''), 'year': id3.get('year', ''),
                'has_id3': bool(id3), 'n_tracks': 1,
                'is_dup': dup is not None,
                'dup_fecha': (dup or {}).get('fecha', '')}

    def _album_item(self, folder, dup_index):
        fp = Path(folder)
        audio = sorted(f for f in fp.iterdir()
                       if f.is_file() and is_audio(f.name))
        if not audio:
            return None
        parsed = parse_folder_name(fp.name)
        id3 = read_id3(audio[0])
        dup = find_duplicate([f.name for f in audio], dup_index)
        return {'type': 'album', 'name': fp.name, 'path': str(fp),
                'folder_name': fp.name,
                'artist': id3.get('artist') or parsed.get('artist', ''),
                'title': '',
                'album': id3.get('album') or parsed.get('album', ''),
                'genre': format_genre(id3.get('genre', '')),
                'label': id3.get('label', ''), 'year': id3.get('year', ''),
                'has_id3': bool(id3), 'n_tracks': len(audio),
                'is_dup': dup is not None,
                'dup_fecha': (dup or {}).get('fecha', '')}

    def load_tracks(self, paths, existing_names, current_count):
        idx = self._dup_index()
        existing = set(existing_names)
        items, skipped, capped = [], 0, False
        for p in paths:
            if current_count + len(items) >= MAX_ITEMS:
                capped = True
                break
            name = Path(p).name
            if not is_audio(name):
                continue
            if name in existing:
                skipped += 1
                continue
            items.append(self._track_item(p, idx))
            existing.add(name)
        return {'items': items, 'skipped': skipped, 'capped': capped}

    def load_album_folder(self, path, existing_names, current_count):
        if current_count >= MAX_ITEMS:
            return {'error': f'Llegaste al máximo de {MAX_ITEMS} ítems por tanda.'}
        name = Path(path).name
        if name in existing_names:
            return {'error': f'"{name}" ya está cargada.'}
        item = self._album_item(path, self._dup_index())
        if item is None:
            return {'error': f'No hay archivos de audio en "{name}".'}
        return {'item': item}

    def scan_folder(self, path, existing_names, current_count):
        fp = Path(path)
        if not fp.is_dir():
            return {'error': 'Carpeta inválida.'}
        idx = self._dup_index()
        existing = set(existing_names)
        items, skipped, capped = [], 0, False

        def full():
            return current_count + len(items) >= MAX_ITEMS

        for f in sorted(fp.iterdir()):
            if not (f.is_file() and is_audio(f.name)):
                continue
            if full():
                capped = True
                break
            if f.name in existing:
                skipped += 1
                continue
            items.append(self._track_item(str(f), idx))
            existing.add(f.name)

        if not capped:
            for sub in sorted(fp.iterdir()):
                if not sub.is_dir():
                    continue
                if full():
                    capped = True
                    break
                if sub.name in existing:
                    skipped += 1
                    continue
                item = self._album_item(str(sub), idx)
                if item:
                    items.append(item)
                    existing.add(sub.name)

        return {'items': items, 'skipped': skipped, 'capped': capped}

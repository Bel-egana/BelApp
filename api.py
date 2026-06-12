"""
Puente PyWebView: la clase que el frontend JS puede invocar.

Cada método público es llamable desde JS como
`pywebview.api.metodo(args)` y devuelve datos serializables a JSON.
Toda la lógica real vive en core/ — esto es pegamento fino y testeable
(se instancia sin ventana; los diálogos nativos requieren set_window).
"""
from pathlib import Path

from core.config import load_config, save_config

APP_DIR = Path(__file__).parent
CONFIG_PATH = APP_DIR / 'config.json'
HISTORY_PATH = APP_DIR / 'historial.json'

DEFAULT_BASE = r'D:\Bel\Música'


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

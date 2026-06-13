"""
BelApp — Music Organizer (interfaz web-style).
Punto de entrada: abre la ventana PyWebView sobre web/index.html.
Correr:  python main.py
"""
from pathlib import Path

import webview

from api import Api

BASE = Path(__file__).parent

if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        'BelApp — Music Organizer',
        str(BASE / 'web' / 'index.html'),
        js_api=api,
        width=1100, height=700, min_size=(860, 560),
        background_color='#0c0c10')
    api.set_window(window)

    def _on_start():
        try:
            window.maximize()
        except Exception:
            pass

    webview.start(_on_start)

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
        width=1200, height=760, min_size=(980, 620),
        background_color='#0c0c10')
    api.set_window(window)
    webview.start()

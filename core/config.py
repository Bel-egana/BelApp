"""
Persistencia de configuración (config.json): token de Discogs y carpeta base.

Funciones puras respecto de la app: reciben el Path del archivo, devuelven
datos. Toleran archivo inexistente o corrupto devolviendo un dict vacío.
"""
import json


def load_config(path):
    """Lee el JSON de config. Devuelve {} si no existe, está corrupto o no es dict."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_config(path, data):
    """Guarda el dict como JSON legible. Devuelve True si pudo escribir."""
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding='utf-8')
        return True
    except Exception:
        return False

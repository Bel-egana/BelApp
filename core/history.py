"""
Historial persistente (historial.json) y detección de duplicados.

La detección compara NOMBRES DE ARCHIVO normalizados (minúsculas, solo
alfanumérico): tolera diferencias de espacios, guiones y mayúsculas, y es
independiente de en qué carpeta quedó el archivo.
"""
import json
import re
from pathlib import Path


# Conectores de artistas que ignoramos al comparar: son ruido, no identifican
# el track. Así 'A & B', 'B vs A' y 'A feat B' cuentan como lo mismo.
_CONECTORES = {'vs', 'versus', 'feat', 'featuring', 'ft', 'and', 'pres', 'presents'}


def normalize_name(s):
    """Normaliza un nombre para comparar: palabras alfanuméricas en minúsculas,
    ORDENADAS y sin conectores de artistas. Así el orden no importa y
    'Liquid Soul & Vini Vici' coincide con 'Vini Vici vs Liquid Soul'."""
    palabras = [w for w in re.findall(r'[a-z0-9]+', str(s).lower())
                if w not in _CONECTORES]
    return ''.join(sorted(palabras))


def build_name_index(history):
    """Dict {nombre_normalizado: entrada} de todo lo que está en el historial."""
    idx = {}
    for h in history:
        dest = h.get('destino', '')
        if not dest:
            continue
        key = normalize_name(Path(dest).stem)
        if key:
            idx.setdefault(key, h)
    return idx


def find_duplicate(filenames, index):
    """Devuelve la entrada del historial que coincide con alguno de los
    nombres de archivo dados, o None."""
    for name in filenames:
        key = normalize_name(Path(name).stem)
        if key and key in index:
            return index[key]
    return None


def load_history(path):
    """Lee el historial. Devuelve [] si no existe, está corrupto o no es lista."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def save_history(path, entries):
    """Guarda el historial como JSON legible. Devuelve True si pudo."""
    try:
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2),
                        encoding='utf-8')
        return True
    except Exception:
        return False

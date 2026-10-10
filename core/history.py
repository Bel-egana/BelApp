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


def build_disk_index(base_path, is_audio_fn, ignore=()):
    """Índice {nombre_normalizado: [rutas]} de los archivos de audio que YA
    están físicamente en la biblioteca (base_path, recursivo).

    Permite avisar de un duplicado desde la primera pantalla aunque el track
    no esté en el historial (ej. ordenado a mano, o antes de usar la app).
    Guarda TODAS las rutas de cada nombre: puede haber dos copias del mismo
    tema (una sin ordenar y otra ya ordenada) y hay que poder ver la otra.

    'ignore' es una lista de textos: cualquier archivo cuya ruta los contenga
    (sin distinguir mayúsculas) NO se cuenta. Sirve para excluir carpetas como
    un backup de playlists de Traktor que vive adentro de la biblioteca."""
    idx = {}
    base = Path(base_path)
    if not base.is_dir():
        return idx
    ign = [s.lower() for s in ignore if s]
    for f in base.rglob('*'):
        try:
            if f.is_file() and is_audio_fn(f.name):
                p = str(f)
                if ign and any(s in p.lower() for s in ign):
                    continue
                key = normalize_name(f.stem)
                if key:
                    idx.setdefault(key, []).append(p)
        except OSError:
            continue
    return idx


def find_disk_duplicate(filenames, disk_index, exclude_paths=()):
    """Devuelve {'destino','fecha','origen'} de un archivo YA en la biblioteca
    que coincide por nombre y es DISTINTO a los que se están cargando
    (exclude_paths). Así, si hay dos copias del mismo tema (una sin ordenar y
    otra ordenada), detecta la ordenada aunque estemos cargando la otra."""
    excl = set()
    for e in exclude_paths:
        try:
            excl.add(Path(e).resolve())
        except OSError:
            pass
    for name in filenames:
        key = normalize_name(Path(name).stem)
        for dest in disk_index.get(key, []):
            p = Path(dest)
            try:
                if not p.exists():
                    continue
                if p.resolve() in excl:
                    continue      # es uno de los que estamos cargando: no cuenta
            except OSError:
                continue
            return {'destino': dest, 'fecha': '', 'origen': 'biblioteca'}
    return None


def find_disk_duplicates_all(filenames, disk_index, exclude_paths=()):
    """Como find_disk_duplicate, pero devuelve TODOS los tracks que ya están en
    la biblioteca (uno por filename que coincida), para poder listar de una vez
    todos los duplicados de un compilado. Cada item: {'nombre','destino','origen'}."""
    excl = set()
    for e in exclude_paths:
        try:
            excl.add(Path(e).resolve())
        except OSError:
            pass
    out = []
    for name in filenames:
        key = normalize_name(Path(name).stem)
        for dest in disk_index.get(key, []):
            p = Path(dest)
            try:
                if not p.exists():
                    continue
                if p.resolve() in excl:
                    continue
            except OSError:
                continue
            out.append({'nombre': name, 'destino': dest, 'origen': 'biblioteca'})
            break   # con una coincidencia por track alcanza
    return out


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

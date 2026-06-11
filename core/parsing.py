"""
Funciones puras de parsing de nombres de archivos y carpetas.

"Puras" = no dependen de la UI, ni tocan el disco, ni la red: reciben
texto y devuelven datos. Por eso son fáciles de testear de forma
automática (ver tests/test_parsing.py).
"""
import re
from pathlib import Path


def parse_filename(name):
    """Separa 'Artista - Título.ext' en {'artist', 'title'}.

    - Saca la extensión del archivo.
    - Tolera un prefijo entre corchetes, ej. '[Sello] Artista - Título'.
    - Si no hay ' - ', devuelve todo como artista y el título vacío.
    """
    stem = re.sub(r'^\[[^\]]+\]\s*', '', Path(name).stem)
    i = stem.find(' - ')
    if i > 0:
        return {'artist': stem[:i].strip(), 'title': stem[i + 3:].strip()}
    return {'artist': stem.strip(), 'title': ''}


def parse_folder_name(folder):
    """Separa 'Artista - Album (2020)' en {'artist', 'album'}.

    - Saca el año entre paréntesis al final, ej. ' (2020)'.
    - Si no hay ' - ', devuelve el nombre completo como álbum.
    """
    clean = re.sub(r'\s*\(\d{4}\)\s*$', '', folder).strip()
    i = clean.find(' - ')
    if i > 0:
        return {'artist': clean[:i].strip(), 'album': clean[i + 3:].strip()}
    return {'artist': '', 'album': clean}

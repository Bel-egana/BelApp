"""
Lógica de organización: construir la ruta destino de cada track.

Pura: no mueve archivos ni toca el disco — solo arma el objeto Path de
destino a partir de la carpeta base + género/sello/año. El movimiento
real de archivos vive (por ahora) en la UI.
"""
from pathlib import Path


def build_path(base, genre, label, year, name):
    """Arma la ruta destino:  base / Género / Sello / Año / archivo.

    Si falta algún dato usa un placeholder ('Sin Género', 'Sin Sello',
    'Sin Año') para que el track nunca quede suelto en la raíz.
    """
    return (Path(base)
            / (genre or 'Sin Género')
            / (label or 'Sin Sello')
            / (year  or 'Sin Año')
            / name)

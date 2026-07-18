"""
Armado de playlists .m3u8 para Traktor, agrupando por Género (tag) + Año.

Lógica pura y testeable: no toca el disco. La API se encarga de escanear los
tags y escribir los archivos. Las playlists son por REFERENCIA (rutas a los
archivos) — no mueven ni copian audio.
"""
import re
from pathlib import Path

# Caracteres no permitidos en nombres de archivo de Windows.
_ILEGAL = r'[<>:"/\\|?*]'


def playlist_filename(genre, year):
    """Nombre de archivo seguro para la playlist: 'Género - Año.m3u8'.

    Reemplaza los caracteres ilegales (la '/' de 'Ethereal / Melodic Techno',
    ':', '*', etc.) por '_'."""
    safe = re.sub(_ILEGAL, '_', str(genre)).strip()
    return f"{safe} - {year}.m3u8"


def group_by_genre_year(tracks):
    """Agrupa una lista de tracks en {(género, año): [tracks]}.

    Cada track es un dict con al menos 'genre' y 'year'. Los que no tienen
    género o año se saltean (no se pueden clasificar)."""
    grupos = {}
    for t in tracks:
        genre = (t.get('genre') or '').strip()
        year = (t.get('year') or '').strip()
        if not genre or not year:
            continue
        grupos.setdefault((genre, year), []).append(t)
    return grupos


def build_m3u8(tracks):
    """Arma el texto de un .m3u8 (UTF-8) a partir de una lista de tracks.

    Cada track: dict con 'path' y, opcionalmente, 'artist'/'title'. Si no hay
    artista/título usa el nombre del archivo como etiqueta."""
    lines = ['#EXTM3U']
    for t in tracks:
        path = t.get('path', '')
        artist = (t.get('artist') or '').strip()
        title = (t.get('title') or '').strip()
        if artist or title:
            etiqueta = f'{artist} - {title}'.strip(' -')
        else:
            etiqueta = Path(path).name
        lines.append(f'#EXTINF:-1,{etiqueta}')
        lines.append(path)
    return '\n'.join(lines) + '\n'

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


def traktor_key(path):
    """Convierte una ruta de Windows al formato de clave de Traktor.
    'D:\\Bel\\Música\\Psy\\x.mp3'  ->  'D:/:Bel/:Música/:Psy/:x.mp3'."""
    s = str(path).replace('/', '\\')
    if ':' in s:
        drive, rest = s.split(':', 1)
        segs = [x for x in rest.split('\\') if x]
        return drive + ':' + ''.join('/:' + x for x in segs)
    segs = [x for x in s.split('\\') if x]
    return ''.join('/:' + x for x in segs)


def _xml_attr(s):
    """Escapa un valor para un atributo XML del .nml."""
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def _split_traktor(path):
    """Ruta Windows -> (VOLUME, DIR_traktor, FILE) como los guarda Traktor.
    'D:\\Bel\\Música\\Psy\\x.mp3' -> ('D:', '/:Bel/:Música/:Psy/:', 'x.mp3')."""
    s = str(path).replace('/', '\\')
    if ':' in s:
        drive, rest = s.split(':', 1)
        vol = drive + ':'
    else:
        vol, rest = '', s
    segs = [x for x in rest.split('\\') if x]
    file = segs[-1] if segs else ''
    dirs = segs[:-1]
    dir_t = ''.join('/:' + d for d in dirs) + '/:'
    return vol, dir_t, file


def nml_filename(genre, year):
    """Nombre de archivo seguro para el .nml de una playlist: 'Género - Año.nml'."""
    safe = re.sub(_ILEGAL, '_', str(genre)).strip()
    return f"{safe} - {year}.nml"


def _collection_entry(t):
    """Una <ENTRY> de la sección COLLECTION para un track (DRY)."""
    vol, dir_t, file = _split_traktor(t.get('path', ''))
    return (
        f'<ENTRY TITLE="{_xml_attr(t.get("title", ""))}" '
        f'ARTIST="{_xml_attr(t.get("artist", ""))}">'
        f'<LOCATION DIR="{_xml_attr(dir_t)}" FILE="{_xml_attr(file)}" '
        f'VOLUME="{_xml_attr(vol)}"></LOCATION>'
        f'<INFO GENRE="{_xml_attr(t.get("genre", ""))}" '
        f'LABEL="{_xml_attr(t.get("label", ""))}"></INFO></ENTRY>')


def _playlist_entry(t):
    """Una <ENTRY><PRIMARYKEY> de la sección PLAYLIST para un track (DRY)."""
    return (
        f'<ENTRY><PRIMARYKEY TYPE="TRACK" '
        f'KEY="{_xml_attr(traktor_key(t.get("path", "")))}">'
        f'</PRIMARYKEY></ENTRY>')


def build_traktor_playlist_nml(name, tracks):
    """Arma UN .nml de Traktor con una sola playlist plana (por referencia).
    Es el formato NATIVO que Traktor importa bien (el árbol anidado no lo toma:
    Traktor 2 lo aplana). Incluye la sección COLLECTION con una entrada por
    track para que Traktor agregue/enlace los que no estén en la colección.

    'name' es el nombre de la playlist (ej. 'Deep House - 2019'). No toca disco."""
    import uuid
    # COLLECTION: una entrada por track (única por ruta).
    usados = {}
    for t in tracks:
        usados.setdefault(t.get('path', ''), t)
    col = ''.join(_collection_entry(t) for t in usados.values())
    pk = ''.join(_playlist_entry(t) for t in tracks)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        '<NML VERSION="19"><HEAD COMPANY="www.native-instruments.com" PROGRAM="Traktor"></HEAD>\n'
        '<MUSICFOLDERS></MUSICFOLDERS>\n'
        f'<COLLECTION ENTRIES="{len(usados)}">' + col + '</COLLECTION>\n'
        '<PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="1">'
        f'<NODE TYPE="PLAYLIST" NAME="{_xml_attr(name)}">'
        f'<PLAYLIST ENTRIES="{len(tracks)}" TYPE="LIST" UUID="{uuid.uuid4().hex}">'
        + pk +
        '</PLAYLIST></NODE></SUBNODES></NODE></PLAYLISTS>\n</NML>\n')

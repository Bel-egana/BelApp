"""
Lógica de géneros: el mapeo de estilos de Discogs a las categorías de Bel.

Discogs devuelve estilos muy variados (ej. 'Tech House', 'Goa Trance').
Acá los traducimos a las 4 categorías con las que Bel organiza su música.
Es lógica pura: entra un texto, sale la categoría (o '' si no hay match).
"""

# Las 4 categorías propias (las que aparecen en el desplegable de la app)
BEL_GENRES = [
    'Deep & Progressive House',
    'Melodic Techno & Techno',
    'Psychedelic Trance',
    'Trance',
]

# Mapeo: estilo de Discogs (en minúsculas) -> categoría de Bel.
# OJO: el orden importa. format_genre() devuelve la PRIMERA clave que
# aparezca dentro del texto, así que las más específicas van primero.
GENRE_MAP = {
    'melodic techno':     'Melodic Techno & Techno',
    'techno':             'Melodic Techno & Techno',
    'industrial techno':  'Melodic Techno & Techno',
    'dark techno':        'Melodic Techno & Techno',
    'melodic house':      'Deep & Progressive House',
    'deep house':         'Deep & Progressive House',
    'progressive house':  'Deep & Progressive House',
    'tech house':         'Deep & Progressive House',
    'organic house':      'Deep & Progressive House',
    'afro house':         'Deep & Progressive House',
    'house':              'Deep & Progressive House',
    'psychedelic trance': 'Psychedelic Trance',
    'psytrance':          'Psychedelic Trance',
    'goa trance':         'Psychedelic Trance',
    'trance':             'Trance',
    'progressive trance': 'Trance',
    'uplifting trance':   'Trance',
}


def format_genre(raw):
    """Traduce un estilo crudo (ej. 'Deep House') a una categoría de Bel.

    Devuelve '' si el texto está vacío o si ningún estilo conocido
    aparece dentro de él.
    """
    if not raw:
        return ''
    low = raw.lower()
    for clave, categoria in GENRE_MAP.items():
        if clave in low:
            return categoria
    return ''

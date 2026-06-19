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


# ─────────────────────────────────────────────────────────────────────────────
# Taxonomía ESPECÍFICA de Bel (para el normalizador del historial de Traktor).
# Más granular que las 4 de arriba. Se usa para limpiar los géneros sucios de
# la biblioteca hacia esta lista curada.
# ─────────────────────────────────────────────────────────────────────────────
BEL_GENRES_SPECIFIC = [
    'Melodic Techno', 'Techno', 'Acid Techno', 'Deep House', 'Melodic House',
    'Progressive House', 'Tech House', 'Afro / Organic House', 'Indie Dance',
    'Trance', 'Psytrance', 'Progressive Psy',
]

# Reglas ORDENADAS (substring en minúsculas -> categoría). Gana la PRIMERA que
# matchea, por eso las más específicas van primero. Lo que no matchea queda '' .
SPECIFIC_RULES = [
    ('acid techno',             'Acid Techno'),
    ('melodic house & techno',  'Melodic Techno'),   # Beatport los junta -> Bel: Melodic Techno
    ('melodic house and techno', 'Melodic Techno'),
    ('melodic techno',          'Melodic Techno'),
    ('progressive psy',         'Progressive Psy'),
    ('iboga',                   'Progressive Psy'),
    ('tech house',              'Tech House'),
    ('afro house',              'Afro / Organic House'),
    ('organic house',           'Afro / Organic House'),
    ('deep house',              'Deep House'),
    ('melodic house',           'Melodic House'),
    ('progressive house',       'Progressive House'),
    ('prog-house',              'Progressive House'),
    ('house progressive',       'Progressive House'),
    ('indie dance',             'Indie Dance'),
    ('psy',                     'Psytrance'),          # psychedelic, psy-trance, psychadelic, goa-psy
    ('goa',                     'Psytrance'),
    ('progressive trance',      'Trance'),
    ('progressivetrance',       'Trance'),
    ('uplifting',               'Trance'),
    ('techno',                  'Techno'),             # peak time / driving / raw / hypnotic / minimal techno
    ('trance',                  'Trance'),             # genérico, dance/trance, tech trance, main floor
]


def map_genre_specific(raw):
    """Traduce un género crudo a la taxonomía específica de Bel (12 categorías).

    Devuelve '' si está vacío o no matchea ninguna regla (basura, géneros que
    no son de Bel, etc. — esos se dejan sin tocar)."""
    if not raw:
        return ''
    low = raw.lower()
    for clave, categoria in SPECIFIC_RULES:
        if clave in low:
            return categoria
    return ''

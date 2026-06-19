"""
Normalizador de géneros: recorre una carpeta de música, lee el género de
cada track y lo traduce a una de las 4 categorías de Bel (vía format_genre).

Clasifica cada track en:
  - changed:    su género mapea a otra categoría -> se reescribe el tag
  - already_ok: su género ya es una de las 4 categorías
  - no_match:   tiene género pero no mapea (ej. Blues) -> no se toca
  - no_genre:   no tiene género -> no se puede normalizar (necesita Discogs)

Con dry_run=True solo reporta; con dry_run=False reescribe los tags
(preservando artista/título/álbum/sello/año, solo cambia el género).
"""
from pathlib import Path

from core.genres import map_genre_specific
from core.metadata import is_audio, read_id3, write_id3_tags


def normalize_folder(folder, dry_run=True):
    report = {'changed': [], 'already_ok': 0, 'no_match': 0,
              'no_genre': 0, 'total': 0}
    base = Path(folder)
    for f in base.rglob('*'):
        if not (f.is_file() and is_audio(f.name)):
            continue
        report['total'] += 1
        tags = read_id3(f)
        cur = tags.get('genre', '')
        if not cur:
            report['no_genre'] += 1
            continue
        mapped = map_genre_specific(cur)
        if not mapped:
            report['no_match'] += 1
            continue
        if mapped == cur:
            report['already_ok'] += 1
            continue
        report['changed'].append({'path': str(f), 'old': cur, 'new': mapped})
        if not dry_run:
            write_id3_tags(f, tags.get('artist', ''), tags.get('title', ''),
                           tags.get('album', ''), tags.get('label', ''),
                           mapped, tags.get('year', ''))
    return report

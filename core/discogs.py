"""
Cliente de la API de Discogs: búsqueda con rate limit + parseo de resultados.

Rate limit: Discogs permite 60 requests/min autenticado. Espaciamos cada
llamada al menos MIN_INTERVAL segundos.
search_with_fallback implementa el reintento "solo artista" cuando la
búsqueda completa no devuelve nada.
"""
import re
import time

import requests

from core.genres import format_genre

DISCOGS_BASE = 'https://api.discogs.com'
USER_AGENT = 'BelApp/1.0'
MIN_INTERVAL = 1.1

_last_request = 0.0


def discogs_search(query, token, limit=10):
    """Busca releases en Discogs. Lanza requests.HTTPError si la API falla."""
    global _last_request
    wait = MIN_INTERVAL - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()
    headers = {'User-Agent': USER_AGENT,
               'Authorization': f'Discogs token={token}'}
    r = requests.get(f'{DISCOGS_BASE}/database/search',
                     params={'q': query, 'type': 'release', 'per_page': limit},
                     headers=headers, timeout=12)
    r.raise_for_status()
    return r.json().get('results', [])


def search_with_fallback(query, token, fallback='', limit=10):
    """Busca; si no hay resultados y hay fallback, reintenta con el fallback.

    Devuelve (results, used_fallback).
    """
    results = discogs_search(query, token, limit)
    if not results and fallback:
        return discogs_search(fallback, token, limit), True
    return results, False


def parse_discogs_result(res):
    """Convierte un resultado crudo de la API en un dict plano para la app."""
    genres = res.get('genre') or []
    styles = res.get('style') or []
    labels = res.get('label') or []
    year = str(res.get('year', '') or '')[:4]
    title = res.get('title', '')
    genre_raw = styles[0] if styles else (genres[0] if genres else '')
    genre = format_genre(genre_raw) or genre_raw
    label = labels[0] if labels else ''
    label = re.sub(r'\s*[-–]\s*\w*\d+\w*$', '', label).strip()
    artist = ''
    if ' - ' in title:
        parts = title.split(' - ', 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    return {'artist': artist, 'title': title, 'genre': genre,
            'label': label, 'year': year,
            'format': ', '.join(res.get('format') or [])}

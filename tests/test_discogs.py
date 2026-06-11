"""Tests de core/discogs.py — búsqueda en Discogs (sin red) y parseo."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core.discogs as discogs_mod
from core.discogs import (discogs_search, parse_discogs_result,
                          search_with_fallback)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_discogs_search_arma_request_correcto(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, params=params, headers=headers)
        return FakeResponse({'results': [{'title': 'X - Y'}]})

    monkeypatch.setattr(discogs_mod.requests, 'get', fake_get)
    monkeypatch.setattr(discogs_mod.time, 'sleep', lambda s: None)

    out = discogs_search('camelphat feeling', 'TOKEN123', limit=5)
    assert out == [{'title': 'X - Y'}]
    assert captured['url'].endswith('/database/search')
    assert captured['params']['q'] == 'camelphat feeling'
    assert captured['params']['per_page'] == 5
    assert 'token=TOKEN123' in captured['headers']['Authorization']


def test_fallback_se_usa_cuando_no_hay_resultados(monkeypatch):
    calls = []

    def fake_search(query, token, limit=10):
        calls.append(query)
        return [] if query == 'query completa' else [{'title': 'ok'}]

    monkeypatch.setattr(discogs_mod, 'discogs_search', fake_search)
    results, used_fallback = search_with_fallback(
        'query completa', 'tok', fallback='solo artista')
    assert used_fallback is True
    assert results == [{'title': 'ok'}]
    assert calls == ['query completa', 'solo artista']


def test_fallback_no_se_usa_si_hay_resultados(monkeypatch):
    monkeypatch.setattr(discogs_mod, 'discogs_search',
                        lambda q, t, limit=10: [{'title': 'directo'}])
    results, used_fallback = search_with_fallback('q', 'tok', fallback='artista')
    assert used_fallback is False
    assert results == [{'title': 'directo'}]


def test_parse_resultado_completo():
    res = {'title': 'CamelPhat - For A Feeling', 'style': ['Tech House'],
           'genre': ['Electronic'], 'label': ['RCA - 12345'],
           'year': 2020, 'format': ['File', 'MP3']}
    p = parse_discogs_result(res)
    assert p['artist'] == 'CamelPhat'
    assert p['title'] == 'For A Feeling'
    assert p['genre'] == 'Deep & Progressive House'
    assert p['label'] == 'RCA'
    assert p['year'] == '2020'
    assert p['format'] == 'File, MP3'


def test_parse_resultado_minimo_no_explota():
    p = parse_discogs_result({'title': 'Sin Separador'})
    assert p['artist'] == ''
    assert p['title'] == 'Sin Separador'
    assert p['genre'] == ''
    assert p['label'] == ''
    assert p['year'] == ''

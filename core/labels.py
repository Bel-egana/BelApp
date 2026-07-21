"""
Detección de sellos (labels) con nombre PARECIDO a una carpeta ya existente,
para evitar crear duplicados tipo "Stil Vor Talent" vs "Stir Vol Talent" o
"Set About" vs "Set About Music".

Lógica pura: entra un sello candidato + la lista de sellos existentes, sale la
lista de existentes "parecidos" (ordenada, más parecido primero; vacía si no
hay). No toca el disco.
"""
import re

# Sufijos genéricos de sello que ignoramos al comparar el "núcleo" del nombre.
_SUFIJOS = ('recordings', 'records', 'music', 'recs', 'rec', 'ltd')

# Mínimo de caracteres tipeados para empezar a sugerir por prefijo (evita ruido).
_MIN_PREFIJO = 4


def _norm(s):
    """Minúsculas y solo alfanumérico (ignora espacios, guiones, puntos, may.)."""
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


def _core(s):
    """Como _norm pero saca un sufijo genérico de sello del final (Music, Records…)."""
    palabras = [p for p in re.split(r'[^a-z0-9]+', str(s).lower()) if p]
    if len(palabras) > 1 and palabras[-1] in _SUFIJOS:
        palabras = palabras[:-1]
    return ''.join(palabras)


def _distancia(a, b):
    """Distancia de edición (Levenshtein) entre dos strings."""
    if a == b:
        return 0
    if not a or not b:
        return len(a) + len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _es_parecido(cand, exist):
    """¿'cand' se parece a 'exist' sin ser la MISMA carpeta?"""
    # Idénticos como carpeta (Windows ignora mayúsculas) -> es la misma, no avisar.
    if cand.strip().lower() == exist.strip().lower():
        return False
    nc, ne = _norm(cand), _norm(exist)
    if not nc or not ne:
        return False
    # Regla 1: iguales ignorando mayúsculas / espacios / guiones / puntos.
    if nc == ne:
        return True
    # Regla 2: mismo núcleo salvo un sufijo genérico de sello (Music/Records/…).
    cc = _core(cand)
    if cc and cc == _core(exist):
        return True
    # Regla 3: lo tipeado es el COMIENZO de un sello existente -> avisa temprano,
    # mientras escribís (tipo autocompletado). Desde _MIN_PREFIJO caracteres.
    if len(nc) >= _MIN_PREFIJO and ne.startswith(nc):
        return True
    # Regla 4: 1-2 letras de diferencia (typo/transposición), con guarda de largo.
    if min(len(nc), len(ne)) >= 5 and _distancia(nc, ne) <= 2:
        return True
    return False


def sellos_parecidos(candidato, existentes):
    """Sellos de 'existentes' parecidos al 'candidato' (sin contar idénticos).

    Ordenados por cercanía (más parecido primero). [] si el candidato está
    vacío o no hay parecidos."""
    if not candidato or not str(candidato).strip():
        return []
    cand_low = str(candidato).strip().lower()
    # Si coincide EXACTO con una carpeta existente, la estás reusando: no avisar.
    if any(str(e).strip().lower() == cand_low for e in existentes):
        return []
    nc = _norm(candidato)
    matches = [e for e in existentes if _es_parecido(candidato, e)]
    matches.sort(key=lambda e: _distancia(nc, _norm(e)))
    return matches

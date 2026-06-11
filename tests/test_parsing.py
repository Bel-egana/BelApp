"""
Tests de core/parsing.py

Cada función test_* verifica un comportamiento concreto con 'assert'
(= "afirmo que esto tiene que ser verdad"). Si alguna afirmación falla,
el test falla y nos avisa exactamente qué se rompió.

Se puede correr de dos formas:
  - Con pytest:        pytest
  - Sin instalar nada: python tests/test_parsing.py
"""
import os
import sys

# Permite importar 'core' aunque corramos el archivo directo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.parsing import parse_filename, parse_folder_name


# ─── parse_filename ──────────────────────────────────────────────────────────

def test_artista_y_titulo_basico():
    r = parse_filename("Atmos - Only for You.mp3")
    assert r['artist'] == "Atmos"
    assert r['title'] == "Only for You"


def test_titulo_con_parentesis_y_remix():
    r = parse_filename("CamelPhat - For A Feeling (Layton Giordani Remix).mp3")
    assert r['artist'] == "CamelPhat"
    assert r['title'] == "For A Feeling (Layton Giordani Remix)"


def test_artista_con_coma_y_varios():
    r = parse_filename("Ae-ther, Benjamin Yellowitz - Dynamite (Original Mix).mp3")
    assert r['artist'] == "Ae-ther, Benjamin Yellowitz"
    assert r['title'] == "Dynamite (Original Mix)"


def test_saca_prefijo_entre_corchetes():
    r = parse_filename("[Anjunabeats] Above & Beyond - Sun in Your Eyes.mp3")
    assert r['artist'] == "Above & Beyond"
    assert r['title'] == "Sun in Your Eyes"


def test_sin_separador_todo_es_artista():
    r = parse_filename("UntitledTrack.wav")
    assert r['artist'] == "UntitledTrack"
    assert r['title'] == ""


# ─── parse_folder_name ───────────────────────────────────────────────────────

def test_carpeta_con_anio():
    r = parse_folder_name("Tale Of Us - Endless (2020)")
    assert r['artist'] == "Tale Of Us"
    assert r['album'] == "Endless"


def test_carpeta_sin_artista():
    r = parse_folder_name("Compilado Verano 2021 (2021)")
    assert r['artist'] == ""
    assert r['album'] == "Compilado Verano 2021"


# ─── Runner casero (por si no tenés pytest instalado) ────────────────────────

if __name__ == '__main__':
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith('test_') and callable(v)]
    ok = 0
    print(f"Corriendo {len(tests)} tests de core/parsing.py\n")
    for t in tests:
        try:
            t()
            print(f"  [OK]   {t.__name__}")
            ok += 1
        except AssertionError as e:
            print(f"  [FAIL] {t.__name__}  ->  AFIRMACION FALLIDA: {e}")
        except Exception:
            print(f"  [FAIL] {t.__name__}  ->  ERROR:")
            traceback.print_exc()
    print(f"\nResultado: {ok}/{len(tests)} tests OK")
    sys.exit(0 if ok == len(tests) else 1)

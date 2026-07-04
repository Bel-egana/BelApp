"""
Tests de core/labels.py — detección de sellos con nombre parecido.

Correr con:  pytest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.labels import sellos_parecidos


# ── Regla 1: iguales ignorando mayúsculas / espacios / guiones ───────────────

def test_igual_ignorando_guiones_y_mayusculas():
    # Distinto en disco (guion vs espacio) pero es el mismo sello -> avisa.
    assert "Set About" in sellos_parecidos("Set-About", ["Set About"])
    assert "Set.About" in sellos_parecidos("Set About", ["Set.About"])


def test_identico_como_carpeta_no_avisa():
    # Windows ignora mayúsculas: "steyoyoke" y "Steyoyoke" son la MISMA carpeta.
    assert sellos_parecidos("Steyoyoke", ["Steyoyoke"]) == []
    assert sellos_parecidos("steyoyoke", ["Steyoyoke"]) == []


# ── Regla 2: sufijo típico de sello (Music / Records / Recordings) ───────────

def test_sufijo_music():
    assert "Set About Music" in sellos_parecidos("Set About", ["Set About Music"])
    assert "Set About" in sellos_parecidos("Set About Music", ["Set About"])


def test_sufijo_records():
    assert "Space Motion Records" in sellos_parecidos(
        "Space Motion", ["Space Motion Records"])


# ── Regla 3: 1-2 letras de diferencia (typo / transposición) ─────────────────

def test_typo_transposicion():
    # El caso real de la foto de Belén.
    assert "Stil Vor Talent" in sellos_parecidos(
        "Stir Vol Talent", ["Stil Vor Talent"])


# ── No falsos positivos ──────────────────────────────────────────────────────

def test_sellos_realmente_distintos_no_avisan():
    existentes = ["Space Kraft Recordings", "Steyoyoke", "Sol Music",
                  "Siona Records", "Sincopat"]
    assert sellos_parecidos("Space Motion Records", existentes) == []
    # "Steyoyoke Black" es un sublabel real, distinto de "Steyoyoke" -> no avisa.
    assert sellos_parecidos("Steyoyoke Black", ["Steyoyoke"]) == []


def test_candidato_vacio_no_avisa():
    assert sellos_parecidos("", ["Set About"]) == []
    assert sellos_parecidos("   ", ["Set About"]) == []
    assert sellos_parecidos(None, ["Set About"]) == []


def test_sin_existentes_no_avisa():
    assert sellos_parecidos("Set About", []) == []


def test_ordena_por_cercania():
    # El más parecido va primero.
    res = sellos_parecidos("Stir Vol Talent",
                           ["Stone Seed", "Stil Vor Talent"])
    assert res[0] == "Stil Vor Talent"

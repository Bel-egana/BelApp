# BelApp Fase 1 — Fundaciones (git + spike PyWebView + completar core/)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar la base lista para el rediseño web-style: carpeta de trabajo versionada en privado, PyWebView validado en esta máquina, y toda la lógica de `belapp.py` extraída a `core/` con tests (la app tkinter sigue funcionando igual).

**Architecture:** La app tkinter actual (`belapp.py`) va quedando como capa fina de UI que importa todo de `core/`. Cada extracción es TDD: test primero, mover código, conectar, verificar suite completa, commit. El spike PyWebView valida el único riesgo técnico desconocido antes de invertir en el frontend.

**Tech Stack:** Python 3.13, pytest, pywebview, mutagen, requests, tkinter (app actual), git.

**Spec:** `docs/superpowers/specs/2026-06-11-webstyle-ui-design.md`

**Contexto de rutas:**
- Carpeta de trabajo: `C:\Users\Bel\OneDrive\Escritorio\Belapp` (hoy contiene el repo PÚBLICO de vidriera, que ignora todo el código)
- Repo privado viejo (desactualizado): `C:\Users\Bel\OneDrive\Escritorio\Belapp-privado`
- Los tests existentes usan el patrón `sys.path.insert` para importar `core` — los nuevos tests siguen el mismo patrón.

---

### Task 1: Reorganizar git — vidriera afuera, repo privado en la carpeta de trabajo

**Objetivo:** que la carpeta de trabajo sea un repo privado versionable (con el código adentro), y la vidriera pública viva en su propia carpeta `Belapp-vidriera`.

**Files:**
- Move: `Belapp\.git` → `Belapp-vidriera\.git`
- Create: `Belapp-vidriera\` con README.md, README.en.md, LICENSE, .gitignore (copias)
- Replace: `Belapp\.gitignore` (versión privada)
- Init: repo git nuevo en `Belapp\`

- [ ] **Step 1: Crear la carpeta vidriera y mover el repo público entero**

```powershell
$base = "C:\Users\Bel\OneDrive\Escritorio"
New-Item -ItemType Directory -Force "$base\Belapp-vidriera" | Out-Null
Move-Item "$base\Belapp\.git" "$base\Belapp-vidriera\.git"
Copy-Item "$base\Belapp\README.md","$base\Belapp\README.en.md","$base\Belapp\LICENSE","$base\Belapp\.gitignore" "$base\Belapp-vidriera\"
git -C "$base\Belapp-vidriera" status --short
```

Expected: solo ` M .gitignore` (el cambio pendiente que excluye docs/). Si aparece otra cosa, frenar y revisar.

- [ ] **Step 2: Commitear el .gitignore pendiente en la vidriera**

```powershell
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp-vidriera" add .gitignore
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp-vidriera" -c user.name="Belén Egaña" -c user.email="beleganha@gmail.com" commit -m "Excluir documentación interna de la vidriera"
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp-vidriera" status --short
```

Expected: working tree limpio.

- [ ] **Step 3: Escribir el .gitignore PRIVADO en la carpeta de trabajo**

Reemplazar el contenido completo de `C:\Users\Bel\OneDrive\Escritorio\Belapp\.gitignore` por:

```gitignore
# ─── Datos sensibles / personales — NUNCA subir, ni en repo privado ──────────
config.json
historial.json
belapp_*.txt

# ─── Python ─────────────────────────────────────────────────────────────────
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
env/

# ─── Herramientas de sesión ─────────────────────────────────────────────────
.superpowers/
.remember/

# ─── Sistema operativo / editores ───────────────────────────────────────────
Thumbs.db
desktop.ini
.DS_Store
.vscode/
.idea/
```

Nota: este repo SÍ incluye `*.py`, `core/`, `tests/` y `docs/` — es el privado.

- [ ] **Step 4: Inicializar el repo privado y commit inicial**

```powershell
$repo = "C:\Users\Bel\OneDrive\Escritorio\Belapp"
git -C $repo init -b main
git -C $repo config user.name "Belén Egaña"
git -C $repo config user.email "beleganha@gmail.com"
git -C $repo add .
git -C $repo status --short
```

Expected en el status: `belapp.py`, `core/`, `tests/`, `docs/`, READMEs, LICENSE, `.gitignore`. NO deben aparecer `config.json`, `historial.json` ni `belapp_*.txt`. Verificar con:

```powershell
git -C $repo check-ignore config.json historial.json
```

Expected: imprime ambos nombres (= ignorados). Luego:

```powershell
git -C $repo commit -m "Código completo de BelApp: app tkinter + core/ modularizado + tests + docs"
git -C $repo log --oneline
```

- [ ] **Step 5: Conectar el remoto privado (si existe) y retirar la carpeta vieja**

```powershell
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp-privado" remote -v
```

Si muestra un remoto (ej. `belapp-source`): agregarlo al repo nuevo y pushear con historia nueva:

```powershell
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp" remote add origin <URL_DEL_REMOTO>
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp" push --force -u origin main
```

Si NO muestra remoto: no hacer nada (el push a GitHub queda como paso manual de Belén cuando quiera).

Por último, la carpeta `Belapp-privado` queda obsoleta. NO borrarla automáticamente: avisarle a Belén que ya puede borrarla a mano cuando confirme que todo está en el repo nuevo.

---

### Task 2: Spike PyWebView — validar el riesgo técnico

**Files:**
- Create: `spike\hello_webview.py`

- [ ] **Step 1: Instalar pywebview**

```powershell
python -m pip install pywebview
python -c "import webview; print(webview.__version__)"
```

Expected: imprime una versión (5.x o superior). Si la instalación falla, FRENAR: este es el riesgo que el spike debe detectar — investigar antes de seguir.

- [ ] **Step 2: Escribir el hola-mundo con puente JS→Python**

Crear `spike\hello_webview.py`:

```python
"""
Spike PyWebView: valida que (1) abre ventana con HTML/CSS moderno y
(2) el puente JS -> Python funciona en esta máquina (WebView2).
Correr:  python spike/hello_webview.py
"""
import webview


class Api:
    def saludar(self, nombre):
        return f"Hola {nombre} — Python respondió por el puente."


HTML = """
<!DOCTYPE html>
<html><body style="background:#0c0c10;color:#e8e8e8;font-family:Segoe UI,sans-serif;
display:flex;flex-direction:column;align-items:center;justify-content:center;
height:95vh;margin:0;gap:18px">
  <h1 style="font-weight:600;margin:0">
    <span style="color:#e8ff00">Bel</span><span style="color:#ff3c6e">App</span>
    <span style="color:#9a9aa8;font-size:15px;font-weight:400"> spike</span>
  </h1>
  <button style="padding:11px 26px;border-radius:999px;border:none;background:#e8ff00;
   color:#0c0c10;font-weight:600;font-size:14px;cursor:pointer"
   onclick="pywebview.api.saludar('Bel').then(r => document.getElementById('out').innerText = r)">
    Probar puente JS → Python
  </button>
  <p id="out" style="color:#00ffa3;font-size:14px;min-height:20px"></p>
</body></html>
"""

if __name__ == '__main__':
    webview.create_window('BelApp — spike PyWebView', html=HTML,
                          js_api=Api(), width=540, height=400)
    webview.start()
```

- [ ] **Step 3: Correrlo y validar con Belén**

```powershell
python spike/hello_webview.py
```

Expected: se abre una ventana oscura con el logo BelApp, bordes/botón redondeados, y al clickear el botón aparece "Hola Bel — Python respondió por el puente." en verde. Belén confirma visualmente. Si la ventana no abre o el botón no responde: FRENAR y diagnosticar (probable falta de runtime WebView2) antes de continuar con el resto del plan.

- [ ] **Step 4: Commit**

```powershell
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp" add spike/hello_webview.py
git -C "C:\Users\Bel\OneDrive\Escritorio\Belapp" commit -m "spike: validar PyWebView y puente JS-Python en Windows"
```

---

### Task 3: Extraer core/config.py

**Files:**
- Create: `core\config.py`
- Test: `tests\test_config.py`
- Modify: `belapp.py` (métodos `_load_config` / `_save_config` + import)

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `tests\test_config.py`:

```python
"""Tests de core/config.py — carga y guardado de config.json."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import load_config, save_config


def test_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    assert save_config(p, {"base_path": "D:/Música", "discogs_token": "abc"}) is True
    data = load_config(p)
    assert data["base_path"] == "D:/Música"
    assert data["discogs_token"] == "abc"


def test_archivo_inexistente_devuelve_dict_vacio(tmp_path):
    assert load_config(tmp_path / "no_existe.json") == {}


def test_archivo_corrupto_devuelve_dict_vacio(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{esto no es json", encoding="utf-8")
    assert load_config(p) == {}


def test_json_que_no_es_dict_devuelve_dict_vacio(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_config(p) == {}
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL/ERROR con `ModuleNotFoundError: No module named 'core.config'`

- [ ] **Step 3: Crear el módulo**

Crear `core\config.py`:

```python
"""
Persistencia de configuración (config.json): token de Discogs y carpeta base.

Funciones puras respecto de la app: reciben el Path del archivo, devuelven
datos. Toleran archivo inexistente o corrupto devolviendo un dict vacío.
"""
import json


def load_config(path):
    """Lee el JSON de config. Devuelve {} si no existe, está corrupto o no es dict."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_config(path, data):
    """Guarda el dict como JSON legible. Devuelve True si pudo escribir."""
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding='utf-8')
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Conectar belapp.py**

En `belapp.py`, agregar al bloque de imports de core:

```python
from core.config import load_config, save_config
```

Reemplazar los métodos `_load_config` y `_save_config` (sección `# ── CONFIG ──`):

ANTES:
```python
    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
                if data.get('base_path'):     self.base_path.set(data['base_path'])
                if data.get('discogs_token'): self.discogs_token.set(data['discogs_token'])
            except Exception:
                pass

    def _save_config(self):
        try:
            CONFIG_PATH.write_text(
                json.dumps({'base_path': self.base_path.get(),
                            'discogs_token': self.discogs_token.get()}, indent=2),
                encoding='utf-8')
        except Exception:
            pass
```

DESPUÉS:
```python
    def _load_config(self):
        data = load_config(CONFIG_PATH)
        if data.get('base_path'):     self.base_path.set(data['base_path'])
        if data.get('discogs_token'): self.discogs_token.set(data['discogs_token'])

    def _save_config(self):
        save_config(CONFIG_PATH, {'base_path': self.base_path.get(),
                                  'discogs_token': self.discogs_token.get()})
```

- [ ] **Step 6: Verificación completa y commit**

```powershell
python -m py_compile belapp.py
python -c "import belapp; print('import OK')"
python -m pytest tests/ -q
```

Expected: compila, importa, toda la suite verde (21 + 4 nuevos = 25 passed).

```powershell
git add core/config.py tests/test_config.py belapp.py
git commit -m "feat(core): extraer config.py con tests; belapp lo usa"
```

---

### Task 4: Extraer core/metadata.py

**Files:**
- Create: `core\metadata.py`
- Test: `tests\test_metadata.py`
- Modify: `belapp.py` (quitar bloque mutagen, AUDIO_EXTS/IMAGE_EXTS, is_audio/is_image, read_id3, write_id3_tags + import)

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `tests\test_metadata.py`:

```python
"""Tests de core/metadata.py — extensiones de audio/imagen y tags ID3/FLAC."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.metadata import (MUTAGEN_OK, is_audio, is_image, read_id3,
                           write_id3_tags)


def test_is_audio():
    assert is_audio("track.mp3")
    assert is_audio("track.FLAC")
    assert is_audio("track.wav")
    assert not is_audio("portada.jpg")
    assert not is_audio("notas.txt")


def test_is_image():
    assert is_image("portada.jpg")
    assert is_image("cover.PNG")
    assert not is_image("track.mp3")


def test_read_id3_archivo_invalido_devuelve_vacio(tmp_path):
    f = tmp_path / "no_es_audio.mp3"
    f.write_bytes(b"esto no es un mp3")
    assert read_id3(f) == {}


def test_write_extension_no_soportada_devuelve_false(tmp_path):
    f = tmp_path / "archivo.txt"
    f.write_text("hola")
    assert write_id3_tags(f, "A", "T", "Al", "L", "G", "2024") is False


@pytest.mark.skipif(not MUTAGEN_OK, reason="mutagen no instalado")
def test_roundtrip_escribir_y_leer_mp3(tmp_path):
    f = tmp_path / "track.mp3"
    f.write_bytes(b"")
    ok = write_id3_tags(f, "CamelPhat", "For A Feeling", "Single",
                        "RCA", "Deep & Progressive House", "2020")
    assert ok is True
    tags = read_id3(f)
    assert tags["artist"] == "CamelPhat"
    assert tags["title"] == "For A Feeling"
    assert tags["label"] == "RCA"
    assert tags["year"] == "2020"
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_metadata.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'core.metadata'`

- [ ] **Step 3: Crear el módulo (código movido de belapp.py)**

Crear `core\metadata.py`:

```python
"""
Metadata de audio: detección de extensiones y lectura/escritura de tags
ID3 (mp3/wav/aiff) y Vorbis (flac) usando mutagen.

Si mutagen no está instalado, MUTAGEN_OK queda en False y las funciones
de tags degradan con elegancia (read devuelve {}, write devuelve False).
"""
from pathlib import Path

try:
    from mutagen.id3 import (ID3, TALB, TCON, TDRC, TIT2, TPE1, TPUB,
                             ID3NoHeaderError)
    from mutagen.flac import FLAC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

AUDIO_EXTS = {'.mp3', '.wav', '.aiff', '.flac', '.m4a'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}


def is_audio(name):
    return Path(name).suffix.lower() in AUDIO_EXTS


def is_image(name):
    return Path(name).suffix.lower() in IMAGE_EXTS


def read_id3(filepath):
    """Lee los tags del archivo. Devuelve solo los campos con valor."""
    tags = {}
    if not MUTAGEN_OK:
        return tags
    try:
        ext = filepath.suffix.lower()
        if ext in ('.mp3', '.wav', '.aiff'):
            audio = ID3(str(filepath))

            def g(k):
                v = audio.get(k)
                return str(v.text[0]).strip() if v and hasattr(v, 'text') and v.text else ''

            tags = {'artist': g('TPE1') or g('TPE2'), 'title': g('TIT2'),
                    'album': g('TALB'), 'label': g('TPUB'), 'genre': g('TCON'),
                    'year': str(g('TDRC') or g('TYER'))[:4]}
        elif ext == '.flac':
            audio = FLAC(str(filepath))

            def gf(k):
                return (audio.get(k.lower()) or [''])[0].strip()

            tags = {'artist': gf('artist'), 'title': gf('title'), 'album': gf('album'),
                    'label': gf('organization') or gf('label'), 'genre': gf('genre'),
                    'year': (gf('date') or gf('year'))[:4]}
    except Exception:
        pass
    return {k: v for k, v in tags.items() if v}


def write_id3_tags(filepath, artist, title, album, label, genre, year):
    """Escribe los tags. Devuelve True si pudo, False si no."""
    if not MUTAGEN_OK:
        return False
    try:
        ext = filepath.suffix.lower()
        if ext in ('.mp3', '.wav', '.aiff'):
            try:
                tags = ID3(str(filepath))
            except ID3NoHeaderError:
                tags = ID3()
            tags['TIT2'] = TIT2(encoding=3, text=title)
            tags['TPE1'] = TPE1(encoding=3, text=artist)
            tags['TALB'] = TALB(encoding=3, text=album)
            tags['TPUB'] = TPUB(encoding=3, text=label)
            tags['TCON'] = TCON(encoding=3, text=genre)
            tags['TDRC'] = TDRC(encoding=3, text=year)
            tags.save(str(filepath))
            return True
        elif ext == '.flac':
            audio = FLAC(str(filepath))
            audio['title'] = title
            audio['artist'] = artist
            audio['album'] = album
            audio['organization'] = label
            audio['genre'] = genre
            audio['date'] = year
            audio.save()
            return True
    except Exception:
        return False
    return False
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_metadata.py -v`
Expected: 5 passed (o 4 passed + 1 skipped si mutagen faltara)

- [ ] **Step 5: Conectar belapp.py**

5a. Agregar al bloque de imports de core:

```python
from core.metadata import (MUTAGEN_OK, is_audio, is_image, read_id3,
                           write_id3_tags)
```

5b. BORRAR de `belapp.py` el bloque mutagen del tope:

```python
try:
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPUB, TCON, TDRC, ID3NoHeaderError
    from mutagen.flac import FLAC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False
```

5c. BORRAR de las constantes:

```python
AUDIO_EXTS   = {'.mp3', '.wav', '.aiff', '.flac', '.m4a'}
IMAGE_EXTS   = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
```

5d. BORRAR de la sección HELPERS las dos líneas:

```python
def is_audio(n): return Path(n).suffix.lower() in AUDIO_EXTS
def is_image(n): return Path(n).suffix.lower() in IMAGE_EXTS
```

(la función `lighten` se queda — es helper de UI)

5e. BORRAR las funciones completas `read_id3(filepath)` y `write_id3_tags(filepath, ...)` (las definiciones largas que quedaron en belapp.py; son idénticas a las movidas a core).

- [ ] **Step 6: Verificación completa y commit**

```powershell
python -m py_compile belapp.py
python -c "import belapp; print('import OK')"
python -m pytest tests/ -q
```

Expected: todo verde (25 + 5 = 30 passed, o 29+1 skipped).

```powershell
git add core/metadata.py tests/test_metadata.py belapp.py
git commit -m "feat(core): extraer metadata.py (ID3/FLAC) con tests; belapp lo usa"
```

---

### Task 5: Extraer core/discogs.py

**Files:**
- Create: `core\discogs.py`
- Test: `tests\test_discogs.py`
- Modify: `belapp.py` (quitar `DISCOGS_BASE`, `_last_discogs`, `discogs_search`, `parse_discogs_result`, import de `requests` + agregar import de core)

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `tests\test_discogs.py`:

```python
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
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_discogs.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'core.discogs'`

- [ ] **Step 3: Crear el módulo**

Crear `core\discogs.py`:

```python
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
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_discogs.py -v`
Expected: 5 passed

- [ ] **Step 5: Conectar belapp.py**

5a. Agregar al bloque de imports de core:

```python
from core.discogs import discogs_search, parse_discogs_result
```

5b. BORRAR `import requests` del tope (ya nadie lo usa en belapp.py).

5c. BORRAR la constante:

```python
DISCOGS_BASE = 'https://api.discogs.com'
```

5d. BORRAR la sección DISCOGS completa de belapp.py (el `_last_discogs = 0`, la función `discogs_search` y la función `parse_discogs_result` enteras — son idénticas a las movidas).

Nota: el método `_search_thread` de la clase sigue llamando `discogs_search` dos veces (búsqueda + reintento) para poder mostrar el mensaje "reintentando solo con..." entre medio. No tocarlo: ahora resuelve al import de core.

- [ ] **Step 6: Verificación completa y commit**

```powershell
python -m py_compile belapp.py
python -c "import belapp; print('import OK')"
python -m pytest tests/ -q
```

Expected: todo verde (30 + 5 = 35 passed).

```powershell
git add core/discogs.py tests/test_discogs.py belapp.py
git commit -m "feat(core): extraer discogs.py (API + rate limit + fallback) con tests"
```

---

### Task 6: Extraer core/history.py

**Files:**
- Create: `core\history.py`
- Test: `tests\test_history.py`
- Modify: `belapp.py` (métodos `_norm`, `_hist_name_index`, `_find_duplicate`, `_load_history`, `_save_history` + import)

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `tests\test_history.py`:

```python
"""Tests de core/history.py — historial persistente y detección de duplicados."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.history import (build_name_index, find_duplicate, load_history,
                          normalize_name, save_history)

HIST = [
    {'artista': 'CamelPhat', 'track': 'For A Feeling',
     'destino': r'D:\M\House\RCA\2020\CamelPhat - For A Feeling (Layton Giordani Remix).mp3'},
    {'artista': 'Atmos', 'track': 'Only for You',
     'destino': r'D:\M\Trance\Iboga\2012\Atmos - Only for You.mp3'},
]


def test_normalize_ignora_caso_espacios_simbolos():
    a = normalize_name("CamelPhat - For A Feeling (Remix)")
    b = normalize_name("camelphat   for a feeling remix")
    assert a == b
    assert normalize_name("") == ""


def test_index_y_duplicado_encontrado():
    idx = build_name_index(HIST)
    dup = find_duplicate(
        ["CamelPhat - For A Feeling (Layton Giordani Remix).mp3"], idx)
    assert dup is not None
    assert dup['artista'] == 'CamelPhat'


def test_duplicado_no_encontrado():
    idx = build_name_index(HIST)
    assert find_duplicate(["Stephan Bodzin - Strand.mp3"], idx) is None


def test_entrada_sin_destino_se_ignora():
    idx = build_name_index([{'artista': 'X', 'destino': ''}])
    assert idx == {}


def test_roundtrip_load_save(tmp_path):
    p = tmp_path / "historial.json"
    assert save_history(p, HIST) is True
    assert load_history(p) == HIST


def test_load_inexistente_o_corrupto_devuelve_lista_vacia(tmp_path):
    assert load_history(tmp_path / "no_existe.json") == []
    p = tmp_path / "roto.json"
    p.write_text("{no es json", encoding="utf-8")
    assert load_history(p) == []
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_history.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'core.history'`

- [ ] **Step 3: Crear el módulo**

Crear `core\history.py`:

```python
"""
Historial persistente (historial.json) y detección de duplicados.

La detección compara NOMBRES DE ARCHIVO normalizados (minúsculas, solo
alfanumérico): tolera diferencias de espacios, guiones y mayúsculas, y es
independiente de en qué carpeta quedó el archivo.
"""
import json
import re
from pathlib import Path


def normalize_name(s):
    """Normaliza un nombre para comparar (minúsculas, solo alfanumérico)."""
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


def build_name_index(history):
    """Dict {nombre_normalizado: entrada} de todo lo que está en el historial."""
    idx = {}
    for h in history:
        dest = h.get('destino', '')
        if not dest:
            continue
        key = normalize_name(Path(dest).stem)
        if key:
            idx.setdefault(key, h)
    return idx


def find_duplicate(filenames, index):
    """Devuelve la entrada del historial que coincide con alguno de los
    nombres de archivo dados, o None."""
    for name in filenames:
        key = normalize_name(Path(name).stem)
        if key and key in index:
            return index[key]
    return None


def load_history(path):
    """Lee el historial. Devuelve [] si no existe, está corrupto o no es lista."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def save_history(path, entries):
    """Guarda el historial como JSON legible. Devuelve True si pudo."""
    try:
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2),
                        encoding='utf-8')
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_history.py -v`
Expected: 6 passed

- [ ] **Step 5: Conectar belapp.py**

5a. Agregar al bloque de imports de core:

```python
from core.history import (build_name_index, find_duplicate, load_history,
                          save_history)
```

5b. Reemplazar en la clase los helpers de duplicados (sección `# ── DUPLICADOS ──`):

ANTES:
```python
    @staticmethod
    def _norm(s):
        """Normaliza un nombre para comparar (minúsculas, solo alfanumérico)."""
        return re.sub(r'[^a-z0-9]+', '', str(s).lower())

    def _hist_name_index(self):
        """Dict {nombre_normalizado: entrada} de todo lo que ya está en el historial."""
        idx = {}
        for h in self.history:
            dest = h.get('destino', '')
            if not dest: continue
            key = self._norm(Path(dest).stem)
            if key: idx.setdefault(key, h)
        return idx
```

DESPUÉS:
```python
    def _hist_name_index(self):
        return build_name_index(self.history)
```

5c. Reemplazar `_find_duplicate`:

ANTES:
```python
    def _find_duplicate(self, item, idx=None):
        """Devuelve la entrada de historial coincidente, o None."""
        if not self.history: return None
        idx = idx if idx is not None else self._hist_name_index()
        for n in self._item_filenames(item):
            key = self._norm(Path(n).stem)
            if key and key in idx:
                return idx[key]
        return None
```

DESPUÉS:
```python
    def _find_duplicate(self, item, idx=None):
        """Devuelve la entrada de historial coincidente, o None."""
        if not self.history: return None
        idx = idx if idx is not None else build_name_index(self.history)
        return find_duplicate(self._item_filenames(item), idx)
```

5d. Reemplazar `_load_history` y `_save_history`:

ANTES:
```python
    def _load_history(self):
        if HISTORY_PATH.exists():
            try:
                data = json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
                if isinstance(data, list):
                    self.history = data
            except Exception:
                self.history = []

    def _save_history(self):
        try:
            HISTORY_PATH.write_text(
                json.dumps(self.history, ensure_ascii=False, indent=2),
                encoding='utf-8')
        except Exception:
            pass
```

DESPUÉS:
```python
    def _load_history(self):
        self.history = load_history(HISTORY_PATH)

    def _save_history(self):
        save_history(HISTORY_PATH, self.history)
```

- [ ] **Step 6: Verificación completa y commit**

```powershell
python -m py_compile belapp.py
python -c "import belapp; print('import OK')"
python -m pytest tests/ -q
```

Expected: todo verde (35 + 6 = 41 passed).

```powershell
git add core/history.py tests/test_history.py belapp.py
git commit -m "feat(core): extraer history.py (historial + duplicados) con tests"
```

---

### Task 7: Verificación final de fase

- [ ] **Step 1: Suite completa + chequeos estáticos**

```powershell
python -m pytest tests/ -v
python -m py_compile belapp.py
python -c "import belapp; print('import OK')"
```

Expected: ~41 passed, compila, importa.

- [ ] **Step 2: Smoke test manual con Belén (obligatorio)**

Belén abre la app y recorre el flujo completo una vez:

```powershell
python belapp.py
```

Checklist mínimo: cargar 1-2 tracks → buscar en Discogs (verifica red + token de config.json) → confirmar con datos → mover → verlo en Resultado e Historial → probar Deshacer. Todo debe comportarse EXACTAMENTE igual que antes de la fase.

- [ ] **Step 3: Commit de cierre y push (si hay remoto)**

```powershell
git add -A
git status --short
git commit -m "chore: cierre fase 1 - core/ completo, app tkinter 100% sobre core" --allow-empty
git push    # solo si el remoto quedó configurado en Task 1
```

---

## Fuera de este plan (próximos planes)

- **Plan Fase 2 — Frontend web + api.py:** las 4 vistas en `web/` + el puente PyWebView con los métodos de la app. Se escribe al cerrar esta fase (incorporando lo aprendido en el spike).
- **Plan Fase 3 — Empaquetado:** PyInstaller → `belapp.exe` + smoke test en máquina limpia.

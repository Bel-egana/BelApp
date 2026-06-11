# BelApp — Rediseño web-style de la interfaz (Diseño)

**Fecha:** 2026-06-11
**Estado:** Aprobado por Belén (diseño conversacional) — pendiente de plan de implementación
**Decisión de dirección:** Opción C — interfaz estilo web (HTML/CSS/JS) en ventana de escritorio

---

## 1. Contexto y objetivo

BelApp es un organizador de música para DJs: busca metadata en Discogs, valida con la
usuaria, escribe tags ID3/FLAC y mueve los archivos a una estructura
`Género / Sello / Año` en disco. Hoy la UI está en tkinter (`belapp.py`, ~1300 líneas)
y la lógica pura empezó a extraerse al paquete `core/` (parsing, genres, organizer,
con 21 tests en pytest).

**Objetivo:** reemplazar la interfaz tkinter por una interfaz moderna estilo web
(sidebar con íconos, bordes redondeados, dark theme con la identidad amarillo neón /
rosa de BelApp), manteniendo el 100% de la funcionalidad actual y la capacidad de
distribuir la app como `.exe` standalone.

**No-objetivos (fuera de alcance):**
- Versión web hosteada / multiusuario (la app mueve archivos locales; siempre será de escritorio).
- Features nuevas de negocio (export m3u, OAuth, estadísticas) — quedan para después del rediseño.
- Cambiar el comportamiento de organización (carpetas, tags, historial funcionan igual).

## 2. Decisiones técnicas

| Decisión | Elección | Alternativas descartadas y por qué |
|---|---|---|
| Ventana + puente | **PyWebView** | Electron (requiere Node, pesado, integración Python pobre); Flet (widgets propios, menos skill transferible); NiceGUI/Eel (servidor local, empaquetado más frágil) |
| Frontend | **HTML/CSS/JS a mano, sin build** | React/Vite: burocracia innecesaria para 4 pestañas; complica el `.exe` |
| Lógica | **Reutilizar `core/` y completarlo** | Reescribir: tirar trabajo testeado sin razón |
| Empaquetado | **PyInstaller** (fase final) | — |

En Windows, PyWebView usa el runtime **WebView2** (motor de Edge) ya presente en
Windows 10/11. Riesgo principal del proyecto: que PyWebView/WebView2 funcione bien
en la máquina de Belén → se valida primero con un spike (ver fases).

## 3. Arquitectura (3 capas)

```
┌─────────────────────────────────────┐
│  web/  — Frontend (HTML/CSS/JS)     │  ← NUEVO: el diseño moderno, 4 vistas
├─────────────────────────────────────┤
│  api.py — Puente PyWebView          │  ← NUEVO (chico): expone métodos Python a JS
├─────────────────────────────────────┤
│  core/ — Lógica pura (Python)       │  ← SE REUTILIZA y se completa
└─────────────────────────────────────┘
```

- **`web/`**: `index.html` + `style.css` + `app.js`. Una sola página con 4 vistas
  (Cargar, Buscar & Confirmar, Resultado, Historial) que replican el flujo actual.
  Navegación tipo sidebar con íconos. Identidad visual: dark (#0c0c10 aprox.),
  acentos amarillo neón (#e8ff00) y rosa (#ff3c6e), bordes redondeados, tipografía
  sans moderna.
- **`api.py`**: clase expuesta vía `webview.create_window(..., js_api=...)`.
  Métodos = las operaciones que hoy disparan los botones de tkinter:
  elegir carpeta, escanear/cargar tracks, buscar en Discogs, confirmar ítem,
  mover confirmados, deshacer, leer/filtrar historial, exportar CSV,
  abrir en Explorer, abrir Beatport, leer/guardar config.
  JS llama `window.pywebview.api.metodo(args)` → recibe JSON.
  Operaciones largas (búsqueda, mover) corren en hilos y reportan progreso
  con `evaluate_js` hacia el frontend.
- **`core/`**: ya existen `parsing.py`, `genres.py`, `organizer.py` (21 tests).
  Falta extraer de `belapp.py`: `discogs.py` (búsqueda + rate limit + retry por
  artista), `metadata.py` (read/write ID3 y FLAC), `history.py` (historial JSON +
  detección de duplicados), `config.py` (config.json). Cada módulo nuevo llega con
  sus tests.

## 4. Comportamientos que se preservan (paridad funcional)

Carga (tracks sueltos / carpeta EP-álbum / escaneo, tope `MAX_ITEMS`), detección de
duplicados contra historial (aviso, no bloqueo), búsqueda Discogs con rate limit y
reintento por artista, marcado rojo "sin match" (automático + manual), botón
Beatport, edición manual de género/sello/año con preview de ruta, mover con
escritura de tags, los movidos desaparecen de la lista, deshacer último movimiento
(restaura archivos y limpia registros), TXT por período, historial persistente con
búsqueda, CSV, menú contextual y abrir en carpeta, y persistencia de config
(token + carpeta base).

## 5. Fases de implementación

1. **Ordenar git** — consolidar para que la carpeta de trabajo sea versionable en
   privado (hoy es el repo público que ignora el código → sin checkpoints posibles).
   La vidriera pública queda como repo aparte.
2. **Spike PyWebView** — instalar, ventana "hola mundo" con llamada JS→Python ida y
   vuelta. Valida el único riesgo técnico desconocido. Si falla en esta máquina,
   re-evaluamos herramienta antes de invertir más.
3. **Completar `core/`** — extraer `discogs.py`, `metadata.py`, `history.py`,
   `config.py` de `belapp.py` con tests. `belapp.py` (tkinter) pasa a importarlos:
   sigue funcionando durante toda la transición.
4. **Frontend por vistas** — construir `web/` + `api.py` vista por vista, en este
   orden: Cargar → Buscar & Confirmar → Resultado → Historial. Cada vista se valida
   con Belén contra mockup antes de pasar a la siguiente.
5. **Empaquetar** — PyInstaller → `belapp.exe` standalone; smoke test en máquina
   limpia (la de su hermano, idealmente).

**Red de seguridad:** la app tkinter actual sigue intacta y usable hasta que la
nueva tenga paridad completa. Recién ahí se retira.

## 6. Manejo de errores

- Sin conexión / error de Discogs → mensaje claro en la vista de búsqueda
  (equivalente al status rojo actual), nunca crash.
- Operaciones de archivos: mismos guards actuales (origen inexistente, destino ya
  existe, permisos) reportados por ítem en la vista Resultado.
- Si WebView2 no está disponible al iniciar → mensaje con link de instalación de
  Microsoft (caso raro en Win 10/11, posible en máquinas viejas).

## 7. Testing

- `core/` nuevo: tests pytest por módulo (Discogs con respuestas simuladas, sin red;
  metadata con archivos temporales; history con JSON temporal).
- `api.py`: testeable instanciándolo sin ventana (es una clase Python común).
- Frontend: validación manual guiada por checklist de paridad (sección 4) por vista.
- Suite completa debe quedar verde en cada fase.

## 8. Criterios de éxito

1. Paridad funcional completa con la app tkinter (checklist sección 4).
2. Look moderno aprobado por Belén contra los mockups.
3. Suite de tests verde (los 21 actuales + los nuevos de core/).
4. `belapp.exe` corre en una máquina sin Python instalado.

# 🎧 BelApp — Music Organizer

> Organizador de música para DJs que enriquece archivos con metadata de **Discogs** y los ordena automáticamente en una estructura de carpetas por **género / sello / año**.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green)
![Discogs API](https://img.shields.io/badge/API-Discogs-333?logo=discogs)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)

> 🇬🇧 [English version](README.en.md)
>
> 🔒 _Repositorio de portfolio. El código fuente no se publica acá — está disponible **bajo pedido** para entrevistas._

---

## 📖 Sobre el proyecto

Como DJ, organizar cientos de tracks descargados es tedioso: hay que buscar el género, el sello y el año de cada uno, etiquetar los archivos y moverlos a la carpeta correcta. **BelApp** automatiza todo ese flujo en una sola aplicación de escritorio.

El flujo de trabajo es:

```
01 · Cargar  →  02 · Buscar & Confirmar  →  03 · Resultado  →  04 · Historial
```

1. **Cargar** tracks sueltos, carpetas de EP/Album o escanear una carpeta entera.
2. **Buscar en Discogs** la metadata de cada ítem y **validarla** comparando los datos del archivo con los del release antes de aceptar.
3. **Mover** los archivos confirmados a `Género / Sello / Año /`, escribiendo los tags ID3/FLAC en el camino.
4. **Consultar el historial** persistente de todo lo procesado.

---

## 📸 Capturas

> _Guardá tus capturas en una carpeta `assets/` y se mostrarán automáticamente acá._

| Cargar | Buscar & Confirmar |
|---|---|
| ![Pestaña Cargar](assets/01-cargar.png) | ![Pestaña Buscar](assets/02-buscar.png) |

| Resultado | Historial |
|---|---|
| ![Pestaña Resultado](assets/03-resultado.png) | ![Pestaña Historial](assets/04-historial.png) |

---

## ✨ Funcionalidades

### Organización
- 📥 Tres modos de carga: tracks individuales, carpeta de EP/Album, o escaneo recursivo de una carpeta.
- 🏷️ Lectura y escritura de tags **ID3** (MP3/WAV/AIFF) y **Vorbis** (FLAC) con `mutagen`.
- 📂 Movimiento automático a una estructura `Género / Sello / Año / archivo`.
- 🎚️ Normalización de géneros: mapea los estilos de Discogs a categorías propias de DJ (Deep & Progressive House, Melodic Techno, Psytrance, etc.).

### Integración con Discogs
- 🔍 Búsqueda contra la **API REST de Discogs** con autenticación por token.
- ⏱️ **Rate limiting** propio (pausa de 1.1s) para respetar el límite de 60 req/min de la API.
- 🔁 **Reintento automático**: si la búsqueda completa no devuelve resultados, reintenta usando solo el nombre del artista.
- 🧵 Búsquedas en **segundo plano** (threading) para que la interfaz nunca se congele.
- 🆚 **Panel de comparación** lado a lado: datos del archivo vs. datos de Discogs, para validar antes de mover.

### Seguridad y control
- ⚠️ **Detección de duplicados**: avisa (en la carga, en la validación y al mover) si un track ya figura en el historial.
- ⮌ **Deshacer último movimiento**: devuelve los archivos a su ubicación original y limpia los registros asociados.
- 🚦 **Límite por tanda** configurable para evitar bloqueos de UI y mantener el flujo manejable.

### Persistencia
- 💾 `config.json` recuerda el token y la carpeta base entre sesiones.
- 📝 Genera listas `.txt` acumulativas por período (ej. `belapp_2026_06.txt`).
- 🗂️ **Historial persistente** (`historial.json`) con artista, track, género, sello, año, fecha y destino.
- 🔎 Pestaña de historial con búsqueda en vivo, **exportación a CSV**, menú contextual (click derecho) y "abrir en carpeta".

### Experiencia de usuario
- 🎨 Interfaz oscura con estética neón, tipografía monoespaciada y efectos *hover*.
- 🔑 Botón "Obtener token" que abre el navegador en la página de Discogs.

---

## 🛠️ Stack técnico

| Categoría | Tecnología |
|---|---|
| **Lenguaje** | Python 3 |
| **Interfaz gráfica** | Tkinter / ttk |
| **Cliente HTTP / API** | `requests` (API REST de Discogs) |
| **Metadata de audio** | `mutagen` (ID3 y FLAC) |
| **Concurrencia** | `threading` (llamadas no bloqueantes) |
| **Sistema de archivos** | `pathlib`, `shutil` |
| **Persistencia / datos** | `json`, `csv` |
| **Utilidades** | `re` (parsing), `webbrowser`, `datetime` |

---

## 🚀 Instalación y uso

### Requisitos
```bash
pip install requests mutagen pywebview openpyxl
```

### Ejecutar
```bash
python main.py
```
> La interfaz moderna (web-style, sobre PyWebView) se ejecuta con `python main.py`.
> La versión original en tkinter (`belapp.py`) se mantiene como referencia.

### Ejecutable standalone (sin instalar nada)
Se empaqueta con PyInstaller en un único `.exe` que corre en cualquier Windows
sin Python ni dependencias instaladas:
```bash
pyinstaller --noconfirm --onefile --windowed --name BelApp --add-data "web;web" main.py
```
El resultado queda en `dist/BelApp.exe`. La configuración (`config.json`) y el
historial (`historial.json`) se guardan junto al ejecutable.

### Configuración inicial (una sola vez)
1. Click en **🔑 Obtener token** → se abre Discogs en el navegador.
2. Generá un token (*Settings → Developers → Generate new token*) y pegalo en el campo **DISCOGS TOKEN**.
3. Elegí tu **carpeta base** de música.

Ambos quedan guardados en `config.json` automáticamente.

---

## 🏗️ Arquitectura

La aplicación es un único archivo organizado en capas claras:

- **Helpers puros** (sin estado): parsing de nombres, normalización de géneros, lectura/escritura de tags, construcción de rutas.
- **Capa de Discogs**: búsqueda con rate-limiting y parseo de resultados.
- **Clase `BelDJApp` (Tkinter)**: UI organizada en pestañas (`Notebook`), cada una con su método `_build_tab_*`, y la lógica de estado (ítems cargados, resultados, historial).

Decisiones de diseño destacadas:
- Las llamadas a la API y los movimientos de archivos corren en **hilos separados** y se comunican con la UI vía `self.after()` (patrón thread-safe de Tkinter).
- La detección de duplicados usa **normalización de nombres** (minúsculas + solo alfanumérico) para tolerar diferencias de formato.
- El "deshacer" registra los pares `origen → destino` de cada movimiento para poder revertirlos de forma segura, sin pisar archivos existentes.

---

## 📁 Estructura de archivos

```
Belapp/
├── belapp.py          # Aplicación completa (no incluida en este repo público)
├── config.json        # Token + carpeta base (se crea al usar)
├── historial.json     # Historial persistente (se crea al mover)
├── belapp_AAAA_MM.txt # Listas por período (se crean al mover)
└── README.md
```

> 🔒 **Sobre el código:** este repositorio es una vidriera de portfolio. El archivo
> `belapp.py` no se publica para proteger la autoría. Si querés revisar el código
> (por ejemplo, en un proceso de selección), escribime y te doy acceso.

---

## 💡 Skills demostradas

Este proyecto pone en práctica:

- **Integración con APIs REST de terceros** (autenticación, rate limiting, manejo de errores y reintentos).
- **Desarrollo de GUI** de escritorio con manejo de estado y navegación entre vistas.
- **Programación concurrente** para mantener la interfaz responsiva.
- **Procesamiento de archivos y metadata** binaria (tags de audio).
- **Persistencia de datos** en JSON/CSV y diseño de formatos propios.
- **Diseño de UX**: validación previa, prevención de errores (duplicados), recuperación (undo) y feedback claro al usuario.
- **Código mantenible**: separación de responsabilidades, helpers reutilizables, constantes configurables.

---

## 🔮 Mejoras futuras

- [ ] Carga de archivos en segundo plano con barra de progreso (para tandas grandes).
- [ ] Exportación de playlists `.m3u8` para importar en Traktor / Rekordbox.
- [ ] Visualización de la carátula del release de Discogs en el panel de comparación.
- [ ] Estadísticas del historial (tracks por género / sello / período).
- [ ] Flujo OAuth para obtención automática del token.

---

## 👤 Autora

**Belén Egaña** — DJ y desarrolladora.

Proyecto personal desarrollado para optimizar el flujo real de organización de una biblioteca musical de DJ.

---

*Desarrollado con Python 🐍 · Metadata por [Discogs](https://www.discogs.com/)*

# 🎧 BelApp — Music Organizer

> A music organizer for DJs that enriches audio files with **Discogs** metadata and automatically sorts them into a **genre / label / year** folder structure.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green)
![Discogs API](https://img.shields.io/badge/API-Discogs-333?logo=discogs)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)

> 🇪🇸 [Versión en español](README.md)
>
> 🔒 _Portfolio repository. The source code is not published here — it is available **on request** for interviews._

---

## 📖 About the project

As a DJ, organizing hundreds of downloaded tracks is tedious: you have to look up each one's genre, label and year, tag the files, and move them to the right folder. **BelApp** automates that entire workflow in a single desktop application.

The workflow is:

```
01 · Load  →  02 · Search & Confirm  →  03 · Result  →  04 · History
```

1. **Load** loose tracks, EP/Album folders, or scan a whole folder.
2. **Search Discogs** for each item's metadata and **validate it** by comparing the file's data against the release before accepting.
3. **Move** the confirmed files into `Genre / Label / Year /`, writing ID3/FLAC tags along the way.
4. **Browse the persistent history** of everything processed.

---

## 📸 Screenshots

> _Drop your screenshots into an `assets/` folder and they'll show up here automatically._

| Load | Search & Confirm |
|---|---|
| ![Load tab](assets/01-cargar.png) | ![Search tab](assets/02-buscar.png) |

| Result | History |
|---|---|
| ![Result tab](assets/03-resultado.png) | ![History tab](assets/04-historial.png) |

---

## ✨ Features

### Organization
- 📥 Three loading modes: individual tracks, EP/Album folder, or recursive folder scan.
- 🏷️ Reading and writing of **ID3** (MP3/WAV/AIFF) and **Vorbis** (FLAC) tags via `mutagen`.
- 📂 Automatic move into a `Genre / Label / Year / file` structure.
- 🎚️ Genre normalization: maps Discogs styles to custom DJ categories (Deep & Progressive House, Melodic Techno, Psytrance, etc.).

### Discogs integration
- 🔍 Search against the **Discogs REST API** with token authentication.
- ⏱️ Built-in **rate limiting** (1.1s throttle) to respect the API's 60 req/min limit.
- 🔁 **Automatic retry**: if the full search returns no results, it retries using the artist name only.
- 🧵 Searches run in the **background** (threading) so the UI never freezes.
- 🆚 **Side-by-side comparison panel**: file data vs. Discogs data, to validate before moving.

### Safety and control
- ⚠️ **Duplicate detection**: warns (on load, on validation, and on move) if a track is already in the history.
- ⮌ **Undo last move**: returns files to their original location and cleans up the associated records.
- 🚦 Configurable **per-batch limit** to avoid UI freezes and keep the workflow manageable.

### Persistence
- 💾 `config.json` remembers the token and base folder between sessions.
- 📝 Generates cumulative `.txt` lists per period (e.g. `belapp_2026_06.txt`).
- 🗂️ **Persistent history** (`historial.json`) with artist, track, genre, label, year, date and destination.
- 🔎 History tab with live search, **CSV export**, context menu (right-click) and "open in folder".

### User experience
- 🎨 Dark neon-themed interface, monospaced typography and *hover* effects.
- 🔑 "Get token" button that opens the browser on the Discogs page.

---

## 🛠️ Tech stack

| Category | Technology |
|---|---|
| **Language** | Python 3 |
| **GUI** | Tkinter / ttk |
| **HTTP / API client** | `requests` (Discogs REST API) |
| **Audio metadata** | `mutagen` (ID3 and FLAC) |
| **Concurrency** | `threading` (non-blocking calls) |
| **File system** | `pathlib`, `shutil` |
| **Persistence / data** | `json`, `csv` |
| **Utilities** | `re` (parsing), `webbrowser`, `datetime` |

---

## 🚀 Installation and usage

### Requirements
```bash
pip install requests mutagen pywebview openpyxl
```

### Run
```bash
python main.py
```
> The modern web-style UI (built on PyWebView) runs with `python main.py`.
> The original tkinter version (`belapp.py`) is kept for reference.

### Initial setup (one time only)
1. Click **🔑 Get token** → Discogs opens in your browser.
2. Generate a token (*Settings → Developers → Generate new token*) and paste it into the **DISCOGS TOKEN** field.
3. Choose your music **base folder**.

Both are saved to `config.json` automatically.

---

## 🏗️ Architecture

The application is a single file organized into clear layers:

- **Pure helpers** (stateless): filename parsing, genre normalization, tag read/write, path building.
- **Discogs layer**: search with rate limiting and result parsing.
- **`BelDJApp` class (Tkinter)**: UI organized into tabs (`Notebook`), each with its own `_build_tab_*` method, plus state logic (loaded items, results, history).

Notable design decisions:
- API calls and file moves run in **separate threads** and communicate with the UI via `self.after()` (Tkinter's thread-safe pattern).
- Duplicate detection uses **name normalization** (lowercase + alphanumeric only) to tolerate formatting differences.
- The undo feature records the `source → destination` pairs of each move so they can be reverted safely, without overwriting existing files.

---

## 📁 File structure

```
Belapp/
├── belapp.py          # Full application (not included in this public repo)
├── config.json        # Token + base folder (created on use)
├── historial.json     # Persistent history (created on move)
├── belapp_YYYY_MM.txt # Per-period lists (created on move)
└── README.md
```

> 🔒 **About the code:** this repository is a portfolio showcase. The `belapp.py`
> file is not published, to protect authorship. If you'd like to review the code
> (e.g. during a hiring process), reach out and I'll grant access.

---

## 💡 Skills demonstrated

This project puts into practice:

- **Third-party REST API integration** (authentication, rate limiting, error handling and retries).
- **Desktop GUI development** with state management and navigation between views.
- **Concurrent programming** to keep the interface responsive.
- **File and binary metadata processing** (audio tags).
- **Data persistence** in JSON/CSV and design of custom formats.
- **UX design**: pre-move validation, error prevention (duplicates), recovery (undo) and clear user feedback.
- **Maintainable code**: separation of concerns, reusable helpers, configurable constants.

---

## 🔮 Future improvements

- [ ] Background file loading with a progress bar (for large batches).
- [ ] `.m3u8` playlist export for importing into Traktor / Rekordbox.
- [ ] Display the Discogs release artwork in the comparison panel.
- [ ] History statistics (tracks per genre / label / period).
- [ ] OAuth flow for automatic token retrieval.

---

## 👤 Author

**Belén Egaña** — DJ and developer.

A personal project built to streamline the real-world workflow of organizing a DJ's music library.

---

*Built with Python 🐍 · Metadata by [Discogs](https://www.discogs.com/)*

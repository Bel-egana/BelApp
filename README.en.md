# 🎧 BelApp — Music Organizer

> A music organizer for DJs that enriches files with **Discogs** metadata, validates the tags and automatically sorts everything into a `genre / label / year` folder structure — and also generates playlists for **Traktor**.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![PyWebView](https://img.shields.io/badge/GUI-PyWebView%20%2B%20HTML%2FCSS%2FJS-8a2be2)
![Discogs API](https://img.shields.io/badge/API-Discogs-333?logo=discogs)
![Tests](https://img.shields.io/badge/tests-122%20passing-brightgreen)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)

> 🇦🇷 [Versión en español](README.md)

---

## 📖 About the project

As a DJ, organizing hundreds of downloaded tracks is tedious: you have to look up each one's genre, label and year, tag the files and move them to the right folder. **BelApp** automates that entire workflow in a single desktop app.

The workflow is:

```
01 · Load  →  02 · Search & Confirm  →  03 · Result  →  04 · History
```

1. **Load** individual tracks, EP/Album folders, or scan a whole folder.
2. **Search Discogs** for each item's metadata and **validate** it by comparing the file's data with the release before accepting.
3. **Move** confirmed files into `Genre / Label / Year /`, writing the ID3/FLAC tags along the way.
4. **Browse the persistent history** of everything processed, and **generate playlists** for Traktor.

---

## 📸 Screenshots

**Search & Confirm** — Discogs search, metadata validation and destination preview:

![Search & Confirm](docs/screenshots/buscar-confirmar.png)

**History** — persistent log of everything processed, with search, filters and pagination:

![History](docs/screenshots/historial.png)

---

## ✨ Features

### Organization
- 📥 Three load modes: individual tracks, EP/Album folder, or folder scan (skipping year folders that are already organized).
- 🏷️ Reading and writing **ID3** (MP3/WAV/AIFF) and **Vorbis** (FLAC) tags with `mutagen`.
- 📂 Automatic move into a `Genre / Label / Year / file` structure, with guards (never overwrites destinations, only removes empty folders — **never deletes audio**).
- 🎚️ **Genre normalizer with manual review**: maps raw styles to custom DJ categories, then shows a list where you review/fix each track (checkbox + dropdown) or assign in bulk before applying.
- 🔤 **Similar-label detection**: while typing the label, it warns if a similar folder already exists (typos, suffixes like *Music/Records*) to avoid duplicates.

### Discogs integration
- 🔍 Search against the **Discogs REST API** with token authentication.
- ⏱️ Built-in **rate limiting** (1.1s pause) to respect the API limit.
- 🔁 **Automatic retry**: if the full search returns nothing, it retries using only the artist name.
- 🧵 **Background** searches so the UI never freezes.
- 🆚 **Side-by-side comparison** panel: file data vs. Discogs data, to validate before moving.

### Playlists for Traktor
- 🎧 Generates one **`.m3u8` per Genre + Year** by reading the library's tags (by reference, without moving or copying audio), ready to import into Traktor.

### Safety and control
- ⚠️ **Duplicate detection**: warns (on load, on validation and on move) if a track is already in the history.
- ⮌ **Undo last move**: returns the files to their original location and clears the associated records.
- 🚦 **Per-batch limit** to avoid UI freezes and keep the flow manageable.

### Persistence and history
- 💾 `config.json` remembers the token and base folder between sessions.
- 🗂️ **Persistent history** (`historial.json`) with artist, track, genre, label, year, date and destination.
- 🔎 History tab with **live search**, genre filter, **pagination**, **Excel export**, context menu (right-click) and "open in folder".

---

## 🛠️ Tech stack

| Category | Technology |
|---|---|
| **Language** | Python 3 |
| **UI** | **PyWebView** (native window) + **HTML / CSS / JavaScript** (web-style UI) |
| **HTTP client / API** | `requests` (Discogs REST API) |
| **Audio metadata** | `mutagen` (ID3 and FLAC) |
| **Testing** | `pytest` — **122 tests** over the pure logic |
| **Packaging** | `PyInstaller` (standalone `.exe`) |
| **File system** | `pathlib`, `shutil` |
| **Persistence / export** | `json`, `openpyxl` (Excel) |
| **Utilities** | `re` (parsing), `webbrowser`, `datetime` |

---

## 🚀 Install and run

### Requirements
```bash
pip install requests mutagen pywebview openpyxl
```

### Run
```bash
python main.py
```
> The original tkinter version (`belapp.py`) is kept in the repo **for reference only** — the current app is the PyWebView one.

### Tests
```bash
python -m pytest tests/ -q
```

### Standalone executable (nothing to install)
Packaged with PyInstaller into a single `.exe` that runs on any Windows without Python or dependencies:
```bash
pyinstaller --noconfirm --onefile --windowed --name BelApp --add-data "web;web" main.py
```
The result lands in `dist/BelApp.exe`. Config (`config.json`) and history (`historial.json`) are stored next to the executable.

### Initial setup (once)
1. Click **🔑 Get token** → Discogs opens in the browser.
2. Generate a token (*Settings → Developers → Generate new token*) and paste it into the **Discogs token** field.
3. Pick your music **base folder**.

---

## 🏗️ Architecture

The app is split into **3 layers** with clear responsibilities — the important stuff lives in `core/`, isolated from the UI and **tested**:

- **`web/`** (`index.html` + `style.css` + `app.js`): the modern interface (4 views). UI state lives in JS.
- **`api.py`**: the `Api` class = PyWebView bridge. The frontend calls it as `pywebview.api.method()`. Thin glue.
- **`core/`**: **pure, tested logic** (no UI): filename parsing, genre mapping/normalization, tag read/write, path building, Discogs client, history, playlists, similar-label detection.

Notable design decisions:
- All the important logic is **pure and tested** (`core/`), so it can be verified without launching the UI.
- Discogs searches and file moves are **non-blocking**, so the UI never freezes.
- Duplicate detection uses **name normalization** (lowercase + alphanumeric only) to tolerate formatting differences.
- Undo records the `source → destination` pairs of each move to revert them safely, without overwriting existing files.
- **Audio files are never deleted**: only moved, and only empty folders are removed.

---

## 📁 Repo structure

```
Belapp/
├── main.py            # Entry point (opens the PyWebView window)
├── api.py             # PyWebView bridge (Api class) called by the frontend
├── core/              # Pure, tested logic (no UI)
│   ├── parsing.py     #   file/folder names → metadata
│   ├── genres.py      #   genre mapping and normalization
│   ├── metadata.py    #   ID3/FLAC tag read/write
│   ├── discogs.py     #   API client (rate-limit + fallback)
│   ├── organizer.py   #   destination path building
│   ├── history.py     #   history + duplicate detection
│   ├── labels.py      #   similar-label detection
│   ├── playlists.py   #   .m3u8 playlist building for Traktor
│   └── ...
├── web/               # web-style UI (index.html, style.css, app.js)
├── tests/             # pytest suite (122 tests)
├── belapp.py          # Old tkinter version (reference only)
└── README.md
```

> `config.json` (token) and `historial.json` are created when using the app and are **not versioned**.

---

## 💡 Skills demonstrated

This project puts into practice:

- **Third-party REST API integration** (authentication, rate limiting, error handling and retries).
- **Layered architecture** with pure logic isolated from the UI, and **testing with pytest** (TDD).
- **Modern desktop GUI development** (PyWebView + HTML/CSS/JS) with state management and view navigation.
- **File and binary metadata processing** (audio tags) with safe operations (guards, undo).
- **Data persistence** in JSON and Excel export.
- **UX design**: up-front validation, error prevention (duplicates, similar labels), recovery (undo) and clear feedback.
- **Packaging and distribution** (PyInstaller → standalone `.exe`).

---

## 🔮 Future improvements

- [ ] Background file loading with a progress bar (for large batches).
- [ ] Showing the Discogs release cover art in the comparison panel.
- [ ] History statistics (tracks per genre / label / year).
- [ ] OAuth flow for automatic token retrieval.
- [ ] Deriving the year from the folder when it's missing from the tag (for playlists).

---

## 👤 Author

**Belén Egaña** — DJ and developer.

Personal project built to optimize the real workflow of organizing a DJ's music library.

---

*Built with Python 🐍 · Metadata by [Discogs](https://www.discogs.com/)*

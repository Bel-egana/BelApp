"""
BelApp — Music Organizer
Flujo: Cargar → Buscar en Discogs → Confirmar → Mover
Requiere: pip install requests mutagen
"""

import re, time, shutil, threading, tkinter as tk, json, webbrowser
from urllib.parse import quote
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
import requests

# Lógica pura, separada en el paquete core/ (testeada en tests/)
from core.parsing import parse_filename, parse_folder_name
from core.genres import format_genre, BEL_GENRES
from core.organizer import build_path

CONFIG_PATH  = Path(__file__).parent / 'config.json'
HISTORY_PATH = Path(__file__).parent / 'historial.json'

try:
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPUB, TCON, TDRC, ID3NoHeaderError
    from mutagen.flac import FLAC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

# ─── CONSTANTES ────────────────────────────────────────────────────────────────
AUDIO_EXTS   = {'.mp3', '.wav', '.aiff', '.flac', '.m4a'}
IMAGE_EXTS   = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
DISCOGS_BASE = 'https://api.discogs.com'
MAX_ITEMS    = 25   # Tope de ítems por tanda: evita freezes al leer tags y mantiene
                    # el flujo de validación manejable. Cambialo a gusto.

# BEL_GENRES y GENRE_MAP viven ahora en core/genres.py (se importan arriba).

# Colores — textos claros, nunca grises oscuros
BG      = '#0a0a0a'
SURFACE = '#131313'
SURF2   = '#1c1c1c'
BORDER  = '#2a2a2a'
ACCENT  = '#e8ff00'   # amarillo neón
ACCENT2 = '#ff3c6e'   # rosa
TEXT    = '#e8e8e8'   # blanco suave — texto principal
LABEL   = '#bbbbbb'   # labels de campos
DIM     = '#888888'   # texto secundario
SUCCESS = '#00ffa3'
WARNING = '#ffaa00'
INFO    = '#5599ff'
PURPLE  = '#a78bfa'

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def is_audio(n): return Path(n).suffix.lower() in AUDIO_EXTS
def is_image(n): return Path(n).suffix.lower() in IMAGE_EXTS

def lighten(hex_color, amount=0.18):
    """Devuelve una versión más clara del color (para hover)."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f'#{r:02x}{g:02x}{b:02x}'

# format_genre, parse_filename, parse_folder_name y build_path viven ahora
# en el paquete core/ (parsing.py, genres.py, organizer.py) — importados arriba.

def read_id3(filepath):
    tags = {}
    if not MUTAGEN_OK: return tags
    try:
        ext = filepath.suffix.lower()
        if ext in ('.mp3', '.wav', '.aiff'):
            audio = ID3(str(filepath))
            def g(k):
                v = audio.get(k)
                return str(v.text[0]).strip() if v and hasattr(v,'text') and v.text else ''
            tags = {'artist': g('TPE1') or g('TPE2'), 'title': g('TIT2'),
                    'album': g('TALB'), 'label': g('TPUB'), 'genre': g('TCON'),
                    'year': str(g('TDRC') or g('TYER'))[:4]}
        elif ext == '.flac':
            audio = FLAC(str(filepath))
            def gf(k): return (audio.get(k.lower()) or [''])[0].strip()
            tags = {'artist': gf('artist'), 'title': gf('title'), 'album': gf('album'),
                    'label': gf('organization') or gf('label'), 'genre': gf('genre'),
                    'year': (gf('date') or gf('year'))[:4]}
    except Exception: pass
    return {k: v for k, v in tags.items() if v}

def write_id3_tags(filepath, artist, title, album, label, genre, year):
    if not MUTAGEN_OK: return False
    try:
        ext = filepath.suffix.lower()
        if ext in ('.mp3', '.wav', '.aiff'):
            try:    tags = ID3(str(filepath))
            except ID3NoHeaderError: tags = ID3()
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
            audio['title'] = title; audio['artist'] = artist
            audio['album'] = album; audio['organization'] = label
            audio['genre'] = genre; audio['date'] = year
            audio.save(); return True
    except Exception: return False
    return False

# ─── DISCOGS ───────────────────────────────────────────────────────────────────
_last_discogs = 0

def discogs_search(query, token, limit=10):
    global _last_discogs
    wait = max(0, 1.1 - (time.time() - _last_discogs))
    if wait > 0: time.sleep(wait)
    _last_discogs = time.time()
    headers = {'User-Agent': 'BelApp/1.0',
               'Authorization': f'Discogs token={token}'}
    r = requests.get(f'{DISCOGS_BASE}/database/search',
                     params={'q': query, 'type': 'release', 'per_page': limit},
                     headers=headers, timeout=12)
    r.raise_for_status()
    return r.json().get('results', [])

def parse_discogs_result(res):
    genres = res.get('genre') or []
    styles = res.get('style') or []
    labels = res.get('label') or []
    year   = str(res.get('year', '') or '')[:4]
    title  = res.get('title', '')
    genre_raw = styles[0] if styles else (genres[0] if genres else '')
    genre = format_genre(genre_raw) or genre_raw
    label = labels[0] if labels else ''
    label = re.sub(r'\s*[-–]\s*\w*\d+\w*$', '', label).strip()
    artist = ''
    if ' - ' in title:
        parts = title.split(' - ', 1)
        artist = parts[0].strip()
        title  = parts[1].strip()
    return {'artist': artist, 'title': title, 'genre': genre,
            'label': label, 'year': year,
            'format': ', '.join(res.get('format') or [])}

# ─── APP ───────────────────────────────────────────────────────────────────────
class BelDJApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BelApp — Music Organizer')
        self.configure(bg=BG)
        self.geometry('1100x720')
        self.minsize(900, 600)
        self.resizable(True, True)

        self.items             = []
        self.base_path         = tk.StringVar(value=r'D:\Bel\Música')
        self.discogs_token     = tk.StringVar(value='')
        self._load_config()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self._log_entries      = []
        self._moved_paths      = []
        self._session_paths    = []
        self._current_item_idx = 0
        self._discogs_results  = []
        self.history           = []
        self._session_history  = []
        self._last_move        = []
        self._moved_item_ids   = []
        self._next_id          = 0
        self._load_history()

        # Nombre del período activo (ej: "2026_06")
        now = datetime.now()
        period = f"{now.year}_{'06' if now.month <= 6 else '12'}"
        self.playlist_name = tk.StringVar(value=period)

        self._style_ttk()
        self._build_ui()
        # Cargar rutas guardadas del período activo
        self.after(500, self._load_existing_txt)

    # ── ESTILOS ───────────────────────────────────────────────────────────────
    def _style_ttk(self):
        s = ttk.Style(self)
        s.theme_use('default')
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background=SURF2, foreground=LABEL,
                    font=('Consolas', 10), padding=[14, 7], borderwidth=0)
        s.map('TNotebook.Tab',
              background=[('selected', SURFACE)],
              foreground=[('selected', ACCENT)])
        s.configure('Treeview', background=SURFACE, foreground=TEXT,
                    fieldbackground=SURFACE, borderwidth=0,
                    font=('Consolas', 10), rowheight=26)
        s.configure('Treeview.Heading', background=SURF2, foreground=LABEL,
                    font=('Consolas', 9, 'bold'), borderwidth=0)
        s.map('Treeview',
              background=[('selected', '#1a2e1a')],
              foreground=[('selected', ACCENT)])
        s.configure('TScrollbar', background=SURF2, troughcolor=BG,
                    borderwidth=0, arrowcolor=LABEL)
        s.configure('TCombobox', fieldbackground=SURF2, background=SURF2,
                    foreground=TEXT, selectbackground=SURF2,
                    selectforeground=TEXT)
        s.map('TCombobox', fieldbackground=[('readonly', SURF2)])

    # ── UI PRINCIPAL ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header fijo
        hdr = tk.Frame(self, bg=BG, pady=14, padx=24)
        hdr.pack(fill='x', side='top')
        tk.Label(hdr, text='Bel', font=('Consolas', 26, 'bold'),
                 fg=ACCENT, bg=BG).pack(side='left')
        tk.Label(hdr, text='App', font=('Consolas', 26, 'bold'),
                 fg=ACCENT2, bg=BG).pack(side='left')
        tk.Label(hdr, text='   Music Organizer',
                 font=('Consolas', 11), fg=LABEL, bg=BG).pack(side='left', pady=6)
        tk.Label(hdr, text='Discogs Search Edition',
                 font=('Consolas', 9), fg=PURPLE, bg=BG).pack(side='right', pady=8)
        tk.Frame(self, bg=BORDER, height=1).pack(fill='x', side='top')

        # Notebook ocupa todo el resto
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill='both', expand=True, side='top')

        self.tab_load    = tk.Frame(self.nb, bg=BG)
        self.tab_search  = tk.Frame(self.nb, bg=BG)
        self.tab_done    = tk.Frame(self.nb, bg=BG)
        self.tab_history = tk.Frame(self.nb, bg=BG)
        self.nb.add(self.tab_load,    text='  01 · Cargar  ')
        self.nb.add(self.tab_search,  text='  02 · Buscar & Confirmar  ')
        self.nb.add(self.tab_done,    text='  03 · Resultado  ')
        self.nb.add(self.tab_history, text='  04 · Historial  ')
        self._history_tab_idx = self.nb.index(self.tab_history)
        self.nb.bind('<<NotebookTabChanged>>', self._on_tab_change)
        self._allowed_tab = 0

        self._build_tab_load()
        self._build_tab_search()
        self._build_tab_done()
        self._build_tab_history()

    def _on_tab_change(self, e):
        cur = self.nb.index('current')
        if cur == self._history_tab_idx:   # Historial: siempre accesible
            return
        if cur > self._allowed_tab:
            self.nb.select(self._allowed_tab)

    def _go_tab(self, idx):
        self._allowed_tab = idx
        self.nb.select(idx)

    # ── TAB 1: CARGAR ─────────────────────────────────────────────────────────
    def _build_tab_load(self):
        f = self.tab_load

        # Barra inferior PRIMERO (side=bottom) → siempre visible
        bb = tk.Frame(f, bg=SURFACE, pady=6, padx=16)
        bb.pack(fill='x', side='bottom')
        self.lbl_count = tk.Label(bb, text='Ningún ítem cargado',
                                   font=('Consolas', 10), fg=LABEL, bg=SURFACE)
        self.lbl_count.pack(side='left')
        self.btn_go = self._btn(bb, '▶  Continuar',
                                 self._go_to_search, accent=True,
                                 side='right', state='disabled')

        # Contenido scrollable arriba
        top = tk.Frame(f, bg=BG)
        top.pack(fill='both', expand=True, side='top')

        # Config rows
        cf = tk.Frame(top, bg=SURFACE, pady=10, padx=16)
        cf.pack(fill='x', padx=20, pady=(14, 3))
        tk.Label(cf, text='CARPETA BASE:', font=('Consolas', 9),
                 fg=LABEL, bg=SURFACE).pack(side='left')
        tk.Entry(cf, textvariable=self.base_path, font=('Consolas', 11),
                 fg=ACCENT, bg=SURF2, insertbackground=ACCENT,
                 relief='flat', bd=4).pack(side='left', padx=10, fill='x', expand=True)
        self._btn(cf, 'Cambiar', self._pick_base, side='right')

        tf = tk.Frame(top, bg=SURF2, pady=8, padx=16)
        tf.pack(fill='x', padx=20, pady=3)
        tk.Label(tf, text='DISCOGS TOKEN:', font=('Consolas', 9),
                 fg=LABEL, bg=SURF2).pack(side='left')
        self.entry_token = tk.Entry(tf, textvariable=self.discogs_token,
                                     font=('Consolas', 10), fg=PURPLE,
                                     bg='#0d0d1a', insertbackground=PURPLE,
                                     relief='flat', bd=4, show='•')
        self.entry_token.pack(side='left', padx=8, fill='x', expand=True)
        self._btn(tf, '👁', self._toggle_token, side='left')
        self._btn(tf, '🔑 Obtener token', self._open_token_page,
                  color=PURPLE, side='left', padx=(6, 0))
        tk.Label(tf, text='Generás el token 1 vez, lo pegás acá y queda guardado',
                 font=('Consolas', 8), fg=DIM, bg=SURF2).pack(side='left', padx=8)

        nf = tk.Frame(top, bg='#0d1a0d', pady=8, padx=14)
        nf.pack(fill='x', padx=20, pady=6)
        tk.Label(nf,
                 text='Cargá tus tracks o carpetas de EP/Album.\n'
                      'Después buscás en Discogs, elegís el resultado correcto y confirmás.',
                 font=('Consolas', 10), fg='#99cc99', bg='#0d1a0d',
                 justify='left').pack(anchor='w')

        bf = tk.Frame(top, bg=BG)
        bf.pack(fill='x', padx=20, pady=6)
        self._btn(bf, '+ Tracks sueltos',     self._add_tracks,  accent=True,  side='left')
        self._btn(bf, '+ Carpeta EP / Album', self._add_folder,  color=PURPLE, side='left', padx=(8,0))
        self._btn(bf, '📂 Escanear carpeta',  self._scan_folder, color=INFO,   side='left', padx=(8,0))
        self._btn(bf, 'Limpiar',              self._clear_items, danger=True,  side='right')

        lf = tk.Frame(top, bg=BG)
        lf.pack(fill='both', expand=True, padx=20, pady=(0, 4))
        cols = ('tipo', 'nombre', 'artista', 'tags')
        self.tree_load = ttk.Treeview(lf, columns=cols, show='headings', selectmode='browse')
        self.tree_load.heading('tipo',    text='TIPO')
        self.tree_load.heading('nombre',  text='NOMBRE')
        self.tree_load.heading('artista', text='ARTISTA DETECTADO')
        self.tree_load.heading('tags',    text='TAGS ID3')
        self.tree_load.column('tipo',    width=80,  stretch=False)
        self.tree_load.column('nombre',  width=400)
        self.tree_load.column('artista', width=220)
        self.tree_load.column('tags',    width=140, stretch=False)
        self.tree_load.tag_configure('track', foreground=TEXT)
        self.tree_load.tag_configure('album', foreground=PURPLE)
        self.tree_load.tag_configure('hasid3', foreground=SUCCESS)
        self.tree_load.tag_configure('dup', foreground=WARNING)
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.tree_load.yview)
        self.tree_load.configure(yscrollcommand=sb.set)
        self.tree_load.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.tree_load.bind('<Delete>',    self._del_selected)
        self.tree_load.bind('<BackSpace>', self._del_selected)

    # ── TAB 2: BUSCAR & CONFIRMAR ─────────────────────────────────────────────
    def _build_tab_search(self):
        f = self.tab_search

        # ── Barra de navegación FIJA en el fondo ──────────────────────────
        nav = tk.Frame(f, bg=SURFACE, pady=6, padx=12)
        nav.pack(fill='x', side='bottom')

        self._btn(nav, '← Volver', lambda: self._go_tab(0), side='left')
        self.lbl_progress = tk.Label(nav, text='', font=('Consolas', 9),
                                      fg=LABEL, bg=SURFACE)
        self.lbl_progress.pack(side='left', padx=14)

        # Botones a la derecha — en orden de izquierda a derecha
        self.btn_move_all = self._btn(nav, '▶ Mover',
                                       self._move_all, color=SUCCESS,
                                       side='right', state='disabled')
        self._btn(nav, '✓ Confirmar', self._confirm_current,
                  accent=True, side='right', padx=(0, 6))
        self._btn(nav, '✓ Usar', self._use_discogs_result,
                  color=INFO, side='right', padx=(0, 6))
        self._btn(nav, '✗ Sin match', self._flag_current,
                  color=ACCENT2, side='right', padx=(0, 6))
        self._btn(nav, 'Saltar', self._skip_item,
                  side='right', padx=(0, 6))

        # ── Cuerpo principal ──────────────────────────────────────────────
        body = tk.Frame(f, bg=BG)
        body.pack(fill='both', expand=True, side='top')

        # Panel izquierdo — lista de ítems, ancho fijo
        left = tk.Frame(body, bg=BG, width=210)
        left.pack(side='left', fill='y', padx=(12, 0), pady=12)
        left.pack_propagate(False)

        tk.Label(left, text='ÍTEMS', font=('Consolas', 9),
                 fg=LABEL, bg=BG).pack(anchor='w', pady=(0, 4))
        self.list_items = tk.Listbox(
            left, bg=SURFACE, fg=TEXT, font=('Consolas', 10),
            selectbackground='#1a2e1a', selectforeground=ACCENT,
            relief='flat', bd=0, activestyle='none',
            highlightthickness=1,
            highlightcolor=BORDER, highlightbackground=BORDER)
        self.list_items.pack(fill='both', expand=True)
        self.list_items.bind('<<ListboxSelect>>', self._on_item_select)

        leg = tk.Frame(left, bg=BG)
        leg.pack(fill='x', pady=(6, 0))
        for color, lbl in [(SUCCESS,'✓ Confirmado'),
                           (WARNING,'⧖ Pendiente'),
                           (ACCENT2,'✗ Sin match / revisar')]:
            tk.Label(leg, text=lbl, font=('Consolas', 8),
                     fg=color, bg=BG).pack(anchor='w')

        # Panel derecho — búsqueda + resultados + datos
        right = tk.Frame(body, bg=BG)
        right.pack(side='left', fill='both', expand=True, padx=12, pady=12)

        self.lbl_current = tk.Label(right, text='← Seleccioná un ítem',
                                     font=('Consolas', 12, 'bold'),
                                     fg=ACCENT, bg=BG, anchor='w')
        self.lbl_current.pack(fill='x', pady=(0, 6))

        # Buscador
        sf = tk.Frame(right, bg=SURFACE, pady=8, padx=12)
        sf.pack(fill='x', pady=(0, 4))
        tk.Label(sf, text='BUSCAR EN DISCOGS:',
                 font=('Consolas', 9), fg=LABEL, bg=SURFACE).pack(anchor='w', pady=(0, 4))
        sr = tk.Frame(sf, bg=SURFACE)
        sr.pack(fill='x')
        self.search_var = tk.StringVar()
        self.entry_search = tk.Entry(
            sr, textvariable=self.search_var,
            font=('Consolas', 11), fg=TEXT, bg=SURF2,
            insertbackground=ACCENT, relief='flat', bd=4)
        self.entry_search.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.entry_search.bind('<Return>', lambda e: self._do_search())
        self.btn_search_disc = self._btn(sr, '🔍 Buscar', self._do_search,
                                          accent=True, side='left')
        self._btn(sr, '🔊 Beatport', self._search_beatport,
                  color='#a9ff1f', side='left', padx=(6, 0))
        self.lbl_search_status = tk.Label(sf, text='',
                                           font=('Consolas', 9), fg=LABEL, bg=SURFACE)
        self.lbl_search_status.pack(anchor='w', pady=(4, 0))

        # ── Panel DATOS PARA MOVER — anclado al fondo (altura fija, nunca se corta) ─
        conf = tk.Frame(right, bg=SURFACE, pady=10, padx=14)
        conf.pack(side='bottom', fill='x', pady=(6, 0))

        tk.Label(conf, text='DATOS PARA MOVER:',
                 font=('Consolas', 9), fg=LABEL, bg=SURFACE).pack(anchor='w', pady=(0, 6))
        fr = tk.Frame(conf, bg=SURFACE)
        fr.pack(fill='x')

        self.conf_genre = tk.StringVar()
        self.conf_label = tk.StringVar()
        self.conf_year  = tk.StringVar()

        cg = tk.Frame(fr, bg=SURFACE)
        cg.pack(side='left', padx=(0, 12))
        tk.Label(cg, text='GÉNERO', font=('Consolas', 8),
                 fg=LABEL, bg=SURFACE).pack(anchor='w')
        self.combo_genre = ttk.Combobox(
            cg, textvariable=self.conf_genre,
            values=BEL_GENRES, font=('Consolas', 11),
            width=24, state='normal')
        self.combo_genre.pack()

        for lbl_txt, var, w in [('SELLO', self.conf_label, 18),
                                  ('AÑO',   self.conf_year,  6)]:
            c = tk.Frame(fr, bg=SURFACE)
            c.pack(side='left', padx=(0, 12))
            tk.Label(c, text=lbl_txt, font=('Consolas', 8),
                     fg=LABEL, bg=SURFACE).pack(anchor='w')
            tk.Entry(c, textvariable=var, font=('Consolas', 11),
                     fg=TEXT, bg=SURF2, insertbackground=ACCENT,
                     relief='flat', bd=4, width=w).pack()

        self.lbl_path_preview = tk.Label(
            conf, text='→ completá género, sello y año',
            font=('Consolas', 9), fg=DIM, bg=SURFACE, anchor='w')
        self.lbl_path_preview.pack(fill='x', pady=(6, 0))

        for v in [self.conf_genre, self.conf_label, self.conf_year]:
            v.trace_add('write', self._update_path_preview)

        # ── Resultados de Discogs — ocupa el espacio del medio (con scroll) ───
        tk.Label(right, text='RESULTADOS DE DISCOGS:',
                 font=('Consolas', 9), fg=LABEL, bg=BG).pack(anchor='w', pady=(4, 2))
        rf = tk.Frame(right, bg=BG)
        rf.pack(fill='both', expand=True)

        cols = ('titulo', 'artista', 'genero', 'sello', 'año', 'formato')
        self.tree_discogs = ttk.Treeview(rf, columns=cols, show='headings',
                                          selectmode='browse', height=14)
        for col, txt, w in [('titulo','TÍTULO',200), ('artista','ARTISTA',150),
                             ('genero','GÉNERO',180), ('sello','SELLO',150),
                             ('año','AÑO',50), ('formato','FORMATO',110)]:
            self.tree_discogs.heading(col, text=txt)
            stretch = col not in ('año','formato')
            self.tree_discogs.column(col, width=w, stretch=stretch,
                                      minwidth=50 if not stretch else 80)
        self.tree_discogs.tag_configure('result', foreground=TEXT)
        self.tree_discogs.bind('<<TreeviewSelect>>', self._on_discogs_select)
        self.tree_discogs.bind('<Double-1>', lambda e: self._confirm_current())
        sb2 = ttk.Scrollbar(rf, orient='vertical', command=self.tree_discogs.yview)
        self.tree_discogs.configure(yscrollcommand=sb2.set)
        self.tree_discogs.pack(side='left', fill='both', expand=True)
        sb2.pack(side='right', fill='y')

    # ── TAB 3: RESULTADO ─────────────────────────────────────────────────────
    def _build_tab_done(self):
        f = self.tab_done

        # Barra inferior fija
        bb = tk.Frame(f, bg=SURFACE, pady=6, padx=12)
        bb.pack(fill='x', side='bottom')
        self._btn(bb, '↺ Nuevo', self._reset, accent=True, side='left')
        self.btn_undo = self._btn(bb, '⮌ Deshacer movimiento',
                                   self._undo_last_move, color=WARNING,
                                   side='left', padx=(8, 0), state='disabled')

        # Indicador de período y rutas acumuladas
        period_frame = tk.Frame(bb, bg=SURFACE)
        period_frame.pack(side='left', padx=(16, 0))
        tk.Label(period_frame, text='PERÍODO ACTIVO:',
                 font=('Consolas', 8), fg=LABEL, bg=SURFACE).pack(anchor='w')
        pf2 = tk.Frame(period_frame, bg=SURFACE)
        pf2.pack(fill='x')
        tk.Entry(pf2, textvariable=self.playlist_name,
                 font=('Consolas', 11), fg=ACCENT, bg=SURF2,
                 insertbackground=ACCENT, relief='flat', bd=3, width=10).pack(side='left')
        self._btn(pf2, '↺ Nuevo período', self._new_period,
                  color=WARNING, side='left', padx=(6, 0))
        self.lbl_txt_count = tk.Label(bb, text='',
                 font=('Consolas', 10), fg=SUCCESS, bg=SURFACE)
        self.lbl_txt_count.pack(side='right', padx=(0, 16))

        # Cards de resumen
        sc = tk.Frame(f, bg=BG)
        sc.pack(fill='x', padx=20, pady=(14, 8), side='top')
        self.sum_vars = {}
        for key, lbl in [('tracks','Tracks movidos'), ('albums','Albums/EPs'),
                          ('skipped','Salteados'), ('folders','Carpetas nuevas')]:
            card = tk.Frame(sc, bg=SURFACE, pady=8, padx=16)
            card.pack(side='left', padx=(0, 6))
            sv = tk.StringVar(value='0')
            self.sum_vars[key] = sv
            tk.Label(card, textvariable=sv,
                     font=('Consolas', 22, 'bold'), fg=ACCENT, bg=SURFACE).pack()
            tk.Label(card, text=lbl.upper(),
                     font=('Consolas', 8), fg=LABEL, bg=SURFACE).pack()

        # Log
        lf = tk.Frame(f, bg=BG)
        lf.pack(fill='both', expand=True, padx=20, pady=(0, 4), side='top')
        self.log_text = tk.Text(lf, bg=SURFACE, fg=TEXT,
                                 font=('Consolas', 10),
                                 relief='flat', bd=0, state='disabled', wrap='word')
        for tag, color in [('success', SUCCESS), ('error', ACCENT2),
                            ('info', INFO), ('album', PURPLE),
                            ('warn', WARNING), ('dim', DIM)]:
            self.log_text.tag_configure(tag, foreground=color)
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

    # ── BOTÓN HELPER ─────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, accent=False, danger=False,
             color=None, side='left', padx=(0, 0), state='normal'):
        if accent:   fg, bg = '#000',   ACCENT
        elif danger: fg, bg = ACCENT2,  SURF2
        elif color:  fg, bg = '#000',   color
        else:        fg, bg = TEXT,     SURF2
        hover = lighten(bg, 0.22)
        b = tk.Button(
            parent, text=text, command=cmd,
            font=('Consolas', 10, 'bold' if accent else 'normal'),
            fg=fg, bg=bg, activeforeground=fg, activebackground=hover,
            relief='flat', bd=0, padx=12, pady=5,
            cursor='hand2', state=state)
        b.pack(side=side, padx=padx)

        def _enter(e):
            if b['state'] != 'disabled': b.config(bg=hover)
        def _leave(e):
            if b['state'] != 'disabled': b.config(bg=bg)
        b.bind('<Enter>', _enter)
        b.bind('<Leave>', _leave)
        return b

    # ── CONFIG ────────────────────────────────────────────────────────────────
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

    def _on_close(self):
        self._save_config()
        self.destroy()

    # ── CARGAR ────────────────────────────────────────────────────────────────
    def _pick_base(self):
        d = filedialog.askdirectory(title='Elegí tu carpeta base')
        if d: self.base_path.set(d)

    def _toggle_token(self):
        self.entry_token.config(
            show='' if self.entry_token.cget('show') == '•' else '•')

    def _open_token_page(self):
        """Abre el navegador en la página de Discogs para generar el token."""
        try:
            webbrowser.open('https://www.discogs.com/settings/developers')
            messagebox.showinfo('Obtener token',
                'Se abrió Discogs en tu navegador.\n\n'
                '1. Iniciá sesión (si hace falta).\n'
                '2. Click en "Generate new token".\n'
                '3. Copiá el token y pegalo en el campo DISCOGS TOKEN.\n\n'
                'Queda guardado, no lo tenés que volver a hacer.')
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo abrir el navegador:\n{e}')

    def _make_item(self, type_, **kw):
        """Crea un dict de ítem con valores por defecto."""
        self._next_id += 1
        return {'id': self._next_id, 'type': type_,
                'status': 'pending', 'flag': '', 'genre': '', 'label': '',
                'year': '', 'destination': '', **kw}

    def _limit_reached(self):
        if len(self.items) >= MAX_ITEMS:
            messagebox.showinfo('Límite por tanda',
                f'Llegaste al máximo de {MAX_ITEMS} ítems por tanda.\n\n'
                'Procesá y mové estos, y después cargás los que falten.')
            return True
        return False

    def _add_tracks(self):
        files = filedialog.askopenfilenames(
            title='Elegí tracks',
            filetypes=[('Audio', '*.mp3 *.wav *.aiff *.flac *.m4a'),
                       ('All', '*.*')])
        for f in files:
            if self._limit_reached(): break
            p = Path(f)
            if not is_audio(p.name): continue
            if any(i.get('name') == p.name for i in self.items): continue
            id3    = read_id3(p)
            parsed = parse_filename(p.name)
            if id3.get('artist'): parsed['artist'] = id3['artist']
            if id3.get('title'):  parsed['title']  = id3['title']
            self.items.append(self._make_item(
                'track', name=p.name, path=p, parsed=parsed, id3=id3,
                genre=format_genre(id3.get('genre', '')),
                label=id3.get('label', ''), year=id3.get('year', '')))
        self._refresh_load()

    def _add_folder(self):
        if self._limit_reached(): return
        folder = filedialog.askdirectory(title='Elegí carpeta EP/Album')
        if not folder: return
        fp = Path(folder); fn = fp.name
        if any(i.get('folder_name') == fn for i in self.items):
            messagebox.showinfo('', f'"{fn}" ya está cargada.'); return
        audio = sorted([f for f in fp.iterdir() if f.is_file() and is_audio(f.name)])
        imgs  = [f for f in fp.iterdir() if f.is_file() and is_image(f.name)]
        if not audio:
            messagebox.showwarning('', f'No hay audio en "{fn}".'); return
        parsed = parse_folder_name(fn)
        id3    = read_id3(audio[0])
        if id3.get('artist'): parsed['artist'] = id3['artist']
        if id3.get('album'):  parsed['album']  = id3['album']
        self.items.append(self._make_item(
            'album', folder_name=fn, folder_path=fp,
            audio_files=audio, image_files=imgs,
            parsed=parsed, id3=id3,
            genre=format_genre(id3.get('genre', '')),
            label=id3.get('label', ''), year=id3.get('year', '')))
        self._refresh_load()

    def _scan_folder(self):
        folder = filedialog.askdirectory(title='Elegí la carpeta a escanear')
        if not folder: return
        fp = Path(folder)
        added_t = added_a = skipped = 0
        capped = False

        for f in sorted(fp.iterdir()):
            if len(self.items) >= MAX_ITEMS:
                capped = True; break
            if not (f.is_file() and is_audio(f.name)): continue
            if any(i.get('name') == f.name for i in self.items):
                skipped += 1; continue
            id3    = read_id3(f)
            parsed = parse_filename(f.name)
            if id3.get('artist'): parsed['artist'] = id3['artist']
            if id3.get('title'):  parsed['title']  = id3['title']
            self.items.append(self._make_item(
                'track', name=f.name, path=f, parsed=parsed, id3=id3,
                genre=format_genre(id3.get('genre', '')),
                label=id3.get('label', ''), year=id3.get('year', '')))
            added_t += 1

        for sub in sorted(fp.iterdir()):
            if len(self.items) >= MAX_ITEMS:
                capped = True; break
            if not sub.is_dir(): continue
            fn = sub.name
            if any(i.get('folder_name') == fn for i in self.items):
                skipped += 1; continue
            audio = sorted([f for f in sub.iterdir() if f.is_file() and is_audio(f.name)])
            imgs  = [f for f in sub.iterdir() if f.is_file() and is_image(f.name)]
            if not audio: continue
            parsed = parse_folder_name(fn)
            id3    = read_id3(audio[0])
            if id3.get('artist'): parsed['artist'] = id3['artist']
            if id3.get('album'):  parsed['album']  = id3['album']
            self.items.append(self._make_item(
                'album', folder_name=fn, folder_path=sub,
                audio_files=audio, image_files=imgs,
                parsed=parsed, id3=id3,
                genre=format_genre(id3.get('genre', '')),
                label=id3.get('label', ''), year=id3.get('year', '')))
            added_a += 1

        self._refresh_load()
        parts = []
        if added_t:  parts.append(f"{added_t} track{'s' if added_t>1 else ''}")
        if added_a:  parts.append(f"{added_a} album{'s' if added_a>1 else ''}")
        if skipped:  parts.append(f"{skipped} ya existían")
        msg = 'Cargado: ' + (', '.join(parts) or 'Sin archivos de audio.')
        if capped:
            msg += (f'\n\n⚠ Se alcanzó el tope de {MAX_ITEMS} ítems por tanda.\n'
                    'Procesá estos y volvé a escanear para cargar el resto.')
        messagebox.showinfo('Carpeta escaneada', msg)

    def _clear_items(self):
        if self.items and messagebox.askyesno('', '¿Borrar lista?'):
            self.items.clear(); self._refresh_load()

    def _del_selected(self, event=None):
        sel = self.tree_load.selection()
        if not sel: return
        iid = int(self.tree_load.item(sel[0])['values'][-1])
        self.items = [i for i in self.items if i['id'] != iid]
        self._refresh_load()

    # ── DUPLICADOS ────────────────────────────────────────────────────────────
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

    def _item_filenames(self, item):
        if item['type'] == 'track':
            return [item['name']]
        return [f.name for f in item.get('audio_files', [])]

    def _find_duplicate(self, item, idx=None):
        """Devuelve la entrada de historial coincidente, o None."""
        if not self.history: return None
        idx = idx if idx is not None else self._hist_name_index()
        for n in self._item_filenames(item):
            key = self._norm(Path(n).stem)
            if key and key in idx:
                return idx[key]
        return None

    def _refresh_load(self):
        for r in self.tree_load.get_children():
            self.tree_load.delete(r)
        hist_idx = self._hist_name_index()
        dups = 0
        for item in self.items:
            id3 = item.get('id3', {})
            tags_str = ('✓ ' + ', '.join(
                k for k in ['artist', 'label', 'year'] if id3.get(k))) if id3 else '—'
            tag = ('album' if item['type'] == 'album' else 'track',)
            if id3: tag = tag + ('hasid3',)
            is_dup = self._find_duplicate(item, hist_idx) is not None
            if is_dup:
                dups += 1
                tag = tag + ('dup',)
                tags_str = '⚠ YA EN HISTORIAL'
            nm = item.get('folder_name') or item['name']
            self.tree_load.insert('', 'end', values=(
                'EP/ALBUM' if item['type'] == 'album' else 'TRACK',
                f"📁 {nm}" if item['type'] == 'album' else nm,
                item['parsed'].get('artist', '—'), tags_str, item['id']
            ), tags=tag)
        t = sum(1 for i in self.items if i['type'] == 'track')
        a = sum(1 for i in self.items if i['type'] == 'album')
        parts = ([f"{t} track{'s' if t>1 else ''}"] if t else []) + \
                ([f"{a} album{'s' if a>1 else ''}"] if a else [])
        txt = ', '.join(parts) if parts else 'Ningún ítem cargado'
        if dups:
            txt += f'   ·   ⚠ {dups} ya en tu historial'
        self.lbl_count.config(text=txt)
        self.btn_go.config(state='normal' if self.items else 'disabled')

    # ── BUSCAR & CONFIRMAR ────────────────────────────────────────────────────
    def _go_to_search(self):
        if not self.discogs_token.get().strip():
            messagebox.showwarning('Token requerido',
                'Necesitás un token de Discogs.\n\n'
                'discogs.com → Settings → Developers → Generate token')
            return
        self._save_config()
        self._go_tab(1)
        self._refresh_item_list()
        self._load_item(0)

    def _refresh_item_list(self):
        self.list_items.delete(0, 'end')
        for item in self.items:
            nm = item.get('folder_name') or item['name']
            if item['status'] == 'confirmed':
                prefix, color = '✓ ', SUCCESS
            elif item['status'] == 'skipped':
                prefix, color = '— ', DIM
            elif item.get('flag'):            # sin resultados o marcado a mano
                prefix, color = '✗ ', ACCENT2
            else:
                prefix, color = '⧖ ', WARNING
            self.list_items.insert('end', f"{prefix}{nm[:24]}")
            self.list_items.itemconfig(self.list_items.size()-1, fg=color)
        confirmed = sum(1 for i in self.items if i['status'] == 'confirmed')
        flagged   = sum(1 for i in self.items
                        if i.get('flag') and i['status'] == 'pending')
        txt = f"{confirmed}/{len(self.items)} confirmados"
        if flagged:
            txt += f"  ·  ✗ {flagged} para revisar"
        self.lbl_progress.config(text=txt)
        self.btn_move_all.config(
            state='normal' if confirmed > 0 else 'disabled')

    def _on_item_select(self, event):
        sel = self.list_items.curselection()
        if not sel: return
        self._load_item(sel[0])

    def _load_item(self, idx):
        if idx >= len(self.items): return
        self._current_item_idx = idx
        item = self.items[idx]
        nm   = item.get('folder_name') or item['name']

        self.list_items.selection_clear(0, 'end')
        self.list_items.selection_set(idx)
        self.list_items.see(idx)

        tipo = '📁 EP/Album' if item['type'] == 'album' else '🎵 Track'
        dup = self._find_duplicate(item)
        if dup:
            self.lbl_current.config(
                text=f"{tipo}: {nm}    ⚠ YA EN HISTORIAL ({dup.get('fecha', '')})",
                fg=WARNING)
        else:
            self.lbl_current.config(text=f"{tipo}: {nm}", fg=ACCENT)

        artist = item['parsed'].get('artist', '')
        title  = item['parsed'].get(
            'album' if item['type'] == 'album' else 'title', '') or nm
        self.search_var.set(f"{artist} {title}".strip())

        # Pre-llenar con datos existentes del ítem
        self.conf_genre.set(item.get('genre', ''))
        self.conf_label.set(item.get('label', ''))
        self.conf_year.set(item.get('year', ''))

        # Limpiar resultados anteriores
        for r in self.tree_discogs.get_children():
            self.tree_discogs.delete(r)
        self._discogs_results = []
        self.lbl_search_status.config(text='⧖ Buscando...', fg=LABEL)

        # Auto-búsqueda
        self.after(150, self._do_search)

    def _search_beatport(self):
        """Abre Beatport en el navegador buscando el track actual."""
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo('', 'No hay nada para buscar en Beatport.')
            return
        try:
            webbrowser.open(f'https://www.beatport.com/search?q={quote(query)}')
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo abrir el navegador:\n{e}')

    def _do_search(self):
        query = self.search_var.get().strip()
        if not query: return
        token = self.discogs_token.get().strip()
        if not token: return
        # Fallback: solo artista, si la query incluye más que el nombre del artista
        fallback = ''
        if self._current_item_idx < len(self.items):
            artist = self.items[self._current_item_idx]['parsed'].get('artist', '').strip()
            if artist and artist.lower() != query.lower():
                fallback = artist
        self.lbl_search_status.config(text='⧖ Buscando...', fg=LABEL)
        self.btn_search_disc.config(state='disabled')
        threading.Thread(
            target=self._search_thread, args=(query, token, fallback), daemon=True).start()

    def _search_thread(self, query, token, fallback=''):
        try:
            results = discogs_search(query, token, limit=10)
            if not results and fallback:
                self.after(0, lambda: self.lbl_search_status.config(
                    text=f'⧖ Sin resultados — reintentando solo con "{fallback}"...', fg=WARNING))
                results = discogs_search(fallback, token, limit=10)
            parsed = [parse_discogs_result(r) for r in results]
            self.after(0, lambda p=parsed: self._show_results(p))
        except Exception as e:
            self.after(0, lambda: self.lbl_search_status.config(
                text=f'✗ Error: {e}', fg=ACCENT2))
        finally:
            self.after(0, lambda: self.btn_search_disc.config(state='normal'))

    def _show_results(self, results):
        for r in self.tree_discogs.get_children():
            self.tree_discogs.delete(r)
        self._discogs_results = results
        # Marcar/desmarcar el ítem actual según haya resultados
        if self._current_item_idx < len(self.items):
            cur = self.items[self._current_item_idx]
            if not results:
                if cur.get('flag') == '':
                    cur['flag'] = 'noresult'   # rojo automático
            elif cur.get('flag') == 'noresult':
                cur['flag'] = ''               # aparecieron resultados → limpia
            self._refresh_item_list()
        if not results:
            self.lbl_search_status.config(
                text='✗ Sin resultados — marcado para revisar (o probá otra búsqueda)',
                fg=ACCENT2)
            return
        self.lbl_search_status.config(
            text=f'✓ {len(results)} resultados — seleccioná uno y confirmá', fg=SUCCESS)
        for res in results:
            self.tree_discogs.insert('', 'end', values=(
                res['title'], res['artist'], res['genre'],
                res['label'], res['year'], res['format']
            ), tags=('result',))
        # Auto-seleccionar el primer resultado
        first = self.tree_discogs.get_children()[0]
        self.tree_discogs.selection_set(first)
        self.tree_discogs.see(first)

    def _on_discogs_select(self, event):
        sel = self.tree_discogs.selection()
        if not sel: return
        idx = self.tree_discogs.index(sel[0])
        if idx >= len(self._discogs_results): return
        res = self._discogs_results[idx]
        self.conf_genre.set(res['genre'])
        self.conf_label.set(res['label'])
        self.conf_year.set(res['year'])

    def _use_discogs_result(self):
        sel = self.tree_discogs.selection()
        if not sel:
            messagebox.showinfo('', 'Seleccioná un resultado primero.')
            return
        self._on_discogs_select(None)

    def _update_path_preview(self, *args):
        if self._current_item_idx >= len(self.items): return
        item = self.items[self._current_item_idx]
        nm   = item.get('folder_name') or item['name']
        g, l, y = (self.conf_genre.get().strip(),
                   self.conf_label.get().strip(),
                   self.conf_year.get().strip())
        if g and l and y:
            path = build_path(self.base_path.get(), g, l, y, nm)
            self.lbl_path_preview.config(text=f"→ {path}", fg=ACCENT)
        else:
            self.lbl_path_preview.config(
                text='→ completá género, sello y año', fg=DIM)

    def _confirm_current(self):
        if self._current_item_idx >= len(self.items): return
        item  = self.items[self._current_item_idx]
        genre = self.conf_genre.get().strip()
        label = self.conf_label.get().strip()
        year  = self.conf_year.get().strip()
        if not (genre and label and year):
            messagebox.showwarning('', 'Completá género, sello y año antes de confirmar.')
            return
        item.update({'genre': genre, 'label': label, 'year': year,
                     'status': 'confirmed', 'flag': ''})
        nm = item.get('folder_name') or item['name']
        item['destination'] = str(build_path(
            self.base_path.get(), genre, label, year, nm))
        self._refresh_item_list()
        nxt = self._next_pending()
        if nxt is not None:
            self._load_item(nxt)
        else:
            messagebox.showinfo('¡Listo!',
                'Todos los ítems confirmados.\n'
                'Hacé click en "▶ Mover confirmados".')

    def _skip_item(self):
        if self._current_item_idx >= len(self.items): return
        self.items[self._current_item_idx]['status'] = 'skipped'
        self.items[self._current_item_idx]['flag'] = ''
        self._refresh_item_list()
        nxt = self._next_pending()
        if nxt is not None:
            self._load_item(nxt)

    def _flag_current(self):
        """Marca/desmarca a mano el ítem actual como 'sin match' (rojo, para revisar)."""
        if self._current_item_idx >= len(self.items): return
        item = self.items[self._current_item_idx]
        # Toggle: si ya está marcado, lo desmarca; si no, lo marca
        item['flag'] = '' if item.get('flag') else 'review'
        self._refresh_item_list()

    def _next_pending(self):
        for i, item in enumerate(self.items):
            if item['status'] == 'pending': return i
        return None

    # ── MOVER ────────────────────────────────────────────────────────────────
    def _move_all(self):
        ready   = [i for i in self.items if i['status'] == 'confirmed']
        skipped = [i for i in self.items if i['status'] != 'confirmed']
        if not ready:
            messagebox.showwarning('', 'No hay ítems confirmados.'); return
        n = len(ready)
        hist_idx = self._hist_name_index()
        dups = sum(1 for i in ready if self._find_duplicate(i, hist_idx))
        msg = f"¿Mover {n} ítem{'s' if n>1 else ''} ahora?\n"
        if dups:
            msg += (f"\n⚠ {dups} de estos ya figura"
                    f"{'n' if dups>1 else ''} en tu historial.\n")
        msg += "\nVas a poder deshacer este movimiento desde la pestaña Resultado."
        if not messagebox.askyesno('Confirmar', msg):
            return
        self._go_tab(2)
        self._log_clear()
        self._log_entries.clear()
        # Keep existing accumulated paths, reset only session
        self._session_paths = []
        self._session_history = []
        self._last_move = []
        self._moved_item_ids = []
        threading.Thread(
            target=self._move_thread, args=(ready, skipped), daemon=True).start()

    def _move_thread(self, ready, skipped):
        folders = set()
        moved_t = moved_a = errors = 0
        now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        self._log(f"Iniciando: {len(ready)} ítems\n", 'info')
        self._log_entries += [
            f"BelApp — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            '─' * 60]

        for item in ready:
            dest     = Path(item['destination'])
            dest_dir = dest.parent
            nm       = item.get('folder_name') or item['name']
            try:
                if not dest_dir.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    folders.add(str(dest_dir))
                    self._log(f"📁 Carpeta creada: {dest_dir}\n", 'info')
                else:
                    folders.add(str(dest_dir))

                if item['type'] == 'track':
                    src = item['path']
                    if not src.exists():
                        self._log(f"✗ No encontrado: {nm}\n", 'error')
                        errors += 1; continue
                    if dest.exists():
                        self._log(f"⚠ Ya existe: {nm}\n", 'warn'); continue
                    shutil.move(str(src), str(dest))
                    artist = item['parsed'].get('artist', '')
                    title  = item['parsed'].get('title', '') or Path(nm).stem
                    tag_s  = ''
                    if MUTAGEN_OK:
                        ok = write_id3_tags(dest, artist, title, '',
                                            item['label'], item['genre'], item['year'])
                        tag_s = ' [tags ✓]' if ok else ''
                    self._log(f"✓ {nm}{tag_s}\n  → {dest}\n", 'success')
                    self._log_entries.append(str(dest))
                    self._moved_paths.append(str(dest))
                    self._session_paths.append(str(dest))
                    self._session_history.append({
                        'fecha': now_str, 'artista': artist or '—',
                        'track': title or Path(nm).stem,
                        'genero': item['genre'], 'sello': item['label'],
                        'año': item['year'], 'destino': str(dest)})
                    self._last_move.append(
                        {'type': 'file', 'src': str(src), 'dest': str(dest)})
                    self._moved_item_ids.append(item['id'])
                    moved_t += 1

                else:
                    src_f = item['folder_path']
                    if not src_f.exists():
                        self._log(f"✗ No encontrada: {nm}\n", 'error')
                        errors += 1; continue
                    if dest.exists():
                        self._log(f"⚠ Ya existe: {nm}\n", 'warn'); continue
                    shutil.move(str(src_f), str(dest))
                    self._last_move.append(
                        {'type': 'folder', 'src': str(src_f), 'dest': str(dest)})
                    tagged = 0
                    if MUTAGEN_OK:
                        artist     = item['parsed'].get('artist', '')
                        album_name = item['parsed'].get('album', nm)
                        for tf in dest.iterdir():
                            if tf.is_file() and is_audio(tf.name):
                                ap = parse_filename(tf.name)
                                ok = write_id3_tags(
                                    tf, artist, ap.get('title', tf.stem),
                                    album_name, item['label'],
                                    item['genre'], item['year'])
                                if ok: tagged += 1
                                self._moved_paths.append(str(tf))
                                self._session_paths.append(str(tf))
                                self._session_history.append({
                                    'fecha': now_str,
                                    'artista': ap.get('artist') or artist or '—',
                                    'track': ap.get('title') or tf.stem,
                                    'genero': item['genre'], 'sello': item['label'],
                                    'año': item['year'], 'destino': str(tf)})
                    else:
                        artist = item['parsed'].get('artist', '')
                        for tf in dest.iterdir():
                            if tf.is_file() and is_audio(tf.name):
                                ap = parse_filename(tf.name)
                                self._moved_paths.append(str(tf))
                                self._session_paths.append(str(tf))
                                self._session_history.append({
                                    'fecha': now_str,
                                    'artista': ap.get('artist') or artist or '—',
                                    'track': ap.get('title') or tf.stem,
                                    'genero': item['genre'], 'sello': item['label'],
                                    'año': item['year'], 'destino': str(tf)})
                    na = len(item['audio_files'])
                    self._log(
                        f"📁 {nm} ({na} tracks)"
                        f"{f' [tags {tagged}✓]' if MUTAGEN_OK else ''}\n"
                        f"  → {dest}\n", 'album')
                    self._log_entries.append(str(dest))
                    self._moved_item_ids.append(item['id'])
                    moved_a += 1

            except PermissionError:
                self._log(f"✗ Sin permisos: {nm}\n", 'error')
                errors += 1
            except Exception as e:
                self._log(f"✗ Error: {e}\n", 'error')
                errors += 1

        for item in skipped:
            nm = item.get('folder_name') or item['name']
            self._log(f"— Salteado: {nm}\n", 'dim')

        summary = (f"✓ Listo! {moved_t} tracks, {moved_a} albums, "
                   f"{len(folders)} carpetas nuevas, {errors} errores.")
        self._log(f"\n{summary}\n", 'warn')
        self.after(0, lambda: self._move_done(
            moved_t, moved_a, len(skipped), len(folders)))

    def _move_done(self, t, a, sk, f):
        for k, v in [('tracks',t), ('albums',a), ('skipped',sk), ('folders',f)]:
            self.sum_vars[k].set(str(v))
        # Auto-guardar en TXT del período activo
        self._append_to_txt(self._session_paths)
        self._update_txt_count()
        # Volcar al historial persistente
        if self._session_history:
            self.history.extend(self._session_history)
            self._save_history()
            self._refresh_history()
        # Sacar de la lista los ítems ya acomodados (salteados/fallidos quedan)
        if self._moved_item_ids:
            moved = set(self._moved_item_ids)
            self.items = [it for it in self.items if it['id'] not in moved]
            self._refresh_load()
            self._refresh_item_list()
        # Habilitar "Deshacer" si hubo movimientos
        self.btn_undo.config(
            state='normal' if self._last_move else 'disabled')

    # ── LOG ──────────────────────────────────────────────────────────────────
    def _log(self, text, tag=''):
        def _do():
            self.log_text.config(state='normal')
            ts = time.strftime('%H:%M:%S')
            self.log_text.insert('end', f"[{ts}] ", 'dim')
            self.log_text.insert('end', text, tag)
            self.log_text.see('end')
            self.log_text.config(state='disabled')
        self.after(0, _do)

    def _log_clear(self):
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.config(state='disabled')

    def _get_txt_path(self):
        """Ruta del TXT del período activo."""
        base = Path(self.base_path.get())
        return base / f"beldj_{self.playlist_name.get().strip() or 'playlist'}.txt"

    def _load_existing_txt(self):
        """Carga rutas ya guardadas del TXT del período activo."""
        txt = self._get_txt_path()
        if not txt.exists(): self._update_txt_count(); return
        try:
            lines = txt.read_text(encoding='utf-8').splitlines()
            # Las rutas son líneas que empiezan con una letra de drive (ej: D:\)
            loaded = [l for l in lines if len(l) > 3 and (l[1:3] == ':\\' or l[1:3] == ':/')]
            # Agregar solo las que no están ya en memoria
            existing = set(self._moved_paths)
            for l in loaded:
                if l not in existing:
                    self._moved_paths.append(l)
            self._update_txt_count()
        except Exception:
            pass

    def _append_to_txt(self, new_paths):
        """Agrega rutas nuevas al TXT del período activo (append, no reescribe)."""
        if not new_paths: return
        try:
            txt = self._get_txt_path()
            txt.parent.mkdir(parents=True, exist_ok=True)
            with open(txt, 'a', encoding='utf-8') as fp:
                if not txt.exists() or txt.stat().st_size == 0:
                    fp.write(f"BelApp — Período {self.playlist_name.get()}\n")
                    fp.write('─' * 60 + '\n')
                for path in new_paths:
                    fp.write(path + '\n')
            self._update_txt_count()
        except Exception as e:
            print(f"Error guardando TXT: {e}")

    def _update_txt_count(self):
        """Actualiza el label con cantidad de tracks acumulados."""
        n = len(self._moved_paths)
        txt = self._get_txt_path()
        name = self.playlist_name.get()
        if n == 0:
            self.lbl_txt_count.config(
                text=f"Período {name}: sin tracks aún", fg=LABEL)
        else:
            self.lbl_txt_count.config(
                text=f"Período {name}: {n} track{'s' if n>1 else ''} acumulado{'s' if n>1 else ''}  ·  {txt.name}",
                fg=SUCCESS)

    def _new_period(self):
        """Arranca un período nuevo (resetea la lista en memoria, el TXT viejo queda)."""
        name = self.playlist_name.get().strip()
        if not name:
            messagebox.showwarning('', 'Escribí el nombre del período (ej: 2026_12)'); return
        if not messagebox.askyesno('Nuevo período',
            f'¿Empezar el período "{name}"?\n\n'
            f'Los tracks anteriores quedan en su TXT.\n'
            f'Este período va a crear: beldj_{name}.txt'):
            return
        self._moved_paths.clear()
        self._update_txt_count()
        messagebox.showinfo('¡Listo!', f'Período "{name}" iniciado.\nbeldj_{name}.txt se creará al mover los primeros tracks.')

    def _save_txt(self):
        """Abre el TXT del período activo en el explorador de Windows."""
        txt = self._get_txt_path()
        if not txt.exists():
            messagebox.showinfo('', 'Todavía no hay tracks guardados en este período.'); return
        try:
            import subprocess
            subprocess.Popen(['explorer', '/select,', str(txt)])
        except Exception:
            messagebox.showinfo('Ubicación del TXT', str(txt))

    # ── TAB 4: HISTORIAL ──────────────────────────────────────────────────────
    def _build_tab_history(self):
        f = self.tab_history

        # Barra inferior fija
        bb = tk.Frame(f, bg=SURFACE, pady=6, padx=12)
        bb.pack(fill='x', side='bottom')
        self._btn(bb, '📂 Abrir en carpeta', self._open_hist_dest,
                  accent=True, side='left')
        self._btn(bb, '⬇ Exportar CSV', self._export_history_csv,
                  color=INFO, side='left', padx=(8, 0))
        self._btn(bb, '🗑 Limpiar historial', self._clear_history,
                  danger=True, side='left', padx=(8, 0))
        self.lbl_hist_count = tk.Label(bb, text='', font=('Consolas', 10),
                                        fg=SUCCESS, bg=SURFACE)
        self.lbl_hist_count.pack(side='right')

        # Barra de búsqueda
        sf = tk.Frame(f, bg=BG)
        sf.pack(fill='x', padx=20, pady=(14, 6), side='top')
        tk.Label(sf, text='BUSCAR:', font=('Consolas', 9),
                 fg=LABEL, bg=BG).pack(side='left')
        self.hist_filter = tk.StringVar()
        tk.Entry(sf, textvariable=self.hist_filter, font=('Consolas', 11),
                 fg=TEXT, bg=SURF2, insertbackground=ACCENT,
                 relief='flat', bd=4).pack(side='left', fill='x',
                                            expand=True, padx=(8, 0))
        self.hist_filter.trace_add('write', lambda *a: self._refresh_history())
        tk.Label(sf, text='(doble click en una fila → abre la carpeta)',
                 font=('Consolas', 8), fg=DIM, bg=BG).pack(side='left', padx=(10, 0))

        # Tabla
        lf = tk.Frame(f, bg=BG)
        lf.pack(fill='both', expand=True, padx=20, pady=(0, 4), side='top')
        cols = ('fecha', 'artista', 'track', 'genero', 'sello', 'año', 'destino')
        self.tree_hist = ttk.Treeview(lf, columns=cols, show='headings',
                                       selectmode='browse')
        for col, txt, w, stretch in [
                ('fecha',  'FECHA',   115, False), ('artista', 'ARTISTA', 160, True),
                ('track',  'TRACK',   280, True),  ('genero',  'GÉNERO',  210, False),
                ('sello',  'SELLO',   150, False), ('año',     'AÑO',      50, False),
                ('destino','DESTINO', 320, True)]:
            self.tree_hist.heading(col, text=txt)
            self.tree_hist.column(col, width=w, stretch=stretch,
                                   minwidth=40 if not stretch else 80)
        self.tree_hist.tag_configure('row', foreground=TEXT)
        self.tree_hist.bind('<Double-1>', self._open_hist_dest)
        self.tree_hist.bind('<Button-3>', self._hist_context_menu)

        # Menú contextual (click derecho)
        self.hist_menu = tk.Menu(self, tearoff=0, bg=SURF2, fg=TEXT,
                                  activebackground=ACCENT, activeforeground='#000',
                                  relief='flat', bd=0,
                                  font=('Consolas', 10))
        self.hist_menu.add_command(label='  📂 Abrir en carpeta',
                                   command=self._open_hist_dest)
        self.hist_menu.add_command(label='  📋 Copiar ruta destino',
                                   command=self._copy_hist_dest)
        self.hist_menu.add_separator()
        self.hist_menu.add_command(label='  🗑 Eliminar del historial',
                                   command=self._delete_hist_entry)

        sb = ttk.Scrollbar(lf, orient='vertical', command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=sb.set)
        self.tree_hist.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self._refresh_history()

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

    def _refresh_history(self):
        if not hasattr(self, 'tree_hist'): return
        flt = self.hist_filter.get().strip().lower()
        for r in self.tree_hist.get_children():
            self.tree_hist.delete(r)
        shown = 0
        for h in reversed(self.history):   # más reciente primero
            if flt:
                blob = ' '.join([h.get('artista',''), h.get('track',''),
                                 h.get('genero',''), h.get('sello',''),
                                 h.get('destino','')]).lower()
                if flt not in blob: continue
            self.tree_hist.insert('', 'end', values=(
                h.get('fecha',''), h.get('artista',''), h.get('track',''),
                h.get('genero',''), h.get('sello',''), h.get('año',''),
                h.get('destino','')), tags=('row',))
            shown += 1
        total = len(self.history)
        if total == 0:
            self.lbl_hist_count.config(text='Sin registros aún', fg=LABEL)
        elif flt:
            self.lbl_hist_count.config(
                text=f'{shown} de {total} registros', fg=SUCCESS)
        else:
            self.lbl_hist_count.config(
                text=f'{total} registro{"s" if total != 1 else ""}', fg=SUCCESS)

    def _hist_context_menu(self, event):
        row = self.tree_hist.identify_row(event.y)
        if not row: return
        self.tree_hist.selection_set(row)
        self.tree_hist.focus(row)
        try:
            self.hist_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.hist_menu.grab_release()

    def _copy_hist_dest(self):
        sel = self.tree_hist.selection()
        if not sel: return
        vals = self.tree_hist.item(sel[0])['values']
        if not vals: return
        dest = str(vals[-1])
        self.clipboard_clear()
        self.clipboard_append(dest)
        if hasattr(self, 'lbl_hist_count'):
            self.lbl_hist_count.config(text='✓ Ruta copiada al portapapeles', fg=INFO)
            self.after(2000, self._refresh_history)

    def _delete_hist_entry(self):
        sel = self.tree_hist.selection()
        if not sel: return
        vals = self.tree_hist.item(sel[0])['values']
        if not vals: return
        dest = str(vals[-1])
        if not messagebox.askyesno('Eliminar registro',
                '¿Quitar este registro del historial?\n\n'
                'NO borra ni mueve el archivo de música.'):
            return
        self.history = [h for h in self.history
                        if str(h.get('destino', '')) != dest]
        self._save_history()
        self._refresh_history()

    def _open_hist_dest(self, event=None):
        sel = self.tree_hist.selection()
        if not sel:
            messagebox.showinfo('', 'Seleccioná una fila del historial primero.')
            return
        vals = self.tree_hist.item(sel[0])['values']
        if not vals: return
        dest = str(vals[-1])
        try:
            import subprocess
            if Path(dest).exists():
                subprocess.Popen(['explorer', '/select,', dest])
            else:
                subprocess.Popen(['explorer', str(Path(dest).parent)])
        except Exception:
            messagebox.showinfo('Ubicación', dest)

    def _export_history_csv(self):
        if not self.history:
            messagebox.showinfo('', 'No hay historial para exportar.'); return
        path = filedialog.asksaveasfilename(
            title='Exportar historial', defaultextension='.csv',
            initialfile='belapp_historial.csv',
            filetypes=[('CSV', '*.csv')])
        if not path: return
        try:
            import csv
            with open(path, 'w', newline='', encoding='utf-8-sig') as fp:
                w = csv.writer(fp)
                w.writerow(['Fecha', 'Artista', 'Track', 'Género',
                            'Sello', 'Año', 'Destino'])
                for h in self.history:
                    w.writerow([h.get('fecha',''), h.get('artista',''),
                                h.get('track',''), h.get('genero',''),
                                h.get('sello',''), h.get('año',''),
                                h.get('destino','')])
            messagebox.showinfo('Exportado', f'Historial exportado:\n{path}')
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo exportar:\n{e}')

    def _clear_history(self):
        if not self.history:
            messagebox.showinfo('', 'El historial ya está vacío.'); return
        if messagebox.askyesno('Limpiar historial',
                f'¿Borrar los {len(self.history)} registros del historial?\n\n'
                'Esto NO borra ni mueve ningún archivo de música,\n'
                'solo el registro consultable.'):
            self.history = []
            self._save_history()
            self._refresh_history()

    # ── DESHACER ÚLTIMO MOVIMIENTO ────────────────────────────────────────────
    def _undo_last_move(self):
        if not self._last_move:
            messagebox.showinfo('', 'No hay ningún movimiento reciente para deshacer.')
            return
        n = len(self._last_move)
        if not messagebox.askyesno('Deshacer último movimiento',
                f'¿Devolver {n} ítem{"s" if n>1 else ""} a su ubicación original?\n\n'
                'Los archivos se van a mover de vuelta a donde estaban\n'
                'antes del último "Mover".'):
            return
        restored = errors = skipped = 0
        undone_dests = []
        problems = []
        for entry in reversed(self._last_move):
            src  = Path(entry['src'])
            dest = Path(entry['dest'])
            try:
                if not dest.exists():
                    skipped += 1
                    problems.append(f"• Ya no está: {dest.name}")
                    continue
                if src.exists():
                    skipped += 1
                    problems.append(f"• El origen ya existe: {src.name}")
                    continue
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(src))
                undone_dests.append(str(dest))
                restored += 1
            except Exception as e:
                errors += 1
                problems.append(f"• Error con {dest.name}: {e}")

        if undone_dests:
            self._purge_paths_from_records(undone_dests)

        self._last_move = []
        self.btn_undo.config(state='disabled')
        self._log(f"\n⮌ Deshacer: {restored} restaurados, "
                  f"{skipped} salteados, {errors} errores.\n", 'warn')

        msg = f'✓ {restored} ítem{"s" if restored != 1 else ""} devuelto'
        msg += 's' if restored != 1 else ''
        msg += ' a su lugar original.'
        if skipped or errors:
            msg += f'\n\n⚠ {skipped + errors} no se pudo{"" if skipped+errors==1 else "ieron"} deshacer:\n'
            msg += '\n'.join(problems[:8])
            if len(problems) > 8:
                msg += f'\n… y {len(problems) - 8} más'
        messagebox.showinfo('Deshacer', msg)

    def _purge_paths_from_records(self, dests):
        """Quita del historial / TXT / acumulado las rutas deshechas (archivos o carpetas)."""
        dests_norm = [str(d).rstrip('\\/').lower() for d in dests]
        def is_under(path):
            p = str(path).lower()
            for d in dests_norm:
                if p == d or p.startswith(d + '\\') or p.startswith(d + '/'):
                    return True
            return False
        self.history     = [h for h in self.history
                            if not is_under(h.get('destino', ''))]
        self._moved_paths = [p for p in self._moved_paths if not is_under(p)]
        self._save_history()
        self._refresh_history()
        self._rewrite_txt()
        self._update_txt_count()

    def _rewrite_txt(self):
        """Reescribe el TXT del período activo desde las rutas acumuladas en memoria."""
        try:
            txt = self._get_txt_path()
            txt.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"BelApp — Período {self.playlist_name.get()}", '─' * 60]
            lines += self._moved_paths
            txt.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        except Exception as e:
            print(f"Error reescribiendo TXT: {e}")

    # ── RESET ────────────────────────────────────────────────────────────────
    def _reset(self):
        if not messagebox.askyesno('', '¿Empezar de nuevo?'): return
        self.items.clear()
        self._log_entries.clear()
        self._moved_paths.clear()
        self._discogs_results = []
        self._refresh_load()
        self.list_items.delete(0, 'end')
        for r in self.tree_discogs.get_children():
            self.tree_discogs.delete(r)
        self._log_clear()
        for k in self.sum_vars:
            self.sum_vars[k].set('0')
        self._go_tab(0)

# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = BelDJApp()
    app.mainloop()

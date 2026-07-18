/* BelApp — frontend. Estado de UI en JS; operaciones en Python vía pywebview.api. */
'use strict';

const $ = (sel) => document.querySelector(sel);
const api = () => window.pywebview.api;

/* ── Estado global de UI ─────────────────────────────────── */
const state = {
  items: [],     // {id, ...itemPython, status:'pending'|'confirmed'|'skipped', flag, conf:{}}
  nextId: 1,
};

const itemNames = () => state.items.map((i) => i.name);
const itemPaths = () => state.items.map((i) => i.path);   // dedup por ruta

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/* Modal de confirmación con el estilo de la app (reemplaza window.confirm). */
function confirmModal(title, message) {
  return new Promise((resolve) => {
    const ov = $('#modal-overlay');
    const okBtn = $('#modal-ok');
    const cancelBtn = $('#modal-cancel');
    $('#modal-title').textContent = title;
    $('#modal-msg').textContent = message;
    ov.classList.add('show');
    function cleanup(val) {
      ov.classList.remove('show');
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      resolve(val);
    }
    function onOk() { cleanup(true); }
    function onCancel() { cleanup(false); }
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
  });
}

/* ── Navegación entre vistas ─────────────────────────────── */
const VIEWS = ['cargar', 'buscar', 'resultado', 'historial'];

function showView(name) {
  VIEWS.forEach((v) => {
    document.getElementById('view-' + v).classList.toggle('active', v === name);
    document.getElementById('nav-' + v).classList.toggle('active', v === name);
  });
}

VIEWS.forEach((v) => {
  document.getElementById('nav-' + v).addEventListener('click', () => showView(v));
});

showView('cargar');

/* ── Config ──────────────────────────────────────────────── */
async function saveConfig() {
  await api().save_config_values($('#base-path').value.trim(), $('#token').value.trim());
}

function flashMsg(text, ms = 5000) {
  $('#load-msg').textContent = text;
  if (text) setTimeout(() => { $('#load-msg').textContent = ''; }, ms);
}

/* ── Vista Cargar ────────────────────────────────────────── */
function addItems(newItems) {
  newItems.forEach((it) => {
    it.id = state.nextId++;
    it.status = 'pending';
    it.flag = '';
    // Carpeta sugerida: deducida del género específico (decisiones de Bel);
    // si no hay específico, cae en lo que detectó format_genre.
    const spec = it.genre_specific || '';
    const folder = (spec && SPEC2BROAD[spec]) || it.genre || '';
    it.conf = { genre: folder, genre_specific: spec,
                label: it.label, year: it.year };
    state.items.push(it);
  });
  renderLoadTable();
}

function removeItem(id) {
  state.items = state.items.filter((i) => i.id !== id);
  renderLoadTable();
}

function showDupInfo(it) {
  const d = it.dup_info || {};
  const msg =
    'Este ítem coincide con algo que YA ordenaste:\n\n' +
    `• Artista:  ${d.artista || '—'}\n` +
    `• Track:  ${d.track || '—'}\n` +
    `• Fecha:  ${d.fecha || '—'}\n` +
    `• Género:  ${d.genero || '—'}\n` +
    `• Sello:  ${d.sello || '—'}\n` +
    `• Ubicación:  ${d.destino || '—'}\n\n` +
    'Coincide por nombre de archivo: puede ser el mismo tema en otra compilación.';
  confirmModal('Ya en historial', msg);
}

function renderLoadTable() {
  const tbody = $('#tbl-load tbody');
  tbody.innerHTML = '';
  let dups = 0;

  state.items.forEach((it) => {
    if (it.is_dup) dups++;
    const tagsTxt = it.is_dup ? '⚠ YA EN HISTORIAL'
      : (it.has_id3 ? '✓ tags ID3' : '—');
    const tagsCls = it.is_dup ? 't-dup' : (it.has_id3 ? 't-ok' : 'muted');
    const nameCls = it.type === 'album' ? 't-album' : '';
    const nameTxt = (it.type === 'album' ? '📁 ' : '') + it.name +
      (it.type === 'album' ? ` (${it.n_tracks} tracks)` : '');

    const dupTitle = it.is_dup ? ' title="Click derecho para ver dónde y por qué"' : '';
    const tr = document.createElement('tr');
    tr.innerHTML =
      `<td class="muted">${it.type === 'album' ? 'EP/ALBUM' : 'TRACK'}</td>` +
      `<td class="${nameCls}">${escapeHtml(nameTxt)}</td>` +
      `<td>${escapeHtml(it.artist || '—')}</td>` +
      `<td class="${tagsCls}"${dupTitle}>${tagsTxt}</td>` +
      `<td><button class="row-x" title="Quitar">✕</button></td>`;
    tr.querySelector('.row-x').addEventListener('click', () => removeItem(it.id));
    if (it.is_dup) {
      tr.style.cursor = 'context-menu';
      tr.addEventListener('contextmenu', (e) => { e.preventDefault(); showDupInfo(it); });
    }
    tbody.appendChild(tr);
  });

  $('#load-empty').style.display = state.items.length ? 'none' : 'block';

  const t = state.items.filter((i) => i.type === 'track').length;
  const a = state.items.filter((i) => i.type === 'album').length;
  const parts = [];
  if (t) parts.push(`${t} track${t > 1 ? 's' : ''}`);
  if (a) parts.push(`${a} album${a > 1 ? 's' : ''}`);
  let txt = parts.length ? parts.join(', ') : 'Ningún ítem cargado';
  if (dups) txt += `   ·   ⚠ ${dups} ya en tu historial`;
  $('#load-count').textContent = txt;
  $('#btn-continue').disabled = state.items.length === 0;
}

function loadSummary(res) {
  const bits = [];
  if (res.items.length) bits.push(`${res.items.length} cargado${res.items.length > 1 ? 's' : ''}`);
  if (res.skipped) bits.push(`${res.skipped} ya estaban`);
  if (res.capped) bits.push('⚠ tope de tanda alcanzado — procesá estos y cargá el resto después');
  if (bits.length) flashMsg(bits.join(' · '));
}

$('#btn-pick-base').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (p) { $('#base-path').value = p; await saveConfig(); }
});
$('#base-path').addEventListener('change', saveConfig);
$('#token').addEventListener('change', saveConfig);

$('#btn-eye').addEventListener('click', () => {
  const t = $('#token');
  t.type = t.type === 'password' ? 'text' : 'password';
});

$('#btn-get-token').addEventListener('click', () => api().open_token_page());

$('#btn-add-tracks').addEventListener('click', async () => {
  const paths = await api().pick_tracks();
  if (!paths.length) return;
  const res = await api().load_tracks(paths, itemPaths(), state.items.length);
  addItems(res.items);
  loadSummary(res);
});

$('#btn-add-album').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (!p) return;
  const res = await api().load_album_folder(p, itemPaths(), state.items.length);
  if (res.error) { flashMsg('✗ ' + res.error); return; }
  addItems([res.item]);
});

$('#btn-scan').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (!p) return;
  const res = await api().scan_folder(p, itemPaths(), state.items.length);
  if (res.error) { flashMsg('✗ ' + res.error); return; }
  addItems(res.items);
  loadSummary(res);
});

$('#btn-clear').addEventListener('click', async () => {
  if (!state.items.length) return;
  if (await confirmModal('Limpiar', '¿Borrar la lista de ítems cargados?')) {
    state.items = [];
    renderLoadTable();
  }
});

let normRows = [];   // estado de la revisión de normalización

$('#btn-normalize').addEventListener('click', async () => {
  const folder = await api().pick_folder();
  if (!folder) return;
  flashMsg('⏳ Analizando la carpeta…');
  const r = await api().review_folder_genres(folder);
  if (r.error) { await confirmModal('Normalizar géneros', '✗ ' + r.error); return; }
  if (!r.total) {
    await confirmModal('Normalizar géneros', 'No hay tracks de audio en esa carpeta.');
    return;
  }
  openNormReview(r);
});

function normBase(p) { return String(p).split(/[\\/]/).pop(); }

function updateNormCount() {
  const n = normRows.filter((x) => x.chk.checked).length;
  $('#norm-count').textContent = `${n} de ${normRows.length} seleccionados`;
  $('#norm-apply').disabled = n === 0;
}

function openNormReview(r) {
  const list = $('#norm-list');
  list.innerHTML = '';
  normRows = [];
  $('#norm-sub').textContent =
    `${r.total} tracks · ${r.con_sugerencia} con sugerencia · ${r.sin_genero} sin género. ` +
    'Elegí el género de cada uno (tildá el que quieras aplicar). ' +
    'Solo toca el tag, NO mueve archivos.';
  r.tracks.forEach((t) => {
    const row = document.createElement('div');
    row.className = 'norm-row';

    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.checked = !!t.suggested;               // pre-tildado solo si hay sugerencia
    chk.addEventListener('change', updateNormCount);

    const name = document.createElement('div');
    name.className = 'nr-name';
    name.textContent = normBase(t.path);
    name.title = t.path;

    const old = document.createElement('div');
    old.className = 'nr-old';
    old.textContent = (t.current || '(sin género)') + '  →';

    const sel = document.createElement('select');
    const vacio = document.createElement('option');
    vacio.value = ''; vacio.textContent = '—';
    sel.appendChild(vacio);
    GENRES_SPEC.forEach((g) => {
      const o = document.createElement('option');
      o.value = g; o.textContent = g;
      if (g === t.suggested) o.selected = true;
      sel.appendChild(o);
    });
    // Elegir un género tilda la fila; volver a "—" la destilda.
    sel.addEventListener('change', () => { chk.checked = !!sel.value; updateNormCount(); });

    row.append(chk, name, old, sel);
    list.appendChild(row);
    normRows.push({ path: t.path, chk, sel });
  });
  updateNormCount();
  $('#norm-overlay').classList.add('show');
}

$('#norm-all').addEventListener('click', () => {
  normRows.forEach((x) => { x.chk.checked = !!x.sel.value; });   // solo los que tienen género elegido
  updateNormCount();
});
$('#norm-none').addEventListener('click', () => {
  normRows.forEach((x) => { x.chk.checked = false; });
  updateNormCount();
});
$('#norm-cancel').addEventListener('click', () => $('#norm-overlay').classList.remove('show'));

$('#norm-apply').addEventListener('click', async () => {
  const items = normRows.filter((x) => x.chk.checked)
    .map((x) => ({ path: x.path, new: x.sel.value }));
  if (!items.length) return;
  $('#norm-overlay').classList.remove('show');
  flashMsg('⏳ Aplicando cambios…');
  const res = await api().apply_normalize_selected(items);
  const errTxt = (res.errors && res.errors.length)
    ? `\n\n⚠ ${res.errors.length} con error (no se pudieron escribir).` : '';
  await confirmModal('Listo ✓',
    `${res.applied} géneros actualizados.${errTxt}\n\n` +
    'En Traktor: re-importá/actualizá la carpeta para ver los tags nuevos.');
});

$('#btn-playlists').addEventListener('click', async () => {
  const base = $('#base-path').value.trim();
  if (!base) { await confirmModal('Generar playlists', '✗ Falta la carpeta base de música.'); return; }
  const seguir = await confirmModal('Generar playlists para Traktor',
    'Leo los tags de tu biblioteca y armo una playlist .m3u8 por Género + Año.\n\n' +
    'Después elegís en qué carpeta guardarlas.\n\n' +
    'Ojo: escanear la biblioteca entera tarda unos minutos. NO mueve ni copia audio (es por referencia).');
  if (!seguir) return;
  const out = await api().pick_folder();
  if (!out) return;
  flashMsg('⏳ Generando playlists… puede tardar unos minutos');
  const res = await api().generate_playlists(base, out);
  if (res.error) { await confirmModal('Generar playlists', '✗ ' + res.error); return; }
  await confirmModal('Playlists listas ✓',
    `${res.playlists} playlists creadas (${res.tracks} tracks) en:\n${res.folder}\n\n` +
    `Se saltearon ${res.sin_tag} tracks sin género/año.\n\n` +
    'En Traktor: click derecho en "Playlists" → Import Playlist → elegí un .m3u8.');
});

$('#btn-continue').addEventListener('click', async () => {
  if (!$('#token').value.trim()) {
    flashMsg('✗ Necesitás un token de Discogs — usá el botón "Obtener token"');
    return;
  }
  await saveConfig();
  showView('buscar');
  enterBuscar(true);
});

/* ── Vista Buscar & Confirmar ────────────────────────────── */
let curIdx = -1;
let results = [];
let selResult = -1;
let searchSeq = 0;
let labelWarningActive = false;   // aviso de sello parecido sin resolver
let GENRES = [];           // las 4 carpetas
let GENRES_SPEC = [];      // los 12 géneros (para el tag)
let SPEC2BROAD = {};       // mapa género específico -> carpeta

/* Desplegable de CARPETA (4): siempre muestra las categorías de Bel; si el
   valor que trae Discogs no es una de ellas, lo agrega como opción extra. */
function setGenre(value) {
  const sel = $('#conf-genre');
  const opts = GENRES.slice();
  if (value && !opts.includes(value)) opts.unshift(value);
  sel.innerHTML = '<option value="">—</option>' +
    opts.map((g) => `<option>${escapeHtml(g)}</option>`).join('');
  sel.value = value || '';
}

/* Desplegable de GÉNERO específico (12): el que se escribe en el tag. */
function setGenreSpecific(value) {
  const sel = $('#conf-genre-specific');
  const opts = GENRES_SPEC.slice();
  if (value && !opts.includes(value)) opts.unshift(value);
  sel.innerHTML = '<option value="">—</option>' +
    opts.map((g) => `<option>${escapeHtml(g)}</option>`).join('');
  sel.value = value || '';
}

function setSearchStatus(text, cls) {
  const el = $('#search-status');
  el.textContent = text;
  el.className = 'small ' + (cls || 'muted');
}

function enterBuscar(reset) {
  renderItemList();
  if (reset || curIdx < 0 || curIdx >= state.items.length) {
    const i = nextPending();
    if (i >= 0) loadItem(i);
    else if (state.items.length) loadItem(0);
  }
}

function nextPending() {
  return state.items.findIndex((it) => it.status === 'pending');
}

function renderItemList() {
  const ul = $('#item-list');
  ul.innerHTML = '';
  state.items.forEach((it, idx) => {
    let prefix = '⧖ ', cls = 't-warn';
    if (it.status === 'confirmed') { prefix = '✓ '; cls = 't-ok'; }
    else if (it.flag) { prefix = '✗ '; cls = 't-flag'; }
    const li = document.createElement('li');
    li.className = cls + (idx === curIdx ? ' cur' : '');
    li.textContent = prefix + it.name;
    li.title = it.name;
    li.addEventListener('click', () => loadItem(idx));
    ul.appendChild(li);
  });

  const confirmed = state.items.filter((i) => i.status === 'confirmed').length;
  const flagged = state.items.filter(
    (i) => i.flag && i.status === 'pending').length;
  let txt = `${confirmed}/${state.items.length} confirmados`;
  if (flagged) txt += `  ·  ✗ ${flagged} para revisar`;
  $('#progress').textContent = txt;
  $('#btn-move').disabled = confirmed === 0;
}

function loadItem(idx) {
  if (idx < 0 || idx >= state.items.length) return;
  curIdx = idx;
  const it = state.items[idx];

  const tipo = it.type === 'album' ? '📁 EP/Album' : '🎵 Track';
  const dup = it.is_dup ? `    ⚠ YA EN HISTORIAL (${it.dup_fecha})` : '';
  const h2 = $('#cur-title');
  h2.textContent = `${tipo}: ${it.name}${dup}`;
  h2.style.color = it.is_dup ? 'var(--warning)' : 'var(--accent)';

  // La búsqueda arranca con el NOMBRE del archivo (más limpio que los tags ID3)
  $('#search-q').value = it.search_query || it.name;

  // Metadata que se va a escribir (editable): arranca de la data del NOMBRE
  // del archivo (la del track real), no de Discogs (que trae el álbum).
  $('#conf-title-lbl').textContent = it.type === 'album' ? 'Álbum' : 'Título';
  $('#conf-artist').value = it.name_artist || it.artist || '';
  $('#conf-title').value = it.name_title || '';

  setGenreSpecific(it.conf.genre_specific || '');
  setGenre(it.conf.genre || '');
  $('#conf-label').value = it.conf.label || '';
  $('#conf-year').value = it.conf.year || '';
  updatePreview();
  checkLabelSuggestion();

  $('#tbl-results tbody').innerHTML = '';
  results = []; selResult = -1;
  renderItemList();
  doSearch();
}

async function doSearch() {
  const q = $('#search-q').value.trim();
  if (!q || curIdx < 0) return;
  const it = state.items[curIdx];
  const seq = ++searchSeq;
  setSearchStatus('⧖ Buscando…');
  $('#tbl-results tbody').innerHTML = '';
  results = []; selResult = -1;

  const res = await api().search_discogs(q, it.artist || '');
  if (seq !== searchSeq) return;            // llegó tarde: hay una búsqueda más nueva

  if (res.error) { setSearchStatus('✗ Error: ' + res.error, 't-flag'); return; }

  if (!res.results.length) {
    if (!it.flag) { it.flag = 'noresult'; renderItemList(); }
    setSearchStatus('✗ Sin resultados — marcado para revisar (editá la búsqueda o probá Beatport)', 't-flag');
    return;
  }
  if (it.flag === 'noresult') { it.flag = ''; renderItemList(); }

  results = res.results;
  const fb = res.used_fallback ? ' (reintentó solo con el artista)' : '';
  setSearchStatus(`✓ ${results.length} resultados${fb} — seleccioná uno y confirmá`, 't-ok');
  renderResults();
  selectResult(0);
}

function renderResults() {
  const tbody = $('#tbl-results tbody');
  tbody.innerHTML = '';
  results.forEach((r, i) => {
    const tr = document.createElement('tr');
    [r.title, r.artist, r.genre, r.label, r.year, r.format].forEach((v) => {
      const td = document.createElement('td');
      td.textContent = v || '';
      tr.appendChild(td);
    });
    tr.addEventListener('click', () => selectResult(i));
    tr.addEventListener('dblclick', () => confirmCurrent());
    tbody.appendChild(tr);
  });
}

function selectResult(i) {
  if (i < 0 || i >= results.length) return;
  selResult = i;
  document.querySelectorAll('#tbl-results tbody tr').forEach(
    (tr, j) => tr.classList.toggle('sel', j === i));
  const r = results[i];
  // Discogs aporta sello/año (y la carpeta SOLO si quedó vacía: el género real
  // sale del tag del track, no de Discogs). Artista/Título NO se tocan: el
  // resultado es un release (su "título" es el álbum, no el track).
  if (!$('#conf-genre').value.trim()) setGenre(r.genre || '');
  $('#conf-label').value = r.label || '';
  $('#conf-year').value = r.year || '';
  updatePreview();
  checkLabelSuggestion();
}

// Los 6 campos de "Datos para mover" que tienen que estar completos para confirmar.
const CONF_FIELDS = ['#conf-artist', '#conf-title', '#conf-genre-specific',
                     '#conf-genre', '#conf-label', '#conf-year'];

function formValid() {
  return curIdx >= 0 && CONF_FIELDS.every((sel) => $(sel).value.trim() !== '');
}

// Habilita Confirmar solo si el ítem actual está pendiente, con los 6 campos,
// y sin un aviso de sello parecido pendiente de decidir.
function updateConfirmEnabled() {
  const it = curIdx >= 0 ? state.items[curIdx] : null;
  const confirmable = !!it && it.status !== 'confirmed' && formValid()
    && !labelWarningActive;
  $('#btn-confirm').disabled = !confirmable;
}

async function updatePreview() {
  updateConfirmEnabled();
  const el = $('#dest-preview');
  if (curIdx < 0) return;
  const g = $('#conf-genre').value.trim();
  const l = $('#conf-label').value.trim();
  const y = $('#conf-year').value.trim();
  if (g && l && y) {
    const dest = await api().preview_destination(
      $('#base-path').value.trim(), g, l, y, state.items[curIdx].name);
    el.textContent = '→ ' + dest;
    el.className = 'small ready';
  } else {
    el.textContent = '→ completá género, sello y año';
    el.className = 'small muted';
  }
}

// Aviso de sello parecido: si el Sello se parece a una carpeta que ya existe,
// BLOQUEA Confirmar hasta que decidas "Usar esa" o "No, crear nueva".
const HINT_BTN = 'margin-left:8px; padding:2px 10px; border-radius:6px; ' +
  'background:transparent; cursor:pointer; font-size:12px;';

async function checkLabelSuggestion() {
  const hint = $('#label-hint');
  const label = $('#conf-label').value.trim();
  if (!label || curIdx < 0) {
    labelWarningActive = false;
    hint.style.display = 'none'; hint.textContent = '';
    updateConfirmEnabled(); return;
  }
  let matches = [];
  try {
    matches = await api().suggest_labels($('#base-path').value.trim(), label);
  } catch (e) { matches = []; }
  if ($('#conf-label').value.trim() !== label) return;   // cambió mientras consultaba
  if (!matches || !matches.length) {
    labelWarningActive = false;
    hint.style.display = 'none'; hint.textContent = '';
    updateConfirmEnabled(); return;
  }
  const sug = matches[0];
  labelWarningActive = true;   // hay que decidir antes de poder confirmar
  hint.style.color = '#fc0b91';
  hint.textContent = '⚠ Ya existe una carpeta parecida: "' + sug + '"  ';

  const bUsar = document.createElement('button');
  bUsar.type = 'button';
  bUsar.textContent = 'Usar esa';
  bUsar.style.cssText = HINT_BTN + 'border:1px solid #fc0b91; color:#fc0b91;';
  bUsar.addEventListener('click', () => {
    $('#conf-label').value = sug;
    labelWarningActive = false;
    hint.style.display = 'none'; hint.textContent = '';
    updatePreview();
  });

  const bNueva = document.createElement('button');
  bNueva.type = 'button';
  bNueva.textContent = 'No, crear nueva';
  bNueva.style.cssText = HINT_BTN + 'border:1px solid #6b6b76; color:#b8b8c0;';
  bNueva.addEventListener('click', () => {
    labelWarningActive = false;
    hint.style.color = '#7bd88f';
    hint.textContent = '✓ Se creará "' + label + '" (carpeta nueva).';
    updateConfirmEnabled();
  });

  hint.appendChild(bUsar);
  hint.appendChild(bNueva);
  hint.style.display = '';
  updateConfirmEnabled();
}

async function confirmCurrent() {
  if (curIdx < 0) return;
  // Guarda: no confirmar sin los 6 campos (el botón ya está grisado, pero
  // reforzamos por si se llama de otra forma, ej. doble-clic en un resultado).
  if (!formValid()) {
    setSearchStatus('✗ Completá los 6 campos (artista, título, género, carpeta, sello y año) antes de confirmar', 't-flag');
    return;
  }
  if (labelWarningActive) {
    setSearchStatus('✗ Decidí primero sobre la carpeta de sello parecida ("Usar esa" o "No, crear nueva")', 't-flag');
    return;
  }
  const it = state.items[curIdx];
  const g = $('#conf-genre').value.trim();
  const l = $('#conf-label').value.trim();
  const y = $('#conf-year').value.trim();
  try {
    // Guardar la metadata editada (se escribe en los tags al mover)
    const artist = $('#conf-artist').value.trim();
    const titleVal = $('#conf-title').value.trim();
    it.artist = artist;
    if (it.type === 'album') it.album = titleVal;
    else it.title = titleVal;

    const gs = $('#conf-genre-specific').value.trim();
    it.conf = { genre: g, genre_specific: gs, label: l, year: y };
    it.status = 'confirmed';
    it.flag = '';
    it.destination = await api().preview_destination(
      $('#base-path').value.trim(), g, l, y, it.name);
    renderItemList();
    updateConfirmEnabled();   // el ítem quedó confirmado -> el botón se grisa
    const nxt = nextPending();
    if (nxt >= 0) loadItem(nxt);
    else setSearchStatus('✓ Todos los ítems procesados — dale a ▶ Mover', 't-ok');
  } catch (e) {
    setSearchStatus('✗ Error al confirmar: ' + (e && e.message ? e.message : e), 't-flag');
  }
}

$('#btn-search').addEventListener('click', doSearch);
$('#search-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });

$('#btn-beatport').addEventListener('click', () => {
  const q = $('#search-q').value.trim();
  if (q) api().open_beatport(q);
});

$('#btn-confirm').addEventListener('click', confirmCurrent);

// Al editar cualquiera de los 6 campos: si el ítem ya estaba confirmado, vuelve
// a 'pendiente' (para poder reconfirmar), y se revalida el botón y el preview.
function onConfFieldEdit() {
  const it = curIdx >= 0 ? state.items[curIdx] : null;
  if (it && it.status === 'confirmed') {
    it.status = 'pending';
    renderItemList();
  }
  updatePreview();
}
CONF_FIELDS.forEach((sel) => {
  const el = $(sel);
  el.addEventListener('input', onConfFieldEdit);
  el.addEventListener('change', onConfFieldEdit);
});

// Chequear sello parecido cada vez que se edita el campo Sello.
$('#conf-label').addEventListener('input', checkLabelSuggestion);

$('#btn-discard').addEventListener('click', () => {
  if (curIdx < 0) return;
  const id = state.items[curIdx].id;
  state.items = state.items.filter((i) => i.id !== id);
  renderLoadTable();   // mantener sincronizada la lista de Cargar

  if (!state.items.length) {
    curIdx = -1;
    renderItemList();
    $('#cur-title').textContent = '← No quedan ítems';
    $('#cur-title').style.color = 'var(--muted)';
    $('#search-q').value = '';
    $('#tbl-results tbody').innerHTML = '';
    results = []; selResult = -1;
    setSearchStatus('', 'muted');
    return;
  }
  loadItem(Math.min(curIdx, state.items.length - 1));
});

['#conf-genre', '#conf-label', '#conf-year'].forEach((sel) => {
  $(sel).addEventListener('input', updatePreview);
});

// Al cambiar el género específico (tag), re-sugerir la carpeta (4).
$('#conf-genre-specific').addEventListener('change', () => {
  const spec = $('#conf-genre-specific').value.trim();
  if (spec && SPEC2BROAD[spec]) setGenre(SPEC2BROAD[spec]);
  updatePreview();
});

document.getElementById('nav-buscar').addEventListener('click', () => enterBuscar(false));

/* ── Vista Resultado: mover + deshacer ───────────────────── */
$('#btn-move').addEventListener('click', moveConfirmed);

async function moveConfirmed() {
  const ready = state.items.filter((i) => i.status === 'confirmed');
  if (!ready.length) { setSearchStatus('✗ No hay ítems confirmados', 't-flag'); return; }

  const dups = ready.filter((i) => i.is_dup).length;
  let msg = `¿Mover ${ready.length} ítem${ready.length > 1 ? 's' : ''} ahora?`;
  if (dups) msg += `\n\n⚠ ${dups} ya figura${dups > 1 ? 'n' : ''} en tu historial.`;
  msg += '\n\nVas a poder deshacerlo desde la pantalla de Resultado.';
  if (!(await confirmModal('Confirmar', msg))) return;

  showView('resultado');
  $('#move-log').textContent = 'Moviendo…';

  const payload = ready.map((i) => ({
    type: i.type, path: i.path, name: i.name,
    artist: i.artist, title: i.title, album: i.album,
    genre: i.conf.genre, genre_specific: i.conf.genre_specific,
    label: i.conf.label, year: i.conf.year,
  }));
  const res = await api().move_items(
    payload, $('#base-path').value.trim(), $('#period').value.trim());

  renderMoveResult(res);

  const moved = new Set(res.moved_sources);
  state.items = state.items.filter((i) => !moved.has(i.path));
  curIdx = -1;
  renderLoadTable();
  renderItemList();
}

function renderMoveResult(res) {
  $('#st-tracks').textContent = res.moved;
  $('#st-albums').textContent = res.moved_albums;
  $('#st-folders').textContent = res.new_folders;
  $('#st-errors').textContent = res.errors;

  const logEl = $('#move-log');
  logEl.innerHTML = '';
  res.log.forEach((e) => {
    const span = document.createElement('span');
    span.className = 'log-' + e.kind;
    span.textContent = e.text + '\n';
    logEl.appendChild(span);
  });
  const movedAny = (res.moved + res.moved_albums) > 0;
  $('#btn-undo').disabled = !movedAny;
  lastOpenDir = res.open_dir || '';
  $('#btn-open-folder').disabled = !movedAny || !lastOpenDir;
  updatePeriodCount(res.txt_count);
}

let lastOpenDir = '';
$('#btn-open-folder').addEventListener('click', () => {
  if (lastOpenDir) api().open_in_explorer(lastOpenDir);
});

function appendLog(text, kind) {
  const span = document.createElement('span');
  span.className = 'log-' + kind;
  span.textContent = text + '\n';
  $('#move-log').appendChild(span);
}

$('#btn-undo').addEventListener('click', async () => {
  if (!(await confirmModal('Deshacer movimiento',
        '¿Devolver los archivos a su ubicación original?'))) return;
  const out = await api().undo_last_move();
  let msg = `⮌ ${out.restored} restaurado${out.restored !== 1 ? 's' : ''}`;
  if (out.skipped || out.errors) {
    msg += ` · ${out.skipped + out.errors} con problemas: ` +
      out.problems.slice(0, 4).join('; ');
  }
  appendLog('\n' + msg, 'warn');
  $('#btn-undo').disabled = true;
  await refreshPeriodCount();
});

$('#btn-new').addEventListener('click', async () => {
  if (state.items.length &&
      !(await confirmModal('Nuevo', '¿Empezar de nuevo? Se limpia la lista de ítems.'))) return;
  state.items = []; curIdx = -1;
  renderLoadTable(); renderItemList();
  $('#move-log').textContent = '';
  ['tracks', 'albums', 'folders', 'errors'].forEach((k) => { $('#st-' + k).textContent = '0'; });
  $('#btn-undo').disabled = true;
  showView('cargar');
});

/* ── Período ─────────────────────────────────────────────── */
function defaultPeriod() {
  const d = new Date();
  return d.getFullYear() + '_' + (d.getMonth() < 6 ? '06' : '12');
}

function updatePeriodCount(n) {
  const name = $('#period').value.trim();
  $('#period-count').textContent = n
    ? `Período ${name}: ${n} track${n > 1 ? 's' : ''} acumulado${n > 1 ? 's' : ''}`
    : `Período ${name}: sin tracks aún`;
}

async function refreshPeriodCount() {
  const n = await api().get_period_count(
    $('#base-path').value.trim(), $('#period').value.trim());
  updatePeriodCount(n);
}

$('#period').addEventListener('change', refreshPeriodCount);

/* ── Vista Historial ─────────────────────────────────────── */
let history = [];
let ctxDestino = '';

async function loadHistory() {
  history = await api().get_history();
  populateGenreFilter();
  renderHistory();
}

function populateGenreFilter() {
  const sel = $('#hist-genre');
  const cur = sel.value;
  const genres = [...new Set(history.map((h) => h.genero).filter(Boolean))].sort();
  sel.innerHTML = '<option value="">Todos los géneros</option>' +
    genres.map((g) => `<option>${escapeHtml(g)}</option>`).join('');
  sel.value = cur;   // preservar la selección si todavía existe
}

function renderHistory() {
  const flt = $('#hist-search').value.trim().toLowerCase();
  const gen = $('#hist-genre').value;
  const tbody = $('#tbl-hist tbody');
  tbody.innerHTML = '';
  let shown = 0;

  history.slice().reverse().forEach((h) => {
    if (gen && (h.genero || '') !== gen) return;
    if (flt) {
      const blob = [h.artista, h.track, h.genero, h.sello, h.destino]
        .join(' ').toLowerCase();
      if (!blob.includes(flt)) return;
    }
    const tr = document.createElement('tr');
    [h.fecha, h.artista, h.track, h.genero, h.sello, h['año'], h.destino]
      .forEach((v) => {
        const td = document.createElement('td');
        td.textContent = v || '';
        td.title = v || '';        // ver texto completo al pasar el mouse
        tr.appendChild(td);
      });
    tr.addEventListener('dblclick', () => api().open_in_explorer(h.destino));
    tr.addEventListener('contextmenu', (e) => showCtxMenu(e, h.destino));
    tbody.appendChild(tr);
    shown++;
  });

  $('#hist-empty').style.display = history.length ? 'none' : 'block';
  const total = history.length;
  $('#hist-count').textContent = total === 0 ? 'Sin registros aún'
    : ((flt || gen) ? `${shown} de ${total} registros`
                    : `${total} registro${total !== 1 ? 's' : ''}`);
}

$('#hist-search').addEventListener('input', renderHistory);
$('#hist-genre').addEventListener('change', renderHistory);

function showCtxMenu(e, destino) {
  e.preventDefault();
  ctxDestino = destino;
  const m = $('#ctx-menu');
  m.style.left = e.clientX + 'px';
  m.style.top = e.clientY + 'px';
  m.classList.add('show');
}

document.addEventListener('click', () => $('#ctx-menu').classList.remove('show'));

$('#ctx-menu').addEventListener('click', async (e) => {
  const act = e.target.dataset.act;
  if (!act || !ctxDestino) return;
  if (act === 'open') api().open_in_explorer(ctxDestino);
  else if (act === 'edit') openRecatModal(ctxDestino);
  else if (act === 'copy') navigator.clipboard.writeText(ctxDestino);
  else if (act === 'del') {
    if (await confirmModal('Eliminar registro',
        'Quitar este registro del historial?\nNO borra ni mueve el archivo de música.')) {
      await api().delete_history_entry(ctxDestino);
      await loadHistory();
    }
  }
});

/* Corregir ubicación (re-categorizar) de una entrada del historial */
let recatDestino = '';

function openRecatModal(destino) {
  const h = history.find((x) => x.destino === destino);
  if (!h) return;
  recatDestino = destino;
  $('#recat-info').textContent = `${h.artista || '—'} — ${h.track || ''}`;
  const sel = $('#recat-genre');
  const opts = GENRES.slice();
  if (h.genero && !opts.includes(h.genero)) opts.unshift(h.genero);
  sel.innerHTML = opts.map((g) => `<option>${escapeHtml(g)}</option>`).join('');
  sel.value = h.genero || '';
  $('#recat-label').value = h.sello || '';
  $('#recat-year').value = h['año'] || '';
  $('#recat-clean').checked = true;
  $('#recat-err').textContent = '';
  $('#recat-overlay').classList.add('show');
}

$('#recat-cancel').addEventListener('click',
  () => $('#recat-overlay').classList.remove('show'));

$('#recat-save').addEventListener('click', async () => {
  const genre = $('#recat-genre').value.trim();
  const label = $('#recat-label').value.trim();
  const year = $('#recat-year').value.trim();
  if (!genre || !label || !year) {
    $('#recat-err').textContent = '✗ Completá género, sello y año.';
    return;
  }
  const res = await api().recategorize_entry(
    recatDestino, genre, label, year, $('#recat-clean').checked);
  if (res.error) { $('#recat-err').textContent = '✗ ' + res.error; return; }
  $('#recat-overlay').classList.remove('show');
  await loadHistory();
});

$('#btn-hist-clear').addEventListener('click', async () => {
  if (!history.length) return;
  if (await confirmModal('Limpiar historial',
      `¿Borrar los ${history.length} registros del historial?\n\n` +
      'Esto NO borra ni mueve ningún archivo de música, solo el registro.')) {
    await api().clear_history();
    await loadHistory();
  }
});

$('#btn-hist-csv').addEventListener('click', async () => {
  const res = await api().export_history();
  if (!res) return;                                   // canceló el diálogo
  if (res.error) { await confirmModal('Exportar', res.error); return; }
  if (await confirmModal('Exportado ✓',
      'Historial guardado en:\n' + res.path + '\n\n¿Abrir la carpeta?')) {
    api().open_in_explorer(res.path);
  }
});

document.getElementById('nav-historial').addEventListener('click', loadHistory);

/* ── Handshake con Python ────────────────────────────────── */
window.addEventListener('pywebviewready', async () => {
  try {
    const cfg = await api().get_config();
    $('#base-path').value = cfg.base_path;
    $('#token').value = cfg.discogs_token;
    GENRES = await api().get_genres();
    GENRES_SPEC = await api().get_genres_specific();
    SPEC2BROAD = await api().get_specific_to_broad();
    setGenre('');
    setGenreSpecific('');
    $('#period').value = defaultPeriod();
    await refreshPeriodCount();
    $('#status').textContent =
      'Conectado · Carpeta base: ' + cfg.base_path +
      (cfg.discogs_token ? ' · Token ✓' : ' · Sin token');
  } catch (err) {
    $('#status').textContent = 'Error de puente: ' + err;
  }
});

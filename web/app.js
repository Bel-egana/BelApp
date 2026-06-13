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

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
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
    it.conf = { genre: it.genre, label: it.label, year: it.year };
    state.items.push(it);
  });
  renderLoadTable();
}

function removeItem(id) {
  state.items = state.items.filter((i) => i.id !== id);
  renderLoadTable();
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

    const tr = document.createElement('tr');
    tr.innerHTML =
      `<td class="muted">${it.type === 'album' ? 'EP/ALBUM' : 'TRACK'}</td>` +
      `<td class="${nameCls}">${escapeHtml(nameTxt)}</td>` +
      `<td>${escapeHtml(it.artist || '—')}</td>` +
      `<td class="${tagsCls}">${tagsTxt}</td>` +
      `<td><button class="row-x" title="Quitar">✕</button></td>`;
    tr.querySelector('.row-x').addEventListener('click', () => removeItem(it.id));
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
  const res = await api().load_tracks(paths, itemNames(), state.items.length);
  addItems(res.items);
  loadSummary(res);
});

$('#btn-add-album').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (!p) return;
  const res = await api().load_album_folder(p, itemNames(), state.items.length);
  if (res.error) { flashMsg('✗ ' + res.error); return; }
  addItems([res.item]);
});

$('#btn-scan').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (!p) return;
  const res = await api().scan_folder(p, itemNames(), state.items.length);
  if (res.error) { flashMsg('✗ ' + res.error); return; }
  addItems(res.items);
  loadSummary(res);
});

$('#btn-clear').addEventListener('click', async () => {
  if (!state.items.length) return;
  if (await api().confirm('Limpiar', '¿Borrar la lista de ítems cargados?')) {
    state.items = [];
    renderLoadTable();
  }
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

  const titlePart = it.type === 'album' ? (it.album || it.name) : (it.title || it.name);
  $('#search-q').value = `${it.artist} ${titlePart}`.trim();

  $('#conf-genre').value = it.conf.genre || '';
  $('#conf-label').value = it.conf.label || '';
  $('#conf-year').value = it.conf.year || '';
  updatePreview();

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
  $('#conf-genre').value = r.genre || '';
  $('#conf-label').value = r.label || '';
  $('#conf-year').value = r.year || '';
  updatePreview();
}

async function updatePreview() {
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

async function confirmCurrent() {
  if (curIdx < 0) return;
  const it = state.items[curIdx];
  const g = $('#conf-genre').value.trim();
  const l = $('#conf-label').value.trim();
  const y = $('#conf-year').value.trim();
  if (!g || !l || !y) {
    setSearchStatus('✗ Completá género, sello y año antes de confirmar', 't-flag');
    return;
  }
  it.conf = { genre: g, label: l, year: y };
  it.status = 'confirmed';
  it.flag = '';
  it.destination = await api().preview_destination(
    $('#base-path').value.trim(), g, l, y, it.name);
  renderItemList();
  const nxt = nextPending();
  if (nxt >= 0) loadItem(nxt);
  else setSearchStatus('✓ Todos los ítems procesados — dale a ▶ Mover', 't-ok');
}

$('#btn-search').addEventListener('click', doSearch);
$('#search-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });

$('#btn-beatport').addEventListener('click', () => {
  const q = $('#search-q').value.trim();
  if (q) api().open_beatport(q);
});

$('#btn-use').addEventListener('click', () => {
  if (selResult >= 0) selectResult(selResult);
  else setSearchStatus('✗ Seleccioná un resultado primero', 't-flag');
});

$('#btn-confirm').addEventListener('click', confirmCurrent);

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

$('#btn-flag').addEventListener('click', () => {
  if (curIdx < 0) return;
  const it = state.items[curIdx];
  it.flag = it.flag ? '' : 'review';
  renderItemList();
});

['#conf-genre', '#conf-label', '#conf-year'].forEach((sel) => {
  $(sel).addEventListener('input', updatePreview);
});

$('#btn-move').addEventListener('click', () => {
  setSearchStatus('▶ Mover llega en la próxima tarea 😉', 'muted');
});

document.getElementById('nav-buscar').addEventListener('click', () => enterBuscar(false));

/* ── Handshake con Python ────────────────────────────────── */
window.addEventListener('pywebviewready', async () => {
  try {
    const cfg = await api().get_config();
    $('#base-path').value = cfg.base_path;
    $('#token').value = cfg.discogs_token;
    const genres = await api().get_genres();
    $('#genres-dl').innerHTML =
      genres.map((g) => `<option value="${escapeHtml(g)}">`).join('');
    $('#status').textContent =
      'Conectado · Carpeta base: ' + cfg.base_path +
      (cfg.discogs_token ? ' · Token ✓' : ' · Sin token');
  } catch (err) {
    $('#status').textContent = 'Error de puente: ' + err;
  }
});

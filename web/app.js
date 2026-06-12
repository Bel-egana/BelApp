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
});

/* ── Handshake con Python ────────────────────────────────── */
window.addEventListener('pywebviewready', async () => {
  try {
    const cfg = await api().get_config();
    $('#base-path').value = cfg.base_path;
    $('#token').value = cfg.discogs_token;
    $('#status').textContent =
      'Conectado · Carpeta base: ' + cfg.base_path +
      (cfg.discogs_token ? ' · Token ✓' : ' · Sin token');
  } catch (err) {
    $('#status').textContent = 'Error de puente: ' + err;
  }
});

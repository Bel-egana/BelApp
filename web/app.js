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
function confirmModal(title, message, okLabel) {
  return new Promise((resolve) => {
    const ov = $('#modal-overlay');
    const okBtn = $('#modal-ok');
    const cancelBtn = $('#modal-cancel');
    $('#modal-title').textContent = title;
    $('#modal-msg').textContent = message;
    okBtn.textContent = okLabel || 'Aceptar';   // etiqueta opcional del botón OK
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

/* Muestra "Analizando música…" solo si el índice de duplicados de la
   biblioteca todavía no está en caché (primera carga tras abrir la app o
   cambiar la carpeta base). Devuelve true si mostró el aviso. */
async function avisarAnalisis() {
  try {
    if (!(await api().disk_index_listo())) {
      flashMsg('🔍 Analizando tu música… (buscando duplicados en tu biblioteca)', 60000);
      await new Promise((r) => setTimeout(r, 60));   // deja pintar el mensaje
      return true;
    }
  } catch (e) { /* si falla el chequeo, seguimos sin aviso */ }
  return false;
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

// Compara dos tamaños con tolerancia (100 KB o 1%): 'igual' si la diferencia
// es chica (no significativa para la calidad), o 'a'/'b' según cuál es más grande.
function compararTamano(sa, sb) {
  const diff = Math.abs(sa - sb);
  const tol = Math.max(102400, 0.01 * Math.max(sa, sb));
  if (diff <= tol) return 'igual';
  return sa > sb ? 'a' : 'b';
}

async function showDupInfo(it) {
  // Compilado con varios tracks ya en la biblioteca: los listamos TODOS de una.
  const all = it.dup_all || [];
  if (it.type === 'album' && all.length) {
    let msg = `Este compilado tiene ${all.length} track(s) que YA están en tu ` +
      `biblioteca:\n\n`;
    all.forEach((x) => {
      const nombre = (x.nombre || '').replace(/\.[^.]+$/, '');
      msg += `• ${nombre}\n   → ${x.destino}\n`;
    });
    msg += '\nSon coincidencias por nombre de archivo (puede ser el mismo tema ' +
      'en otra compilación). Vos decidís y borrás a mano — la app no borra nada.';
    await confirmModal('Ya en tu biblioteca', msg);
    return;
  }

  const d = it.dup_info || {};
  const enBiblio = d.origen === 'biblioteca' || !d.fecha;
  let msg = enBiblio
    ? 'Este track YA está en tu biblioteca (encontrado en disco):\n\n'
    : 'Este ítem coincide con algo que YA ordenaste:\n\n';
  if (!enBiblio) {
    msg +=
      `• Artista:  ${d.artista || '—'}\n` +
      `• Track:  ${d.track || '—'}\n` +
      `• Fecha:  ${d.fecha || '—'}\n` +
      `• Género:  ${d.genero || '—'}\n` +
      `• Sello:  ${d.sello || '—'}\n`;
  }
  msg += `• Ubicación:  ${d.destino || '—'}\n`;

  // Comparación de tamaño (calidad) entre el cargado y el ya ordenado.
  try {
    const s = await api().tamano_archivos(it.path, d.destino);
    if (s.a >= 0 && s.b >= 0) {
      const mb = (b) => (b / 1048576).toFixed(1) + ' MB';
      const cmp = compararTamano(s.a, s.b);
      let reco;
      if (cmp === 'igual') reco = 'prácticamente el mismo tamaño (probablemente idéntico) — cualquiera sirve';
      else if (cmp === 'a') reco = 'el que cargaste es MÁS GRANDE → conviene quedarte con este y borrar el que ya tenés';
      else reco = 'el que ya tenés es MÁS GRANDE → conviene quedarte con ese y borrar el que cargaste';
      msg += `\n📊 Calidad (por tamaño):\n` +
        `   • Este (cargado):  ${mb(s.a)}\n` +
        `   • El que ya tenés:  ${mb(s.b)}\n` +
        `   → ${reco}\n`;
    }
  } catch (e) { /* si falla, seguimos sin la comparación */ }

  msg += '\nCoincide por nombre de archivo: puede ser el mismo tema en otra ' +
    'compilación. (Vos decidís y borrás a mano — la app no borra nada.)';
  confirmModal('Ya en tu biblioteca', msg);
}

function renderLoadTable() {
  const tbody = $('#tbl-load tbody');
  tbody.innerHTML = '';
  let dups = 0;

  state.items.forEach((it) => {
    if (it.is_dup) dups++;
    const tagsTxt = it.is_dup ? '⚠ YA EN BIBLIOTECA'
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
  if (dups) txt += `   ·   ⚠ ${dups} ya en tu biblioteca — quitalos para continuar`;
  $('#load-count').textContent = txt;
  $('#btn-remove-dups').style.display = dups ? '' : 'none';
  $('#btn-continue').disabled = state.items.length === 0 || dups > 0;
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
  const analizando = await avisarAnalisis();
  const res = await api().load_tracks(paths, itemPaths(), state.items.length);
  if (analizando) flashMsg('');
  addItems(res.items);
  loadSummary(res);
});

$('#btn-add-album').addEventListener('click', async () => {
  const paths = await api().pick_folders();
  if (!paths.length) return;
  const analizando = await avisarAnalisis();
  const res = await api().load_album_folders(paths, itemPaths(), state.items.length);
  if (analizando) flashMsg('');
  addItems(res.items);
  loadSummary(res);
  if (res.no_audio && res.no_audio.length) {
    flashMsg(`Cargados ${res.items.length}. ⚠ ${res.no_audio.length} carpeta(s) sin audio se saltearon.`);
  }
});

$('#btn-scan').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (!p) return;
  // Escanea la carpeta: tracks sueltos + subcarpetas de álbum, salteando las
  // carpetas con nombre de año (ya organizadas).
  const analizando = await avisarAnalisis();
  const res = await api().scan_folder(p, itemPaths(), state.items.length, true);
  if (analizando) flashMsg('');
  if (res.error) { flashMsg('✗ ' + res.error); return; }
  if (!res.items.length) {
    let msg;
    if (res.skipped_years) {
      msg = `Esa carpeta ya está ordenada: solo tiene ${res.skipped_years} carpeta(s) de año y nada suelto para cargar.`;
    } else if (res.skipped) {
      msg = 'Todo lo de esa carpeta ya estaba cargado en la lista.';
    } else {
      msg = 'No hay nada para cargar en esa carpeta (sin tracks sueltos ni álbumes).';
    }
    await confirmModal('Escanear carpeta', msg);
    return;
  }
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
  flashMsg('⏳ Analizando la carpeta… puede tardar. No cierres la app.', 600000);
  const r = await api().review_folder_genres(folder);
  flashMsg('');   // terminó
  if (r.error) { await confirmModal('Normalizar géneros', '✗ ' + r.error); return; }
  if (!r.total) {
    await confirmModal('Normalizar géneros', 'No hay tracks de audio en esa carpeta.');
    return;
  }
  openNormReview(r);
});

$('#btn-dups').addEventListener('click', async () => {
  const folder = await api().pick_folder();
  if (!folder) return;
  flashMsg('⏳ Buscando duplicados… puede tardar (escanea la carpeta y tu biblioteca). No cierres la app.', 600000);
  const r = await api().buscar_duplicados_carpeta(folder);
  flashMsg('');
  if (r.error) { await confirmModal('Buscar duplicados', '✗ ' + r.error); return; }
  if (!r.grupos) {
    await confirmModal('Buscar duplicados', '✅ No se encontraron duplicados en esa carpeta.');
    return;
  }
  const abrir = await confirmModal('Buscar duplicados',
    `🔍 Se encontraron ${r.grupos} grupo(s) de tracks duplicados.\n\n` +
    `El detalle (rutas + tamaño de cada copia + recomendación de cuál conservar) ` +
    `está en el archivo "${r.report_file}" dentro de esa carpeta.\n\n` +
    '🛡️ BelApp NO borra nada — vos revisás y borrás a mano lo que quieras.',
    '📂 Abrir carpeta');
  if (abrir) api().open_in_explorer(r.folder);
});

/* ── Completar años de una carpeta (en lote) ─────────────── */
let yearRows = [];

function updateYearCount() {
  const conAnio = yearRows.filter((x) => /^(19|20)\d\d$/.test(x.inp.value.trim())).length;
  const tildados = yearRows.filter((x) => x.chk.checked).length;
  $('#year-count').textContent = `${conAnio} con año válido · ${tildados} tildados`;
}

function applyYearFilter() {
  const solo = $('#year-only-empty').checked;
  yearRows.forEach((x) => { x.row.hidden = solo && x.current !== ''; });
}
$('#year-only-empty').addEventListener('change', applyYearFilter);

function openYearReview(r) {
  const list = $('#year-list');
  list.innerHTML = '';
  yearRows = [];
  $('#year-sub').textContent =
    `${r.total} tracks · ${r.sin_anio} sin año. Escribí el año en cada fila, o tildá varios ` +
    'que compartan año y usá "Asignar a tildados". Solo toca el tag, NO mueve archivos.';
  r.tracks.forEach((t) => {
    const row = document.createElement('div');
    row.className = 'norm-row';
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.addEventListener('change', updateYearCount);
    const name = document.createElement('div');
    name.className = 'nr-name';
    name.textContent = normBase(t.path);
    name.title = t.path;
    const old = document.createElement('div');
    old.className = 'nr-old';
    old.textContent = (t.current || '(sin año)') + '  →';
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.placeholder = 'año';
    inp.style.width = '70px';
    inp.value = t.current || t.suggested || '';   // pre-carga el actual o el sugerido
    inp.addEventListener('input', updateYearCount);
    row.append(chk, name, old, inp);
    list.appendChild(row);
    yearRows.push({ path: t.path, chk, inp, current: t.current || '', row });
  });
  $('#year-only-empty').checked = true;   // arranca mostrando solo los sin año
  applyYearFilter();
  updateYearCount();
  $('#year-overlay').classList.add('show');
}

$('#btn-years').addEventListener('click', async () => {
  const folder = await api().pick_folder();
  if (!folder) return;
  flashMsg('⏳ Analizando la carpeta… no cierres la app.', 600000);
  const r = await api().review_folder_years(folder);
  flashMsg('');
  if (r.error) { await confirmModal('Completar años', '✗ ' + r.error); return; }
  if (!r.total) { await confirmModal('Completar años', 'No hay tracks de audio en esa carpeta.'); return; }
  openYearReview(r);
});

$('#year-all').addEventListener('click', () => {
  yearRows.forEach((x) => { if (!x.row.hidden) x.chk.checked = true; });
  updateYearCount();
});
$('#year-none').addEventListener('click', () => {
  yearRows.forEach((x) => { if (!x.row.hidden) x.chk.checked = false; });
  updateYearCount();
});
$('#year-assign').addEventListener('click', () => {
  const y = $('#year-bulk').value.trim();
  if (!/^(19|20)\d\d$/.test(y)) { flashMsg('✗ Escribí un año válido (ej. 2023)'); return; }
  let n = 0;
  yearRows.forEach((x) => {
    if (x.chk.checked) { x.inp.value = y; x.chk.checked = false; n++; }
  });
  flashMsg(n ? `✓ Año ${y} asignado a ${n} track(s)` : '✗ Tildá primero los tracks');
  updateYearCount();
});
$('#year-cancel').addEventListener('click', () => $('#year-overlay').classList.remove('show'));
$('#year-apply').addEventListener('click', async () => {
  const items = yearRows
    .filter((x) => /^(19|20)\d\d$/.test(x.inp.value.trim()) && x.inp.value.trim() !== x.current)
    .map((x) => ({ path: x.path, year: x.inp.value.trim() }));
  if (!items.length) { flashMsg('✗ No hay años nuevos para aplicar'); return; }
  $('#year-overlay').classList.remove('show');
  flashMsg('⏳ Escribiendo años… no cierres la app.', 600000);
  const res = await api().apply_years_selected(items);
  flashMsg('');
  const errTxt = (res.errors && res.errors.length) ? `\n\n⚠ ${res.errors.length} con error.` : '';
  await confirmModal('Listo ✓', `${res.applied} años actualizados.${errTxt}`);
});

function normBase(p) { return String(p).split(/[\\/]/).pop(); }

function updateNormCount() {
  const conGenero = normRows.filter((x) => x.sel.value).length;
  const tildados = normRows.filter((x) => x.chk.checked).length;
  $('#norm-count').textContent = `${conGenero} con género · ${tildados} tildados`;
  $('#norm-apply').disabled = conGenero === 0;
}

function openNormReview(r) {
  const list = $('#norm-list');
  list.innerHTML = '';
  normRows = [];

  // Desplegable de "asignar a tildados" (una sola vez).
  const bulk = $('#norm-bulk');
  if (!bulk.options.length) {
    const ph = document.createElement('option');
    ph.value = ''; ph.textContent = '(elegí género)';
    bulk.appendChild(ph);
    GENRES_SPEC.forEach((g) => {
      const o = document.createElement('option');
      o.value = g; o.textContent = g;
      bulk.appendChild(o);
    });
  }

  $('#norm-sub').textContent =
    `${r.total} tracks · ${r.con_sugerencia} con sugerencia · ${r.sin_genero} sin género. ` +
    'Elegí el género en cada fila, o tildá varios que compartan género y usá "Asignar a tildados". ' +
    'Se aplican los que tengan género elegido. Solo toca el tag, NO mueve archivos.';

  r.tracks.forEach((t) => {
    const row = document.createElement('div');
    row.className = 'norm-row';

    const chk = document.createElement('input');
    chk.type = 'checkbox';                      // selección para asignar en lote
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
      if (g === t.suggested) o.selected = true;   // pre-carga la sugerencia si hay
      sel.appendChild(o);
    });
    sel.addEventListener('change', updateNormCount);

    row.append(chk, name, old, sel);
    list.appendChild(row);
    normRows.push({ path: t.path, chk, sel, current: t.current || '', row });
  });
  $('#norm-only-empty').checked = false;   // arranca sin filtro
  applyNormFilter();
  updateNormCount();
  $('#norm-overlay').classList.add('show');
}

/* Filtro "Solo sin género": muestra solo las filas sin género actual. */
function applyNormFilter() {
  const soloVacios = $('#norm-only-empty').checked;
  normRows.forEach((x) => { x.row.hidden = soloVacios && x.current !== ''; });
}
$('#norm-only-empty').addEventListener('change', applyNormFilter);

$('#norm-all').addEventListener('click', () => {
  normRows.forEach((x) => { if (!x.row.hidden) x.chk.checked = true; });   // solo las visibles
  updateNormCount();
});
$('#norm-none').addEventListener('click', () => {
  normRows.forEach((x) => { if (!x.row.hidden) x.chk.checked = false; });
  updateNormCount();
});
$('#norm-assign').addEventListener('click', () => {
  const g = $('#norm-bulk').value;
  if (!g) { flashMsg('✗ Elegí un género arriba para asignar'); return; }
  let n = 0;
  normRows.forEach((x) => {
    if (x.chk.checked) { x.sel.value = g; x.chk.checked = false; n++; }
  });
  flashMsg(n ? `✓ "${g}" asignado a ${n} track(s)` : '✗ Tildá primero los tracks a asignar');
  updateNormCount();
});
$('#norm-cancel').addEventListener('click', () => $('#norm-overlay').classList.remove('show'));

$('#norm-apply').addEventListener('click', async () => {
  const items = normRows.filter((x) => x.sel.value)
    .map((x) => ({ path: x.path, new: x.sel.value }));
  if (!items.length) return;
  $('#norm-overlay').classList.remove('show');
  flashMsg('⏳ Aplicando cambios… no cierres la app.', 600000);
  const res = await api().apply_normalize_selected(items);
  flashMsg('');   // terminó
  const errTxt = (res.errors && res.errors.length)
    ? `\n\n⚠ ${res.errors.length} con error (no se pudieron escribir).` : '';
  await confirmModal('Listo ✓',
    `${res.applied} géneros actualizados.${errTxt}\n\n` +
    'En Traktor: re-importá/actualizá la carpeta para ver los tags nuevos.');
  await loadHistory();   // refleja los géneros nuevos en el Historial y el contador
});

$('#btn-playlists').addEventListener('click', () => {
  const base = $('#base-path').value.trim();
  if (!base) { confirmModal('Generar playlists', '✗ Falta la carpeta base de música.'); return; }
  // Poblar el selector de género: "Todos" + los géneros específicos.
  const sel = $('#pl-genre');
  sel.innerHTML = '';
  const todos = document.createElement('option');
  todos.value = ''; todos.textContent = 'Todos los géneros';
  sel.appendChild(todos);
  GENRES_SPEC.forEach((g) => {
    const o = document.createElement('option');
    o.value = g; o.textContent = g;
    sel.appendChild(o);
  });
  $('#pl-year').value = '';
  $('#pl-source').value = '';
  $('#pl-dest').value = '';
  $('#pl-overlay').classList.add('show');
});
$('#pl-cancel').addEventListener('click', () => $('#pl-overlay').classList.remove('show'));

$('#pl-pick-source').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (p) $('#pl-source').value = p;
});
$('#pl-pick-dest').addEventListener('click', async () => {
  const p = await api().pick_folder();
  if (p) $('#pl-dest').value = p;
});

$('#pl-go').addEventListener('click', async () => {
  const base = $('#base-path').value.trim();
  const source = $('#pl-source').value.trim() || base;   // vacío = toda la biblioteca
  const dest = $('#pl-dest').value.trim();
  const genre = $('#pl-genre').value;      // '' = todos
  const year = $('#pl-year').value.trim();  // '' = todos
  if (!dest) { flashMsg('✗ Elegí la carpeta "Guardar en"'); return; }
  $('#pl-overlay').classList.remove('show');
  // Mensaje persistente (10 min): se mantiene TODO el análisis y se saca al terminar.
  flashMsg('⏳ Analizando la carpeta y generando playlists… puede tardar varios minutos. No cierres la app.', 600000);
  const res = await api().generate_playlists(source, dest, genre, year);
  flashMsg('');   // terminó: saca el "analizando"
  if (res.error) { await confirmModal('Generar playlists', '✗ ' + res.error); return; }
  let msg = '';
  if (res.ya_fecha) {
    msg += `⚠ Ojo: ya habías generado esto el ${res.ya_fecha} — se actualizó (se sobreescribieron los archivos).\n\n`;
  }
  msg += `${res.playlists} playlists creadas (${res.tracks} tracks) en:\n${res.folder}\n\n`;
  if (res.sin_tag) {
    msg += `⚠ ${res.sin_tag} tracks quedaron AFUERA (les falta género o año). ` +
           `Cuáles → mirá el archivo "${res.sin_tag_file}" en esa carpeta.\n\n`;
  } else {
    msg += 'Todos los tracks entraron (ninguno sin tag). ✅\n\n';
  }
  msg += `${res.playlists} playlists en ${res.generos} carpeta(s) de género ` +
    `(cada archivo nombrado por año, ej. 2013.nml).\n\n` +
    '🎧 En Traktor: creá una carpeta con el nombre del género → click derecho → ' +
    '"Import Playlist Directory" → apuntá a la subcarpeta de ese género. Te entran ' +
    'todas las playlists por año de una. 🌳';
  const abrir = await confirmModal('Playlists listas ✓', msg, '📂 Abrir carpeta');
  if (abrir) api().open_in_explorer(res.folder);
});

/* Pestañas del Historial: música ordenada / playlists generadas */
$('#htab-tracks').addEventListener('click', () => switchHistTab('tracks'));
$('#htab-playlists').addEventListener('click', () => switchHistTab('playlists'));

function switchHistTab(which) {
  const esTracks = which === 'tracks';
  $('#htab-tracks').classList.toggle('active', esTracks);
  $('#htab-playlists').classList.toggle('active', !esTracks);
  $('#hist-tracks').hidden = !esTracks;
  $('#hist-playlists').hidden = esTracks;
  if (!esTracks) renderPlaylistsTab();
}

async function renderPlaylistsTab() {
  const log = await api().get_playlists_log();
  const tb = $('#tbl-pl tbody');
  tb.innerHTML = '';
  (log || []).slice().reverse().forEach((e) => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      `<td>${escapeHtml(e.fecha || '')}</td>` +
      `<td>${escapeHtml(e.genre || 'Todos los géneros')}</td>` +
      `<td>${escapeHtml(e.year || 'Todos')}</td>` +
      `<td>${e.playlists || 0}</td>` +
      `<td>${e.tracks || 0}</td>` +
      `<td>${e.sin_tag ? '⚠ ' + e.sin_tag : '—'}</td>` +
      `<td class="muted">${escapeHtml(e.dest || '')}</td>`;
    if (e.dest) {
      tr.style.cursor = 'pointer';
      tr.title = 'Doble-click para abrir la carpeta';
      tr.addEventListener('dblclick', () => api().open_in_explorer(e.dest));
    }
    tb.appendChild(tr);
  });
  const hay = log && log.length;
  $('#pl-empty').style.display = hay ? 'none' : 'block';
  $('#pl-count').textContent = hay
    ? `${log.length} generación${log.length !== 1 ? 'es' : ''}`
    : 'Sin playlists generadas aún';
}

$('#btn-continue').addEventListener('click', async () => {
  if (state.items.some((i) => i.is_dup)) {   // guarda: el botón ya está gateado
    flashMsg('✗ Quitá los duplicados antes de continuar');
    return;
  }
  if (!$('#token').value.trim()) {
    flashMsg('✗ Necesitás un token de Discogs — usá el botón "Obtener token"');
    return;
  }
  await saveConfig();
  showView('buscar');
  enterBuscar(true);
});

$('#btn-remove-dups').addEventListener('click', () => {
  const n = state.items.filter((i) => i.is_dup).length;
  if (!n) return;
  state.items = state.items.filter((i) => !i.is_dup);
  renderLoadTable();
  flashMsg(`🗑 ${n} duplicado${n > 1 ? 's' : ''} quitado${n > 1 ? 's' : ''} de la lista`);
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
  const dup = it.is_dup
    ? `    ⚠ YA EN BIBLIOTECA${it.dup_fecha ? ` (${it.dup_fecha})` : ''}` : '';
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
    tr.addEventListener('click', () => selectResult(i, true));   // clic = manual, sobrescribe
    tr.addEventListener('dblclick', () => confirmCurrent());
    tbody.appendChild(tr);
  });
}

function selectResult(i, manual = false) {
  if (i < 0 || i >= results.length) return;
  selResult = i;
  document.querySelectorAll('#tbl-results tbody tr').forEach(
    (tr, j) => tr.classList.toggle('sel', j === i));
  const r = results[i];
  // Discogs aporta sello/año (y la carpeta SOLO si quedó vacía). Al AUTO-seleccionar
  // (primera búsqueda) se completan solo los campos VACÍOS, para NO pisar lo que ya
  // editaste/confirmaste. Al hacer clic en un resultado (manual) sí se sobrescribe,
  // porque lo elegiste vos. Artista/Título NO se tocan (el "título" es del álbum).
  if (!$('#conf-genre').value.trim()) setGenre(r.genre || '');
  if (manual || !$('#conf-label').value.trim()) $('#conf-label').value = r.label || '';
  if (manual || !$('#conf-year').value.trim()) $('#conf-year').value = r.year || '';
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
  const sugs = matches.slice(0, 3);          // hasta 3 candidatos, clickeables
  labelWarningActive = true;   // hay que decidir antes de poder confirmar
  hint.style.color = '#fc0b91';
  hint.textContent = sugs.length > 1
    ? '⚠ Ya existen carpetas parecidas: '
    : '⚠ Ya existe una carpeta parecida: ';

  sugs.forEach((sug) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = sug;
    b.title = 'Usar "' + sug + '"';
    b.style.cssText = HINT_BTN + 'border:1px solid #fc0b91; color:#fc0b91;';
    b.addEventListener('click', () => {
      $('#conf-label').value = sug;
      labelWarningActive = false;
      hint.style.display = 'none'; hint.textContent = '';
      updatePreview();
    });
    hint.appendChild(b);
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

  const base = $('#base-path').value.trim();
  const payload = ready.map((i) => ({
    type: i.type, path: i.path, name: i.name,
    artist: i.artist, title: i.title, album: i.album,
    genre: i.conf.genre, genre_specific: i.conf.genre_specific,
    label: i.conf.label, year: i.conf.year,
  }));

  // Pre-chequeo: destinos que YA existen en disco (esos NO se mueven, no se pisan).
  let yaExisten = [];
  try { yaExisten = await api().dests_existentes(payload, base); } catch (e) { yaExisten = []; }

  const dups = ready.filter((i) => i.is_dup).length;
  let msg = `¿Mover ${ready.length} ítem${ready.length > 1 ? 's' : ''} ahora?`;
  if (dups) msg += `\n\n⚠ ${dups} ya figura${dups > 1 ? 'n' : ''} en tu biblioteca.`;
  if (yaExisten.length) {
    const mb = (b) => (b / 1048576).toFixed(1) + ' MB';
    const lineas = yaExisten.slice(0, 6).map((d) => {
      if (d.size_nuevo != null && d.size_existente != null) {
        const cmp = compararTamano(d.size_nuevo, d.size_existente);
        let reco;
        if (cmp === 'igual') reco = 'prácticamente idénticos (mismo tamaño)';
        else if (cmp === 'a') reco = 'este es más grande → borrá el de destino y volvé a moverlo';
        else reco = 'el de destino es más grande → borrá este';
        return `   • ${d.name}\n       este ${mb(d.size_nuevo)} vs destino ${mb(d.size_existente)} → ${reco}`;
      }
      return `   • ${d.name}`;
    }).join('\n');
    const mas = yaExisten.length > 6 ? `\n   …y ${yaExisten.length - 6} más` : '';
    msg += `\n\n⚠ ${yaExisten.length} ya existe${yaExisten.length > 1 ? 'n' : ''} en el destino ` +
      `(no se ${yaExisten.length > 1 ? 'van' : 'va'} a mover, para no pisar). ` +
      `Recomendación por calidad (tamaño):\n${lineas}${mas}`;
  }
  msg += '\n\nVas a poder deshacerlo desde la pantalla de Resultado.';
  if (!(await confirmModal('Confirmar', msg))) return;

  showView('resultado');
  $('#move-log').textContent = 'Moviendo…';

  const res = await api().move_items(payload, base);

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

  if (res.playlists_updated && res.playlists_updated.length) {
    const detalle = res.playlists_updated
      .map((p) => `${p.name} (+${p.added})`).join(', ');
    flashMsg(`🎵 Playlists actualizadas: ${detalle}. Reimportá solo esas en Traktor.`, 600000);
  }
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

/* ── Vista Historial ─────────────────────────────────────── */
let history = [];
let ctxDestino = '';

async function loadHistory() {
  history = await api().get_history();
  // Backfill del género del tag (una sola vez) para filtrar/mostrar por tag.
  try {
    if (await api().history_needs_genre_backfill()) {
      flashMsg('⏳ Actualizando géneros del historial… (solo esta vez, puede tardar)', 600000);
      await api().backfill_history_genres();
      flashMsg('');
      history = await api().get_history();
    }
  } catch (e) { /* si falla, seguimos con lo que haya */ }
  populateGenreFilter();
  await updateRepairButton();
  renderHistory();
}

// Muestra el botón "Reparar rutas movidas" con la cantidad de entradas obsoletas.
async function updateRepairButton() {
  const btn = $('#btn-hist-repair');
  if (!btn) return;
  try {
    const n = await api().count_moved_history();
    btn.hidden = n === 0;
    btn.textContent = `🔧 Reparar rutas movidas (${n})`;
  } catch (e) { btn.hidden = true; }
}

$('#btn-hist-repair').addEventListener('click', async () => {
  const n = await api().count_moved_history();
  if (!n) { await confirmModal('Reparar rutas movidas', 'No hay rutas movidas. ✅'); return; }
  const ok = await confirmModal('Reparar rutas movidas',
    `${n} entradas tienen el archivo movido o renombrado. Voy a buscarlos en tu ` +
    `biblioteca y actualizar el historial (ruta + género real + sello/año). ` +
    'NO toco los archivos.', 'Reparar');
  if (!ok) return;
  flashMsg('⏳ Buscando archivos movidos… puede tardar (escanea la biblioteca).', 600000);
  const r = await api().repair_moved_history();
  flashMsg('');
  if (r.error) { await confirmModal('Reparar rutas movidas', '✗ ' + r.error); return; }
  await loadHistory();
  const noEnc = r.no_encontradas
    ? `\n\n⚠ ${r.no_encontradas} no se encontraron (quedaron marcadas "(archivo movido)"` +
      (r.txt_file ? ` y están en:\n${r.txt_file}).` : ').')
    : '';
  await confirmModal('Listo ✓', `🔧 ${r.reparadas} rutas reparadas.${noEnc}`);
});

function populateGenreFilter() {
  const sel = $('#hist-genre');
  const cur = sel.value;
  const genres = [...new Set(history
    .map((h) => h.genero_especifico || h.genero).filter(Boolean))].sort();
  sel.innerHTML = '<option value="">Todos los géneros</option>' +
    genres.map((g) => `<option>${escapeHtml(g)}</option>`).join('');
  sel.value = cur;   // preservar la selección si todavía existe
}

const HIST_PAGE_SIZE = 50;
let histPage = 1;

/* Filas que pasan el buscador y el filtro de género (más nuevas primero). */
function historyFiltered() {
  const flt = $('#hist-search').value.trim().toLowerCase();
  const gen = $('#hist-genre').value;
  return history.slice().reverse().filter((h) => {
    const g = h.genero_especifico || h.genero || '';
    if (gen && g !== gen) return false;
    if (!flt) return true;
    const blob = [h.artista, h.track, g, h.sello, h.destino]
      .join(' ').toLowerCase();
    return blob.includes(flt);
  });
}

function renderHistory() {
  const rows = historyFiltered();
  const total = history.length;
  const shown = rows.length;
  const pages = Math.max(1, Math.ceil(shown / HIST_PAGE_SIZE));
  histPage = Math.min(Math.max(1, histPage), pages);   // clamp
  const desde = (histPage - 1) * HIST_PAGE_SIZE;

  const tbody = $('#tbl-hist tbody');
  tbody.innerHTML = '';
  rows.slice(desde, desde + HIST_PAGE_SIZE).forEach((h) => {
    const tr = document.createElement('tr');
    [h.fecha, h.artista, h.track, (h.genero_especifico || h.genero),
     h.sello, h['año'], h.destino]
      .forEach((v) => {
        const td = document.createElement('td');
        td.textContent = v || '';
        td.title = v || '';        // ver texto completo al pasar el mouse
        tr.appendChild(td);
      });
    tr.addEventListener('dblclick', () => api().open_in_explorer(h.destino));
    tr.addEventListener('contextmenu', (e) => showCtxMenu(e, h.destino));
    tbody.appendChild(tr);
  });

  $('#hist-empty').style.display = history.length ? 'none' : 'block';
  const flt = $('#hist-search').value.trim();
  const gen = $('#hist-genre').value;
  $('#hist-count').textContent = total === 0 ? 'Sin registros aún'
    : ((flt || gen) ? `${shown} de ${total} registros`
                    : `${total} registro${total !== 1 ? 's' : ''}`);

  $('#hist-pager').style.display = pages > 1 ? '' : 'none';
  $('#hist-page-info').textContent = `Página ${histPage} de ${pages}`;
  $('#hist-prev').disabled = histPage <= 1;
  $('#hist-next').disabled = histPage >= pages;
}

function histGoTo(p) {
  histPage = p;
  renderHistory();
  const card = $('#tbl-hist').closest('.table-card');
  if (card) card.scrollTop = 0;      // cada página arranca arriba
}

$('#hist-prev').addEventListener('click', () => histGoTo(histPage - 1));
$('#hist-next').addEventListener('click', () => histGoTo(histPage + 1));

// Al filtrar/buscar, volver a la página 1.
$('#hist-search').addEventListener('input', () => { histPage = 1; renderHistory(); });
$('#hist-genre').addEventListener('change', () => { histPage = 1; renderHistory(); });

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

/* ── Guía / tour (coach marks) ───────────────────────────── */
const TOUR = [
  { view: 'cargar', sel: null, title: '¡Hola! Soy BelApp 🎧',
    text: 'Organizo tu música: busco metadata en Discogs, ordeno por Género/Sello/Año y armo playlists para Traktor. Te muestro las 4 pantallas en un minuto.' },
  { view: 'cargar', sel: 'nav', title: 'Las 4 pantallas',
    text: 'El flujo es: Cargar → Buscar & Confirmar → Resultado → Historial. Te movés entre ellas desde este menú.' },
  { view: 'cargar', sel: '#cfg-base', title: '1 · Cargar — tu carpeta',
    text: 'Con "Cambiar" elegís tu carpeta base de música: ahí se ordenan los tracks en Género/Sello/Año.' },
  { view: 'cargar', sel: '#cfg-token', title: 'Tu token de Discogs',
    text: 'Con "Obtener token" generás uno gratis y lo pegás acá. Se usa para buscar la metadata de cada track.' },
  { view: 'cargar', sel: '.load-actions', title: 'Cargar música',
    text: 'Sumá tracks sueltos, una carpeta de EP/Album, o escaneá una carpeta entera (saltea las carpetas de año ya ordenadas).' },
  { view: 'cargar', sel: '.tools-row', title: 'Mantenimiento',
    text: 'Normalizá los géneros de una carpeta (con revisión track por track) o generá las playlists .m3u8 para Traktor.' },
  { view: 'cargar', sel: '#btn-continue', title: 'Seguir el flujo',
    text: 'Con ítems cargados, "Continuar" te lleva a la siguiente pantalla.' },
  { view: 'buscar', sel: '#nav-buscar', title: '2 · Buscar & Confirmar',
    text: 'Acá cada track se busca solo en Discogs. Elegís el resultado correcto, completás Género/Sello/Año y confirmás. Cuando estén todos → ▶ Mover.' },
  { view: 'resultado', sel: '#nav-resultado', title: '3 · Resultado',
    text: 'Acá ves el log de todo lo que se movió. Podés "Deshacer" el último movimiento o abrir la carpeta destino.' },
  { view: 'historial', sel: '#nav-historial', title: '4 · Historial',
    text: 'Acá queda el registro de todo lo ordenado: buscás, filtrás por género, navegás con paginación y exportás a Excel. Doble clic en una fila abre la carpeta.' },
  { view: 'cargar', sel: null, title: '¡Listo! 🎉',
    text: 'Eso es todo. Para la referencia completa en texto (o para ver esto de nuevo) tocá "❓ Guía", arriba a la derecha.' },
];
let tourIdx = 0;

function tourShow(i) {
  tourIdx = Math.max(0, Math.min(i, TOUR.length - 1));
  const step = TOUR[tourIdx];
  showView(step.view || 'cargar');
  if (step.view === 'historial') { try { loadHistory(); } catch (e) {} }
  const spot = $('#tour-spot');
  const bubble = $('#tour-bubble');
  $('#tour-overlay').classList.add('show');
  $('#tour-title').textContent = step.title;
  $('#tour-text').textContent = step.text;
  $('#tour-step').textContent = `${tourIdx + 1} / ${TOUR.length}`;
  $('#tour-prev').style.visibility = tourIdx === 0 ? 'hidden' : 'visible';
  $('#tour-next').textContent = tourIdx === TOUR.length - 1 ? 'Listo ✓' : 'Siguiente →';

  const el = step.sel ? document.querySelector(step.sel) : null;
  if (el) {
    const r = el.getBoundingClientRect();
    const pad = 8;
    spot.style.display = 'block';
    spot.style.left = (r.left - pad) + 'px';
    spot.style.top = (r.top - pad) + 'px';
    spot.style.width = (r.width + pad * 2) + 'px';
    spot.style.height = (r.height + pad * 2) + 'px';
    const bh = bubble.offsetHeight || 170;
    const bx = Math.max(16, Math.min(r.left, window.innerWidth - 346));
    let by;
    if (r.bottom + 12 + bh < window.innerHeight) by = r.bottom + 12;
    else if (r.top - 12 - bh > 8) by = r.top - 12 - bh;
    else by = Math.max(16, (window.innerHeight - bh) / 2);
    bubble.style.left = bx + 'px';
    bubble.style.top = by + 'px';
  } else {
    spot.style.display = 'none';
    bubble.style.left = (window.innerWidth / 2 - 150) + 'px';
    bubble.style.top = (window.innerHeight / 2 - 100) + 'px';
  }
}

function tourEnd() {
  $('#tour-overlay').classList.remove('show');
  try { api().marcar_tour_visto(); } catch (e) { /* nada */ }
}

$('#tour-next').addEventListener('click', () => {
  if (tourIdx === TOUR.length - 1) tourEnd(); else tourShow(tourIdx + 1);
});
$('#tour-prev').addEventListener('click', () => tourShow(tourIdx - 1));
$('#tour-skip').addEventListener('click', tourEnd);
$('#btn-guia').addEventListener('click', () => $('#guide-overlay').classList.add('show'));
$('#guide-close').addEventListener('click', () => $('#guide-overlay').classList.remove('show'));
$('#guide-tour').addEventListener('click', () => {
  $('#guide-overlay').classList.remove('show');
  showView('cargar');
  tourShow(0);
});
window.addEventListener('resize', () => {
  if ($('#tour-overlay').classList.contains('show')) tourShow(tourIdx);
});

/* ── Handshake con Python ────────────────────────────────── */
window.addEventListener('pywebviewready', async () => {
  try {
    const cfg = await api().get_config();
    $('#base-path').value = cfg.base_path;
    $('#token').value = cfg.discogs_token;
    GENRES = await api().get_genres();
    GENRES_SPEC = (await api().get_genres_specific())
      .sort((a, b) => a.localeCompare(b, 'es'));   // alfabético en los desplegables
    SPEC2BROAD = await api().get_specific_to_broad();
    setGenre('');
    setGenreSpecific('');
    $('#status').textContent =
      'Conectado · Carpeta base: ' + cfg.base_path +
      (cfg.discogs_token ? ' · Token ✓' : ' · Sin token');
    // Estado del auto-append de playlists al ordenar.
    try {
      const c = $('#chk-pl-auto');
      if (c) {
        c.checked = await api().get_playlists_auto();
        c.addEventListener('change', () => api().set_playlists_auto(c.checked));
      }
    } catch (e) { /* si falla, queda el default del HTML */ }
    // Guía de bienvenida: solo la primera vez.
    if (!(await api().tour_visto())) {
      showView('cargar');
      setTimeout(() => tourShow(0), 600);
    }
  } catch (err) {
    $('#status').textContent = 'Error de puente: ' + err;
  }
});

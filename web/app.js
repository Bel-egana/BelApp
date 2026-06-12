/* BelApp — frontend. Estado de UI en JS; operaciones en Python vía pywebview.api. */
'use strict';

const $ = (sel) => document.querySelector(sel);

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

/* ── Handshake con Python ────────────────────────────────── */
window.addEventListener('pywebviewready', async () => {
  try {
    const cfg = await pywebview.api.get_config();
    $('#status').textContent =
      'Conectado · Carpeta base: ' + cfg.base_path +
      (cfg.discogs_token ? ' · Token ✓' : ' · Sin token');
  } catch (err) {
    $('#status').textContent = 'Error de puente: ' + err;
  }
});

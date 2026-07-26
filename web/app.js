'use strict';

/* ===================== estado ===================== */
const S = {
  sounds: [],
  cats: [],
  sources: [],
  root: '',
  engine: null,
  view: 'all',          // 'all' | 'fav' | <id de categoria>
  q: '',
  dur: '',
  lic: '',
  sort: 'rel',
  ctx: null,            // contexto activo: { type:'similar', id, label }
  filtered: [],
  rendered: 0,
  favs: new Set(JSON.parse(localStorage.getItem('sfx.favs') || '[]')),
  current: null,
  loop: false,
};

const CHUNK = 80;                 // filas por tanda al hacer scroll
const WAVE_MAX_BYTES = 10 << 20;  // por encima de esto no se dibuja la onda:
                                  // decodificar el WAV entero seria lentisimo

const $ = (s) => document.querySelector(s);
const audio = new Audio();
audio.preload = 'metadata';
audio.volume = parseFloat(localStorage.getItem('sfx.vol') ?? '0.85');

/* ===================== utilidades ===================== */
const fmtTime = (s) => {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
};

const fmtDur = (s) => (s < 10 ? `${s.toFixed(1)}s` : fmtTime(s));

const fmtSize = (b) =>
  b >= 1 << 20 ? `${(b / (1 << 20)).toFixed(1)} MB`
               : `${Math.max(1, Math.round(b / 1024))} KB`;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** Rellena todo elemento con data-icon con su SVG. */
function hydrateIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach((el) => {
    if (el.dataset.iconDone) return;
    el.innerHTML = icon(el.dataset.icon) + el.innerHTML;
    el.dataset.iconDone = '1';
  });
}

let toastTimer;
function toast(html, ms = 3600) {
  const t = $('#toast');
  t.innerHTML = html;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}

/* ===================== carga ===================== */
async function boot() {
  hydrateIcons();
  $('#brandMark').innerHTML = icon('waveform');

  let data;
  try {
    const r = await fetch('/api/index');
    if (!r.ok) throw new Error((await r.json()).error || r.statusText);
    data = await r.json();
  } catch (e) {
    $('#list').innerHTML =
      `<div class="empty">${icon('warn', 'empty-ico')}
       <p>No se pudo cargar el índice.</p>
       <p class="muted">${esc(e.message || e)}</p></div>`;
    return;
  }

  S.cats = data.categories.filter((c) => c.count > 0);
  S.sources = (data.sources || []).filter((s) => s.count > 0);
  S.sounds = data.sounds;
  S.root = data.root || '~/SFX-Library/library';
  S.sounds.forEach((s, i) => { s._i = i; });

  const t0 = performance.now();
  S.engine = new SearchEngine(S.sounds);
  const ms = Math.round(performance.now() - t0);

  $('#brandStats').textContent =
    `${data.total.toLocaleString('es')} sonidos · ` +
    `${(data.bytes / 1024 ** 3).toFixed(1)} GB`;
  $('#countAll').textContent = data.total.toLocaleString('es');
  console.log(`[sfx] índice de búsqueda: ${S.engine.vocab.length} términos ` +
              `sobre ${S.sounds.length} sonidos en ${ms} ms`);

  buildNav();
  buildLicenseFilter();
  bindUI();
  apply();
}

function buildNav() {
  $('#navCats').innerHTML = S.cats.map((c) => `
    <button class="nav-item" data-view="${c.id}">
      <span class="nav-ico">${icon(c.icon || 'layers')}</span>
      <span class="nav-label">${esc(c.label)}</span>
      <span class="nav-count">${c.count.toLocaleString('es')}</span>
    </button>`).join('');

  $('#navSources').innerHTML = S.sources.map((s) => `
    <button class="nav-item" data-view="src:${esc(s.id)}">
      <span class="nav-ico">${icon('disc')}</span>
      <span class="nav-label" title="${esc(s.label)}">${esc(s.label)}</span>
      <span class="nav-count">${s.count.toLocaleString('es')}</span>
    </button>`).join('');
}

function buildLicenseFilter() {
  const set = [...new Set(S.sounds.map((s) => s.lic))].sort();
  $('#fLic').insertAdjacentHTML('beforeend',
    set.map((l) => `<option value="${esc(l)}">${esc(l)}</option>`).join(''));
}

/* ===================== filtrado ===================== */
/** Conjunto de índices que pasan los filtros que no son la consulta. */
function poolIndices() {
  const [dMin, dMax] = S.dur ? S.dur.split('-').map(Number) : [null, null];
  const pool = new Set();
  const srcView = S.view.startsWith('src:') ? S.view.slice(4) : null;
  for (const s of S.sounds) {
    if (S.view === 'fav') { if (!S.favs.has(s.id)) continue; }
    else if (srcView) { if (s.src !== srcView) continue; }
    else if (S.view !== 'all' && s.cat !== S.view) continue;
    if (S.lic && s.lic !== S.lic) continue;
    if (dMin !== null && (s.dur < dMin || s.dur >= dMax)) continue;
    pool.add(s._i);
  }
  return pool;
}

function apply() {
  const pool = poolIndices();
  let ordered = null;      // orden por relevancia, si lo hay

  if (S.ctx && S.ctx.type === 'similar') {
    // 150 y no más: por debajo de ese rango el coseno ya devuelve parecidos
    // muy flojos y ensucian el resultado.
    ordered = S.engine.similar(S.ctx.i, 150, pool);
  } else if (S.q) {
    ordered = S.engine.search(S.q, pool);
  }

  if (ordered) {
    S.filtered = ordered.map((i) => S.sounds[i]);
  } else {
    S.filtered = S.sounds.filter((s) => pool.has(s._i));
  }

  // El orden por relevancia solo tiene sentido si hubo consulta; con la lista
  // completa se cae a nombre para no dar un orden aparentemente aleatorio.
  const sort = (S.sort === 'rel' && !ordered) ? 'name' : S.sort;
  const by = {
    name: (a, b) => a.name.localeCompare(b.name, 'es'),
    dur:  (a, b) => a.dur - b.dur,
    size: (a, b) => b.size - a.size,
  }[sort];
  if (by) S.filtered.sort(by);
  else if (sort === 'random') {
    for (let i = S.filtered.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [S.filtered[i], S.filtered[j]] = [S.filtered[j], S.filtered[i]];
    }
  }

  const cat = S.cats.find((c) => c.id === S.view);
  $('#viewTitle').textContent =
    S.view === 'all' ? 'Todos los sonidos'
    : S.view === 'fav' ? 'Favoritos'
    : S.view.startsWith('src:') ? S.view.slice(4)
    : (cat ? cat.label : '');
  $('#resultCount').textContent =
    `${S.filtered.length.toLocaleString('es')} resultado${S.filtered.length === 1 ? '' : 's'}`;

  const ctxBtn = $('#clearCtx');
  ctxBtn.hidden = !S.ctx;
  if (S.ctx) $('#clearCtxLabel').textContent = S.ctx.label;

  $('#list').querySelectorAll('.row').forEach((r) => r.remove());
  $('#list').scrollTop = 0;
  S.rendered = 0;
  renderMore();

  $('#empty').hidden = S.filtered.length > 0;
  if (!S.filtered.length) {
    $('#emptyMsg').textContent = S.q
      ? `Nada para «${S.q}». Prueba con otra palabra, en español o inglés.`
      : 'No hay sonidos que cumplan estos filtros.';
  }
}

/* ===================== render ===================== */
function rowHTML(s) {
  const fav = S.favs.has(s.id);
  const playing = S.current && S.current.id === s.id;
  const tags = s.tags.slice(0, 3)
    .map((t) => `<span class="tag">${esc(t)}</span>`).join('');
  const ch = s.ch === 1 ? 'mono' : s.ch === 2 ? 'estéreo' : `${s.ch}ch`;
  const khz = s.sr ? `${(s.sr / 1000).toFixed(s.sr % 1000 ? 1 : 0)} kHz` : '';
  const ext = s.file.split('.').pop().toUpperCase();

  return `<div class="row${playing ? ' is-playing' : ''}" data-id="${s.id}">
    <span class="r-play">${icon(playing && !audio.paused ? 'pause' : 'play')}</span>
    <span class="r-main">
      <span class="r-name">${esc(s.name)}</span>
      <span class="r-sub">${esc(s.pack || s.src)}</span>
    </span>
    <span class="r-tags col-tags">${tags}</span>
    <span class="r-dur">${fmtDur(s.dur)}</span>
    <span class="r-meta col-meta">${ext} · ${khz} · ${ch}<br>${fmtSize(s.size)}</span>
    <span class="r-act">
      <button class="icon-btn js-similar" title="Buscar parecidos">${icon('similar')}</button>
      <button class="icon-btn js-fav${fav ? ' is-on' : ''}"
              title="Favorito">${icon('star')}</button>
      <button class="icon-btn js-copy" title="Copiar ruta">${icon('copy')}</button>
      <a class="icon-btn js-dl" title="Descargar"
         href="/audio/${encodeURI(s.file)}" download>${icon('download')}</a>
    </span>
  </div>`;
}

function renderMore() {
  const slice = S.filtered.slice(S.rendered, S.rendered + CHUNK);
  if (!slice.length) return;
  // beforebegin del sentinel, para no dejarlo nunca por encima de las filas.
  $('#sentinel').insertAdjacentHTML('beforebegin', slice.map(rowHTML).join(''));
  S.rendered += slice.length;
}

/* ===================== favoritos ===================== */
function saveFavs() {
  localStorage.setItem('sfx.favs', JSON.stringify([...S.favs]));
  $('#countFav').textContent = S.favs.size;
  $('#btnExport').disabled = S.favs.size === 0;
}

function toggleFav(id) {
  S.favs.has(id) ? S.favs.delete(id) : S.favs.add(id);
  saveFavs();

  const on = S.favs.has(id);
  const btn = document.querySelector(`.row[data-id="${id}"] .js-fav`);
  if (btn) btn.classList.toggle('is-on', on);
  if (S.current && S.current.id === id) $('#plFav').classList.toggle('is-on', on);
  if (S.view === 'fav' && !on) apply();
}

/* ===================== reproductor ===================== */
function play(s) {
  S.current = s;
  audio.src = '/audio/' + encodeURI(s.file);
  audio.loop = S.loop;
  audio.play().catch(() => {});

  $('#player').hidden = false;
  $('#plName').textContent = s.name;
  const ch = s.ch === 1 ? 'mono' : s.ch === 2 ? 'estéreo' : `${s.ch}ch`;
  $('#plMeta').textContent =
    `${s.src} · ${s.lic} · ${s.sr ? (s.sr / 1000).toFixed(0) + ' kHz · ' : ''}${ch} · ${fmtSize(s.size)}`;
  $('#plDur').textContent = fmtDur(s.dur);
  $('#plDl').href = '/audio/' + encodeURI(s.file);
  $('#plDl').setAttribute('download', s.file.split('/').pop());
  $('#plFav').classList.toggle('is-on', S.favs.has(s.id));

  document.querySelectorAll('.row.is-playing').forEach((r) => {
    r.classList.remove('is-playing');
    const p = r.querySelector('.r-play');
    if (p) p.innerHTML = icon('play');
  });
  const row = document.querySelector(`.row[data-id="${s.id}"]`);
  if (row) {
    row.classList.add('is-playing');
    row.querySelector('.r-play').innerHTML = icon('pause');
  }

  drawWave(s);
}

function step(delta) {
  if (!S.current) return;
  const i = S.filtered.findIndex((x) => x.id === S.current.id);
  const next = S.filtered[i + delta];
  if (!next) return;
  // Puede no estar renderizado todavia si esta mas alla del scroll actual.
  while (S.rendered < i + delta + 1 && S.rendered < S.filtered.length) renderMore();
  play(next);
  document.querySelector(`.row[data-id="${next.id}"]`)
    ?.scrollIntoView({ block: 'nearest' });
}

function showSimilar(s) {
  S.ctx = { type: 'similar', i: s._i, label: `Parecidos a «${s.name.slice(0, 34)}»` };
  S.q = '';
  $('#search').value = '';
  S.view = 'all';
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('is-active'));
  document.querySelector('.nav-item[data-view="all"]').classList.add('is-active');
  apply();
}

/* ---------- forma de onda ---------- */
let waveToken = 0;
let audioCtx;
const peaksCache = new Map();

async function drawWave(s) {
  const canvas = $('#wave');
  const token = ++waveToken;
  const cached = peaksCache.get(s.id);
  if (cached) return paint(canvas, cached);

  paint(canvas, null);                       // limpia mientras carga
  if (s.size > WAVE_MAX_BYTES) return;       // demasiado grande: solo barra

  try {
    const buf = await (await fetch('/audio/' + encodeURI(s.file))).arrayBuffer();
    if (token !== waveToken) return;         // el usuario ya cambió de sonido
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const decoded = await audioCtx.decodeAudioData(buf);
    if (token !== waveToken) return;

    const N = 420;
    const ch = decoded.getChannelData(0);
    const per = Math.floor(ch.length / N) || 1;
    const peaks = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      let mx = 0;
      const start = i * per;
      for (let j = 0; j < per; j += 2) {     // submuestreo: basta para el pico
        const v = Math.abs(ch[start + j] || 0);
        if (v > mx) mx = v;
      }
      peaks[i] = mx;
    }
    const norm = Math.max(...peaks) || 1;
    for (let i = 0; i < N; i++) peaks[i] /= norm;

    peaksCache.set(s.id, peaks);
    if (peaksCache.size > 60) peaksCache.delete(peaksCache.keys().next().value);
    paint(canvas, peaks);
  } catch { /* formato no decodificable: se queda la barra lisa */ }
}

function paint(canvas, peaks) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const g = canvas.getContext('2d');
  g.scale(dpr, dpr);
  g.clearRect(0, 0, w, h);

  if (!peaks) {
    g.fillStyle = '#232a35';
    g.fillRect(0, h / 2 - 1, w, 2);
    return;
  }
  const n = peaks.length;
  const bw = w / n;
  g.fillStyle = '#5d6878';
  for (let i = 0; i < n; i++) {
    const bh = Math.max(1.5, peaks[i] * (h - 4));
    g.fillRect(i * bw, (h - bh) / 2, Math.max(1, bw - 0.6), bh);
  }
}

/* ===================== eventos ===================== */
function copyPath(s) {
  const abs = `${S.root}/${s.file}`;
  navigator.clipboard.writeText(abs)
    .then(() => toast(`Ruta copiada:<br><code>${esc(abs)}</code>`))
    .catch(() => toast('No se pudo copiar al portapapeles'));
}

function bindUI() {
  // --- navegacion lateral ---
  $('#nav').addEventListener('click', (e) => {
    const b = e.target.closest('.nav-item');
    if (!b) return;
    document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('is-active'));
    b.classList.add('is-active');
    S.view = b.dataset.view;
    S.ctx = null;
    apply();
  });

  // --- busqueda con debounce ---
  let t;
  $('#search').addEventListener('input', (e) => {
    clearTimeout(t);
    t = setTimeout(() => {
      S.q = e.target.value.trim();
      if (S.q) S.ctx = null;
      apply();
    }, 130);
  });

  $('#clearCtx').addEventListener('click', () => { S.ctx = null; apply(); });
  $('#fDur').addEventListener('change', (e) => { S.dur = e.target.value; apply(); });
  $('#fLic').addEventListener('change', (e) => { S.lic = e.target.value; apply(); });
  $('#fSort').addEventListener('change', (e) => { S.sort = e.target.value; apply(); });

  // --- clicks en la lista ---
  $('#list').addEventListener('click', (e) => {
    const row = e.target.closest('.row');
    if (!row) return;
    const s = S.sounds.find((x) => x.id === row.dataset.id);
    if (!s) return;

    if (e.target.closest('.js-fav'))     { e.stopPropagation(); return toggleFav(s.id); }
    if (e.target.closest('.js-similar')) { e.stopPropagation(); return showSimilar(s); }
    if (e.target.closest('.js-dl'))      { e.stopPropagation(); return; }
    if (e.target.closest('.js-copy'))    { e.stopPropagation(); return copyPath(s); }

    if (S.current && S.current.id === s.id) {
      audio.paused ? audio.play() : audio.pause();
    } else play(s);
  });

  // --- scroll infinito ---
  new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) renderMore();
  }, { root: $('#list'), rootMargin: '400px' }).observe($('#sentinel'));

  // --- controles del reproductor ---
  $('#plPlay').addEventListener('click', () =>
    audio.paused ? audio.play() : audio.pause());
  $('#plPrev').addEventListener('click', () => step(-1));
  $('#plNext').addEventListener('click', () => step(1));
  $('#plFav').addEventListener('click', () => S.current && toggleFav(S.current.id));
  $('#plSimilar').addEventListener('click', () => S.current && showSimilar(S.current));
  $('#plCopy').addEventListener('click', () => S.current && copyPath(S.current));
  $('#plLoop').addEventListener('click', (e) => {
    S.loop = !S.loop;
    audio.loop = S.loop;
    e.currentTarget.classList.toggle('is-on', S.loop);
  });

  $('#plVol').value = audio.volume;
  $('#plVol').addEventListener('input', (e) => {
    audio.volume = parseFloat(e.target.value);
    localStorage.setItem('sfx.vol', audio.volume);
  });

  $('#waveWrap').addEventListener('click', (e) => {
    if (!audio.duration) return;
    const r = e.currentTarget.getBoundingClientRect();
    audio.currentTime = ((e.clientX - r.left) / r.width) * audio.duration;
  });

  audio.addEventListener('timeupdate', () => {
    const p = audio.duration ? audio.currentTime / audio.duration : 0;
    $('#waveProg').style.inset = `0 ${(1 - p) * 100}% 0 0`;
    $('#plCur').textContent = fmtTime(audio.currentTime);
  });
  audio.addEventListener('loadedmetadata', () => {
    $('#plDur').textContent = fmtTime(audio.duration);
  });
  audio.addEventListener('play', () => {
    $('#plPlay').innerHTML = icon('pause');
    const r = document.querySelector('.row.is-playing .r-play');
    if (r) r.innerHTML = icon('pause');
  });
  audio.addEventListener('pause', () => {
    $('#plPlay').innerHTML = icon('play');
    const r = document.querySelector('.row.is-playing .r-play');
    if (r) r.innerHTML = icon('play');
  });
  audio.addEventListener('ended', () => { if (!S.loop) step(1); });

  // --- exportar favoritos e importar librerías ---
  $('#btnExport').addEventListener('click', exportFavs);
  $('#btnImport').addEventListener('click', openImport);
  $('#importClose').addEventListener('click', closeImport);
  $('#impCancel').addEventListener('click', closeImport);
  $('#impGo').addEventListener('click', startImport);
  $('#impDone').addEventListener('click', () => location.reload());
  $('#importModal').addEventListener('click', (e) => {
    if (e.target.id === 'importModal') closeImport();
  });

  // --- atajos de teclado ---
  document.addEventListener('keydown', (e) => {
    const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName);
    if (e.key === '/' && !typing) { e.preventDefault(); $('#search').focus(); return; }
    if (e.key === 'Escape' && typing) { e.target.blur(); return; }
    if (typing) return;
    if (e.code === 'Space') {
      e.preventDefault();
      if (S.current) audio.paused ? audio.play() : audio.pause();
    } else if (e.key === 'ArrowDown') { e.preventDefault(); step(1); }
    else if (e.key === 'ArrowUp')     { e.preventDefault(); step(-1); }
    else if (e.key.toLowerCase() === 'f' && S.current) toggleFav(S.current.id);
  });

  saveFavs();
}

async function exportFavs() {
  const files = S.sounds.filter((s) => S.favs.has(s.id)).map((s) => s.file);
  if (!files.length) return;
  const name = prompt('Nombre de la carpeta de exportación:',
    'favoritos-' + new Date().toISOString().slice(0, 10));
  if (name === null) return;

  const btn = $('#btnExport');
  btn.disabled = true;
  btn.textContent = 'Exportando…';
  try {
    const r = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files, name }),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    toast(`${d.ok} sonidos exportados a:<br><code>${esc(d.path)}</code><br>
           Arrastra esa carpeta al Media Pool de Resolve.`, 9000);
    fetch('/api/reveal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: d.path }),
    }).catch(() => {});
  } catch (e) {
    toast('Error al exportar: ' + esc(e.message || e));
  } finally {
    btn.textContent = 'Exportar favoritos';
    btn.disabled = S.favs.size === 0;
  }
}

/* ===================== importar librería ===================== */
function openImport() {
  $('#importModal').hidden = false;
  $('#importForm').hidden = false;
  $('#importProgress').hidden = true;
  $('#impLog').textContent = '';
  $('#impDone').disabled = true;
  $('#impDone').textContent = 'Trabajando…';
  $('#impPath').focus();
}

function closeImport() {
  $('#importModal').hidden = true;
}

async function startImport() {
  const payload = {
    path: $('#impPath').value.trim(),
    vendor: $('#impVendor').value.trim(),
    license: $('#impLicense').value.trim(),
    url: $('#impUrl').value.trim(),
  };
  if (!payload.path || !payload.vendor) {
    return toast('Hacen falta la ruta y el proveedor');
  }

  const r = await fetch('/api/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const d = await r.json();
  if (d.error) return toast('No se pudo importar: ' + esc(d.error), 6000);

  $('#importForm').hidden = true;
  $('#importProgress').hidden = false;
  pollJob();
}

async function pollJob() {
  try {
    const j = await (await fetch('/api/job')).json();
    $('#impLog').textContent = j.log.join('\n');
    $('#impLog').scrollTop = $('#impLog').scrollHeight;

    if (!j.done) return setTimeout(pollJob, 700);

    const btn = $('#impDone');
    btn.disabled = false;
    if (j.error) {
      btn.textContent = 'Cerrar';
      btn.onclick = closeImport;      // no recargar: la biblioteca no cambió
    } else {
      btn.textContent = `Recargar (${j.added} sonidos añadidos)`;
    }
  } catch {
    setTimeout(pollJob, 1200);
  }
}

boot();

'use strict';

/* Set de iconos inline. Todos comparten rejilla 24x24, trazo de 1.75 sin
   relleno y remates redondeados, para que se lean como una sola familia.
   Se heredan color y tamaño del contexto (currentColor / em). */

const ICON_PATHS = {
  /* --- categorías --- */
  target:   '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
  car:      '<path d="M4.5 15.5v2.2a.8.8 0 0 1-.8.8H3a.8.8 0 0 1-.8-.8V12l2-4.7A2 2 0 0 1 6 6h9a2 2 0 0 1 1.85 1.3L18.8 12v5.7a.8.8 0 0 1-.8.8h-.7a.8.8 0 0 1-.8-.8v-2.2"/><path d="M2.2 12h16.6"/><circle cx="6.2" cy="15.4" r="1.2"/><circle cx="14.8" cy="15.4" r="1.2"/><path d="M19.5 9.5h2.3M19.5 12.5h2.3"/>',
  droplet:  '<path d="M12 3.2c3.3 4 5.5 6.7 5.5 9.4a5.5 5.5 0 0 1-11 0c0-2.7 2.2-5.4 5.5-9.4Z"/><path d="M9.4 13.6a2.7 2.7 0 0 0 2.2 2.9"/>',
  paw:      '<ellipse cx="6.6" cy="10.4" rx="1.9" ry="2.4"/><ellipse cx="17.4" cy="10.4" rx="1.9" ry="2.4"/><ellipse cx="10" cy="6.2" rx="1.8" ry="2.3"/><ellipse cx="14.6" cy="6.2" rx="1.8" ry="2.3"/><path d="M12 13.4c2.5 0 4.4 1.7 4.4 3.6 0 1.7-1.4 2.8-3 2.8-.9 0-1.3-.4-2.5-.4-1.1 0-1.6.4-2.4.4-1.6 0-3-1.1-3-2.8 0-1.9 2-3.6 4.5-3.6Z"/>',
  sparkles: '<path d="M12 3.2 13.6 8 18.4 9.6 13.6 11.2 12 16l-1.6-4.8L5.6 9.6 10.4 8 12 3.2Z"/><path d="M18.2 15.2l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z"/><path d="M5.6 14.4l.5 1.4 1.4.5-1.4.5-.5 1.4-.5-1.4L3.7 16.3l1.4-.5.5-1.4Z"/>',
  film:     '<rect x="3" y="4.6" width="18" height="14.8" rx="2"/><path d="M7.6 4.6v14.8M16.4 4.6v14.8M3 12h18M3 8.3h4.6M3 15.7h4.6M16.4 8.3H21M16.4 15.7H21"/>',
  wind:     '<path d="M3 8.4h9.4a2.8 2.8 0 1 0-2.8-2.8"/><path d="M3 12h13.4a2.6 2.6 0 1 1-2.6 2.6"/><path d="M3 15.7h6.6a2.4 2.4 0 1 1-2.4 2.4"/>',
  impact:   '<path d="M12 2.6l2.1 5.1 5.3-1.7-3.2 4.6 4.4 3.3-5.5.6 1 5.4-4.1-3.7-4.1 3.7 1-5.4-5.5-.6 4.4-3.3-3.2-4.6 5.3 1.7L12 2.6Z"/>',
  cursor:   '<path d="M5.4 3.6l4.9 15.1 2.4-5.6 5.9-2.3L5.4 3.6Z"/><path d="M13.6 13.6l5 5"/>',
  mic:      '<rect x="9.2" y="2.8" width="5.6" height="11" rx="2.8"/><path d="M5.8 11.2a6.2 6.2 0 0 0 12.4 0"/><path d="M12 17.4v3.8M8.6 21.2h6.8"/>',
  tree:     '<path d="M12 2.8 6.6 10h3L5.4 16.2h13.2L14.4 10h3L12 2.8Z"/><path d="M12 16.2v5"/>',
  box:      '<path d="M20.6 8.2v7.6a1.6 1.6 0 0 1-.85 1.42l-6.9 3.6a1.7 1.7 0 0 1-1.7 0l-6.9-3.6A1.6 1.6 0 0 1 3.4 15.8V8.2a1.6 1.6 0 0 1 .85-1.42l6.9-3.6a1.7 1.7 0 0 1 1.7 0l6.9 3.6A1.6 1.6 0 0 1 20.6 8.2Z"/><path d="M3.6 7.4 12 11.9l8.4-4.5M12 20.6V11.9"/>',
  layers:   '<path d="M12 2.9 2.9 7.5 12 12.1l9.1-4.6L12 2.9Z"/><path d="M2.9 12.4 12 17l9.1-4.6M2.9 16.9 12 21.5l9.1-4.6"/>',

  /* --- navegación --- */
  waveform: '<path d="M3 12h2M7.4 8.2v7.6M11.7 4.8v14.4M16 8.2v7.6M20.4 10.4v3.2"/>',
  disc:     '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.6"/><path d="M12 3v3.6M12 17.4V21"/>',
  star:     '<path d="M12 3.4l2.6 5.5 5.9.8-4.3 4.2 1.05 6-5.25-2.85L6.75 19.9l1.05-6L3.5 9.7l5.9-.8L12 3.4Z"/>',

  /* --- reproductor --- */
  play:     '<path d="M7.6 4.8v14.4l11.6-7.2L7.6 4.8Z"/>',
  pause:    '<path d="M8.6 4.9v14.2M15.4 4.9v14.2"/>',
  prev:     '<path d="M18 5.2v13.6L8.4 12 18 5.2Z"/><path d="M5.4 5.2v13.6"/>',
  next:     '<path d="M6 5.2v13.6L15.6 12 6 5.2Z"/><path d="M18.6 5.2v13.6"/>',
  loop:     '<path d="M3.6 10.2A4.2 4.2 0 0 1 7.8 6h12.6"/><path d="M17.4 3l3 3-3 3"/><path d="M20.4 13.8A4.2 4.2 0 0 1 16.2 18H3.6"/><path d="M6.6 21l-3-3 3-3"/>',
  copy:     '<rect x="8.6" y="8.6" width="11.4" height="11.4" rx="2"/><path d="M15.4 5.6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.4a2 2 0 0 0 2 2"/>',
  download: '<path d="M12 3.6v11.2"/><path d="M7.8 10.6 12 14.8l4.2-4.2"/><path d="M4 17.2v1.6a1.6 1.6 0 0 0 1.6 1.6h12.8a1.6 1.6 0 0 0 1.6-1.6v-1.6"/>',
  search:   '<circle cx="10.8" cy="10.8" r="6.6"/><path d="M15.6 15.6 20.4 20.4"/>',
  volume:   '<path d="M4 9.4h3.2L11.6 5.6v12.8L7.2 14.6H4a.8.8 0 0 1-.8-.8v-3.6a.8.8 0 0 1 .8-.8Z"/><path d="M15.2 9.4a3.6 3.6 0 0 1 0 5.2"/><path d="M17.8 6.8a7.2 7.2 0 0 1 0 10.4"/>',
  similar:  '<circle cx="7.2" cy="7.2" r="3.4"/><circle cx="16.8" cy="16.8" r="3.4"/><path d="M9.9 9.6l4.2 4.2"/><path d="M16.8 4.2v6M13.8 7.2h6"/>',
  close:    '<path d="M6 6l12 12M18 6 6 18"/>',
  plus:     '<path d="M12 5.2v13.6M5.2 12h13.6"/>',
  empty:    '<circle cx="10.8" cy="10.8" r="6.6"/><path d="M15.6 15.6 20.4 20.4"/><path d="M8.4 10.8h4.8"/>',
  warn:     '<path d="M12 3.6 21.4 19.8H2.6L12 3.6Z"/><path d="M12 9.6v4.4M12 16.9v.1"/>',
};

/** Devuelve el SVG de un icono. `cls` se añade a la clase del elemento. */
function icon(name, cls = '') {
  const d = ICON_PATHS[name];
  if (!d) return '';
  return `<svg class="ico ${cls}" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.75" stroke-linecap="round"
    stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
}

window.icon = icon;
window.ICON_PATHS = ICON_PATHS;

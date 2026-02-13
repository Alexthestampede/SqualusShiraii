import { renderNav, updateNavActive } from './components/nav.js';
import { initPlayer } from './components/player.js';
import { renderLibrary } from './pages/library.js';
import { renderCreateSimple } from './pages/create-simple.js';
import { renderCreateCustom } from './pages/create-custom.js';
import { renderSongDetail } from './pages/song-detail.js';
import { renderPersonas, renderPersonaDetail } from './pages/personas.js';
import { renderSettings } from './pages/settings.js';

const navEl = document.getElementById('nav');
const pageEl = document.getElementById('page');
const playerEl = document.getElementById('player');

// Initialize navigation and player
renderNav(navEl);
initPlayer(playerEl);

// Hash router
const routes = [
  { pattern: /^#\/library$/, render: () => renderLibrary(pageEl) },
  { pattern: /^#\/create$/, render: () => renderCreateSimple(pageEl) },
  { pattern: /^#\/create\/custom$/, render: () => renderCreateCustom(pageEl) },
  { pattern: /^#\/song\/(\d+)$/, render: (m) => renderSongDetail(pageEl, parseInt(m[1])) },
  { pattern: /^#\/personas\/(\d+)$/, render: (m) => renderPersonaDetail(pageEl, parseInt(m[1])) },
  { pattern: /^#\/personas$/, render: () => renderPersonas(pageEl) },
  { pattern: /^#\/settings$/, render: () => renderSettings(pageEl) },
];

function navigate() {
  const hash = window.location.hash || '#/library';
  updateNavActive(hash);

  for (const route of routes) {
    const match = hash.match(route.pattern);
    if (match) {
      route.render(match);
      return;
    }
  }

  // Default to library
  window.location.hash = '#/library';
}

window.addEventListener('hashchange', navigate);

// Initial route
if (!window.location.hash) {
  window.location.hash = '#/library';
} else {
  navigate();
}

// Register service worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

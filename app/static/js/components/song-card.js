import { api } from '../api.js';
import { getPlayer } from './player.js';

const ICON_MUSIC = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
const ICON_PLAY = `<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><polygon points="5,3 19,12 5,21"/></svg>`;

export function renderSongCard(song) {
  const el = document.createElement('div');
  el.className = 'song-card card';

  const artHtml = song.has_art
    ? `<img src="${api.artUrl(song.id)}" class="song-card-art" alt="">`
    : `<div class="song-card-art">${ICON_MUSIC}</div>`;

  const duration = song.duration
    ? `${Math.floor(song.duration / 60)}:${Math.floor(song.duration % 60).toString().padStart(2, '0')}`
    : '';

  const statusBadge = song.status === 'generating'
    ? '<span class="badge badge-generating">Generating</span>'
    : song.status === 'failed'
    ? '<span class="badge badge-failed">Failed</span>'
    : '';

  el.innerHTML = `
    ${artHtml}
    <div class="song-card-info">
      <div class="song-card-title">${song.title || 'Untitled'}</div>
      <div class="song-card-meta">${song.artist || ''} ${statusBadge}</div>
    </div>
    <span class="song-card-duration">${duration}</span>
    <div class="song-card-actions">
      ${song.has_audio ? `<button class="btn btn-ghost btn-icon play-btn" title="Play">${ICON_PLAY}</button>` : ''}
    </div>
  `;

  // Play button
  const playBtn = el.querySelector('.play-btn');
  if (playBtn) {
    playBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      getPlayer().play(song.id, song.title, song.has_art);
    });
  }

  // Click card to go to detail
  el.addEventListener('click', () => {
    window.location.hash = `#/song/${song.id}`;
  });

  return el;
}

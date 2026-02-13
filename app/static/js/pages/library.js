import { api } from '../api.js';
import { renderSongCard } from '../components/song-card.js';
import { toast } from '../components/toast.js';

const ICON_MUSIC = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;

export async function renderLibrary(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Library</h1>
      <a href="#/create" class="btn btn-primary">Create</a>
    </div>
    <div id="song-list"></div>
  `;

  const listEl = document.getElementById('song-list');

  try {
    const songs = await api.getSongs();
    if (songs.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state">
          ${ICON_MUSIC}
          <div class="empty-state-title">No songs yet</div>
          <div class="empty-state-text">Create your first AI-generated song</div>
          <a href="#/create" class="btn btn-primary">Create a Song</a>
        </div>
      `;
      return;
    }

    songs.forEach(song => {
      listEl.appendChild(renderSongCard(song));
    });
  } catch (e) {
    toast('Failed to load songs', 'error');
  }
}

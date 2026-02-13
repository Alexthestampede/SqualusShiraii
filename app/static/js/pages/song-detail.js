import { api } from '../api.js';
import { toast } from '../components/toast.js';
import { getPlayer } from '../components/player.js';

const ICON_MUSIC = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
const ICON_PLAY = `<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>`;
const ICON_SHARE = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>`;

export async function renderSongDetail(container, songId) {
  container.innerHTML = `<div class="text-center"><div class="spinner" style="margin: 48px auto;"></div></div>`;

  let song;
  try {
    song = await api.getSong(songId);
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-state-title">Song not found</div></div>`;
    return;
  }

  const artHtml = song.has_art
    ? `<img src="${api.artUrl(song.id)}" alt="">`
    : ICON_MUSIC;

  container.innerHTML = `
    <div class="detail-art">${artHtml}</div>

    <div class="section">
      <input class="form-input" id="detail-title" value="${song.title || ''}" placeholder="Song title"
        style="font-size: 20px; font-weight: 700; text-align: center; border: none; background: transparent;">
      <input class="form-input" id="detail-artist" value="${song.artist || ''}" placeholder="Artist name"
        style="font-size: 14px; text-align: center; border: none; background: transparent; color: var(--text-secondary);">
    </div>

    ${song.has_audio ? `
    <div class="flex gap-3 items-center justify-between mb-4" style="justify-content: center;">
      <button class="btn btn-primary btn-icon" id="detail-play" style="width: 56px; height: 56px;">
        ${ICON_PLAY}
      </button>
    </div>
    ` : ''}

    ${song.caption ? `
    <div class="section">
      <div class="section-title">Style</div>
      <p class="text-sm" style="color: var(--text-secondary);">${song.caption}</p>
    </div>
    ` : ''}

    ${song.lyrics ? `
    <div class="section">
      <div class="section-title">Lyrics</div>
      <div class="lyrics-display">${song.lyrics}</div>
    </div>
    ` : ''}

    <div class="section">
      <div class="section-title">Details</div>
      <div class="card" style="padding: 12px;">
        ${song.persona_name ? `<div class="setting-row"><span class="setting-label">Persona</span><span class="setting-value">${song.persona_name}</span></div>` : ''}
        ${song.bpm ? `<div class="setting-row"><span class="setting-label">BPM</span><span class="setting-value">${song.bpm}</span></div>` : ''}
        ${song.key_scale ? `<div class="setting-row"><span class="setting-label">Key</span><span class="setting-value">${song.key_scale}</span></div>` : ''}
        ${song.time_signature ? `<div class="setting-row"><span class="setting-label">Time</span><span class="setting-value">${song.time_signature}</span></div>` : ''}
        ${song.duration ? `<div class="setting-row"><span class="setting-label">Duration</span><span class="setting-value">${Math.floor(song.duration / 60)}:${Math.floor(song.duration % 60).toString().padStart(2, '0')}</span></div>` : ''}
        ${song.seed ? `<div class="setting-row"><span class="setting-label">Seed</span><span class="setting-value">${song.seed}</span></div>` : ''}
      </div>
    </div>

    <div class="section">
      <div class="section-title">Actions</div>
      <div class="flex gap-3" style="flex-wrap: wrap;">
        ${!song.has_art ? `<button class="btn btn-secondary" id="detail-gen-art">Generate Art</button>` : ''}
        ${song.has_audio ? `<button class="btn btn-secondary" id="detail-export">Export MP3</button>` : ''}
        ${song.has_audio ? `<button class="btn btn-secondary" id="detail-share">${ICON_SHARE} Share</button>` : ''}
        <button class="btn btn-danger" id="detail-delete">Delete</button>
      </div>
    </div>
  `;

  // Play
  const playBtn = document.getElementById('detail-play');
  if (playBtn) {
    playBtn.addEventListener('click', () => {
      getPlayer().play(song.id, song.title, song.has_art);
    });
  }

  // Save title/artist on blur
  const titleInput = document.getElementById('detail-title');
  const artistInput = document.getElementById('detail-artist');

  const saveField = async () => {
    try {
      await api.updateSong(song.id, {
        title: titleInput.value.trim(),
        artist: artistInput.value.trim(),
      });
    } catch (e) { /* silent */ }
  };
  titleInput.addEventListener('blur', saveField);
  artistInput.addEventListener('blur', saveField);

  // Generate art
  const artBtn = document.getElementById('detail-gen-art');
  if (artBtn) {
    artBtn.addEventListener('click', async () => {
      artBtn.disabled = true;
      artBtn.textContent = 'Generating...';
      try {
        const result = await api.generateArt({ song_id: song.id });
        if (result.error) {
          toast(result.error, 'error');
        } else {
          toast('Art generated!', 'success');
          renderSongDetail(container, songId);
        }
      } catch (e) {
        toast('Failed to generate art', 'error');
      }
      artBtn.disabled = false;
      artBtn.textContent = 'Generate Art';
    });
  }

  // Export
  const exportBtn = document.getElementById('detail-export');
  if (exportBtn) {
    exportBtn.addEventListener('click', async () => {
      exportBtn.disabled = true;
      exportBtn.textContent = 'Exporting...';
      try {
        window.open(api.exportUrl(song.id), '_blank');
      } catch (e) {
        toast('Export failed', 'error');
      }
      exportBtn.disabled = false;
      exportBtn.textContent = 'Export MP3';
    });
  }

  // Share
  const shareBtn = document.getElementById('detail-share');
  if (shareBtn) {
    shareBtn.addEventListener('click', async () => {
      const filename = `${song.title || 'song'} - ${song.artist || 'Unknown'}.mp3`;
      try {
        // Fetch the audio as a file for sharing
        const resp = await fetch(api.exportUrl(song.id));
        if (!resp.ok) throw new Error('Export failed');
        const blob = await resp.blob();
        const file = new File([blob], filename, { type: 'audio/mpeg' });

        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          await navigator.share({
            title: song.title || 'Check out this song',
            text: `${song.title} by ${song.artist}`,
            files: [file],
          });
        } else {
          // Fallback: download the file
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = filename;
          a.click();
          URL.revokeObjectURL(url);
          toast('Song downloaded', 'success');
        }
      } catch (e) {
        if (e.name !== 'AbortError') toast('Share failed', 'error');
      }
    });
  }

  // Delete
  document.getElementById('detail-delete').addEventListener('click', async () => {
    if (!confirm('Delete this song permanently?')) return;
    try {
      await api.deleteSong(song.id);
      toast('Song deleted', 'success');
      window.location.hash = '#/library';
    } catch (e) {
      toast('Failed to delete', 'error');
    }
  });
}

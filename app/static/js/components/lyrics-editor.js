import { api } from '../api.js';
import { toast } from './toast.js';

export function renderLyricsEditor(container, initialLyrics = '') {
  container.innerHTML = `
    <div class="form-group">
      <div class="flex justify-between items-center">
        <label class="form-label">Lyrics</label>
        <button class="btn btn-secondary" id="lyrics-ai-btn" style="padding: 6px 12px; font-size: 12px;">
          AI Generate
        </button>
      </div>
      <textarea class="form-textarea" id="lyrics-textarea" rows="10"
        placeholder="Write lyrics or use AI Generate...">${initialLyrics}</textarea>
    </div>
  `;

  const textarea = container.querySelector('#lyrics-textarea');
  const aiBtn = container.querySelector('#lyrics-ai-btn');

  aiBtn.addEventListener('click', async () => {
    const description = prompt('Describe the song you want lyrics for:');
    if (!description) return;

    aiBtn.disabled = true;
    aiBtn.textContent = 'Generating...';
    try {
      const result = await api.generateLyrics({ description });
      if (result.lyrics) {
        textarea.value = result.lyrics;
      }
      if (result.error) {
        toast(result.error, 'error');
      }
    } catch (e) {
      toast('Failed to generate lyrics', 'error');
    } finally {
      aiBtn.disabled = false;
      aiBtn.textContent = 'AI Generate';
    }
  });

  return {
    getValue: () => textarea.value,
    setValue: (v) => { textarea.value = v; },
  };
}

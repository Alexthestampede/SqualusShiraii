import { api } from '../api.js';
import { toast } from '../components/toast.js';

const STYLE_TAGS = [
  'Pop', 'Rock', 'Hip Hop', 'R&B', 'Electronic', 'Jazz', 'Classical',
  'Country', 'Folk', 'Metal', 'Indie', 'Lo-fi', 'Ambient', 'Funk',
  'Soul', 'Reggae', 'Latin', 'Blues', 'Punk', 'K-Pop',
];

export async function renderCreateSimple(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Create</h1>
      <a href="#/create/custom" class="btn btn-secondary">Custom</a>
    </div>

    <div class="section">
      <div class="form-group">
        <label class="form-label">Describe your song</label>
        <textarea class="form-textarea" id="create-description" rows="4"
          placeholder="A melancholic indie ballad about rainy city nights..."></textarea>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Style</div>
      <div class="chips" id="style-chips">
        ${STYLE_TAGS.map(t => `<span class="chip" data-tag="${t}">${t}</span>`).join('')}
      </div>
    </div>

    <div class="section">
      <div class="row">
        <span class="row-label">Instrumental</span>
        <label class="toggle">
          <input type="checkbox" id="create-instrumental">
          <span class="toggle-track"></span>
        </label>
      </div>
    </div>

    <button class="btn btn-primary btn-lg w-full" id="create-btn">Create Song</button>

    <div id="create-progress" class="hidden mt-4">
      <div class="progress"><div class="progress-bar" id="create-progress-bar"></div></div>
      <p class="text-sm text-muted text-center mt-4" id="create-stage">Starting...</p>
    </div>
  `;

  const selectedTags = new Set();

  // Style chip selection
  document.getElementById('style-chips').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    const tag = chip.dataset.tag;
    if (selectedTags.has(tag)) {
      selectedTags.delete(tag);
      chip.classList.remove('active');
    } else {
      selectedTags.add(tag);
      chip.classList.add('active');
    }
  });

  // Create button
  document.getElementById('create-btn').addEventListener('click', async () => {
    const description = document.getElementById('create-description').value.trim();
    if (!description) {
      toast('Please describe your song', 'error');
      return;
    }

    const data = {
      description,
      styles: [...selectedTags],
      instrumental: document.getElementById('create-instrumental').checked,
    };

    const btn = document.getElementById('create-btn');
    const progressEl = document.getElementById('create-progress');
    const progressBar = document.getElementById('create-progress-bar');
    const stageEl = document.getElementById('create-stage');

    btn.disabled = true;
    btn.textContent = 'Creating...';
    progressEl.classList.remove('hidden');

    try {
      const result = await api.createSimple(data);
      if (result.error) {
        toast(result.error, 'error');
        btn.disabled = false;
        btn.textContent = 'Create Song';
        progressEl.classList.add('hidden');
        return;
      }

      if (result.job_id) {
        // Poll for progress
        const poll = setInterval(async () => {
          try {
            const job = await api.getJob(result.job_id);
            progressBar.style.width = `${(job.progress || 0) * 100}%`;
            stageEl.textContent = job.stage || 'Processing...';

            if (job.status === 'completed') {
              clearInterval(poll);
              toast('Song created!', 'success');
              if (job.song_id) {
                window.location.hash = `#/song/${job.song_id}`;
              } else {
                window.location.hash = '#/library';
              }
            } else if (job.status === 'failed') {
              clearInterval(poll);
              toast(job.error || 'Generation failed', 'error');
              btn.disabled = false;
              btn.textContent = 'Create Song';
            }
          } catch (e) {
            clearInterval(poll);
          }
        }, 2000);
      }
    } catch (e) {
      toast('Failed to start creation', 'error');
      btn.disabled = false;
      btn.textContent = 'Create Song';
      progressEl.classList.add('hidden');
    }
  });
}

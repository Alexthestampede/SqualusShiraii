import { api } from '../api.js';
import { toast } from '../components/toast.js';
import { renderLyricsEditor } from '../components/lyrics-editor.js';

export async function renderCreateCustom(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Custom Create</h1>
      <a href="#/create" class="btn btn-secondary">Simple</a>
    </div>

    <div class="section">
      <div class="form-group">
        <label class="form-label">Song Title</label>
        <input class="form-input" id="custom-title" placeholder="Untitled">
      </div>
    </div>

    <div class="section" id="lyrics-editor-container"></div>

    <div class="section">
      <div class="form-group">
        <label class="form-label">Caption / Style</label>
        <textarea class="form-textarea" id="custom-caption" rows="3"
          placeholder="Indie rock, male raspy vocal, driving guitars, melancholic atmosphere..."></textarea>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Advanced</div>
      <div class="flex gap-3" style="flex-wrap: wrap;">
        <div class="form-group" style="flex: 1; min-width: 100px;">
          <label class="form-label">BPM</label>
          <input class="form-input" id="custom-bpm" type="number" min="30" max="300" placeholder="120">
        </div>
        <div class="form-group" style="flex: 1; min-width: 100px;">
          <label class="form-label">Duration (s)</label>
          <input class="form-input" id="custom-duration" type="number" min="10" max="600" placeholder="180">
        </div>
        <div class="form-group" style="flex: 1; min-width: 100px;">
          <label class="form-label">Key</label>
          <input class="form-input" id="custom-key" placeholder="C Major">
        </div>
      </div>
      <div class="flex gap-3" style="flex-wrap: wrap;">
        <div class="form-group" style="flex: 1; min-width: 100px;">
          <label class="form-label">Time Sig</label>
          <select class="form-select" id="custom-time-sig">
            <option value="">Auto</option>
            <option value="4/4">4/4</option>
            <option value="3/4">3/4</option>
            <option value="6/8">6/8</option>
          </select>
        </div>
        <div class="form-group" style="flex: 1; min-width: 100px;">
          <label class="form-label">Language</label>
          <select class="form-select" id="custom-language">
            <option value="en">English</option>
            <option value="zh">Chinese</option>
            <option value="ja">Japanese</option>
            <option value="ko">Korean</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
          </select>
        </div>
      </div>
      <div class="row">
        <span class="row-label">Instrumental</span>
        <label class="toggle">
          <input type="checkbox" id="custom-instrumental">
          <span class="toggle-track"></span>
        </label>
      </div>
    </div>

    <div class="section">
      <div class="form-group">
        <label class="form-label">Persona</label>
        <select class="form-select" id="custom-persona">
          <option value="">None</option>
        </select>
      </div>
      <div class="form-group hidden" id="voice-strength-group">
        <label class="form-label">Voice Influence <span id="voice-strength-val">50%</span></label>
        <input type="range" class="form-range" id="custom-voice-strength" min="10" max="100" value="50" step="5">
        <span class="text-sm text-muted">How much the persona's voice reference shapes the output</span>
      </div>
    </div>

    <button class="btn btn-primary btn-lg w-full" id="custom-create-btn">Create Song</button>

    <div id="custom-progress" class="hidden mt-4">
      <div class="progress"><div class="progress-bar" id="custom-progress-bar"></div></div>
      <p class="text-sm text-muted text-center mt-4" id="custom-stage">Starting...</p>
    </div>
  `;

  // Init lyrics editor
  const lyricsEditor = renderLyricsEditor(
    document.getElementById('lyrics-editor-container')
  );

  // Load personas
  try {
    const personas = await api.getPersonas();
    const select = document.getElementById('custom-persona');
    const strengthGroup = document.getElementById('voice-strength-group');
    const strengthSlider = document.getElementById('custom-voice-strength');
    const strengthVal = document.getElementById('voice-strength-val');

    personas.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name + (p.has_ref_audio ? ' (voice)' : '');
      select.appendChild(opt);
    });

    // Show voice strength slider when a persona with voice is selected
    select.addEventListener('change', () => {
      const pid = parseInt(select.value);
      const p = personas.find(x => x.id === pid);
      if (p && p.has_ref_audio) {
        strengthGroup.classList.remove('hidden');
      } else {
        strengthGroup.classList.add('hidden');
      }
    });

    strengthSlider.addEventListener('input', () => {
      strengthVal.textContent = strengthSlider.value + '%';
    });
  } catch (e) { /* personas optional */ }

  // Create button
  document.getElementById('custom-create-btn').addEventListener('click', async () => {
    const data = {
      title: document.getElementById('custom-title').value.trim(),
      lyrics: lyricsEditor.getValue(),
      caption: document.getElementById('custom-caption').value.trim(),
      bpm: parseInt(document.getElementById('custom-bpm').value) || null,
      duration: parseInt(document.getElementById('custom-duration').value) || null,
      key_scale: document.getElementById('custom-key').value.trim(),
      time_signature: document.getElementById('custom-time-sig').value,
      vocal_language: document.getElementById('custom-language').value,
      instrumental: document.getElementById('custom-instrumental').checked,
      persona_id: parseInt(document.getElementById('custom-persona').value) || null,
      voice_strength: parseInt(document.getElementById('custom-voice-strength').value) / 100,
    };

    if (!data.lyrics && !data.caption) {
      toast('Please provide lyrics or a caption', 'error');
      return;
    }

    const btn = document.getElementById('custom-create-btn');
    const progressEl = document.getElementById('custom-progress');
    const progressBar = document.getElementById('custom-progress-bar');
    const stageEl = document.getElementById('custom-stage');

    btn.disabled = true;
    btn.textContent = 'Creating...';
    progressEl.classList.remove('hidden');

    try {
      const result = await api.createCustom(data);
      if (result.error) {
        toast(result.error, 'error');
        btn.disabled = false;
        btn.textContent = 'Create Song';
        progressEl.classList.add('hidden');
        return;
      }

      if (result.job_id) {
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

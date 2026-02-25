import { api } from '../api.js';
import { toast } from '../components/toast.js';

// In-memory history of generated audio
const history = [];

export async function renderTTS(container) {
  // Fetch speakers and languages
  let speakers = [];
  let languages = ['Auto', 'English', 'Chinese', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'];
  try {
    const data = await api.ttsSpeakers();
    speakers = data.speakers || [];
    if (data.languages && data.languages.length) languages = data.languages;
  } catch (e) {
    // Use defaults
  }

  const speakerOptions = speakers.map(s => `<option value="${s}">${s}</option>`).join('');
  const langOptions = languages.map(l => `<option value="${l}"${l === 'Auto' ? ' selected' : ''}>${l}</option>`).join('');

  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Text-to-Speech</h1>
    </div>

    <div class="tts-tabs">
      <button class="tts-tab active" data-tab="custom">Custom Voice</button>
      <button class="tts-tab" data-tab="design">Voice Design</button>
      <button class="tts-tab" data-tab="clone">Voice Clone</button>
    </div>

    <!-- Custom Voice Tab -->
    <div class="tts-panel" id="tab-custom">
      <div class="form-group mb-4">
        <label class="form-label">Text</label>
        <textarea class="form-textarea" id="cv-text" placeholder="Enter text to speak..."></textarea>
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Speaker</label>
        <select class="form-select" id="cv-speaker">
          ${speakerOptions}
        </select>
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Language</label>
        <select class="form-select" id="cv-language">${langOptions}</select>
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Instruction (optional)</label>
        <input class="form-input" id="cv-instruct" placeholder="e.g. speak angrily, whisper softly...">
      </div>
      <button class="btn btn-primary btn-lg w-full" id="cv-generate">Generate</button>
    </div>

    <!-- Voice Design Tab -->
    <div class="tts-panel hidden" id="tab-design">
      <div class="form-group mb-4">
        <label class="form-label">Text</label>
        <textarea class="form-textarea" id="vd-text" placeholder="Enter text to speak..."></textarea>
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Voice Description</label>
        <textarea class="form-textarea" id="vd-instruct" placeholder="Describe the voice: e.g. a warm female voice with a slight accent, speaking slowly and calmly"></textarea>
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Language</label>
        <select class="form-select" id="vd-language">${langOptions}</select>
      </div>
      <button class="btn btn-primary btn-lg w-full" id="vd-generate">Generate</button>
    </div>

    <!-- Voice Clone Tab -->
    <div class="tts-panel hidden" id="tab-clone">
      <div class="form-group mb-4">
        <label class="form-label">Text</label>
        <textarea class="form-textarea" id="vc-text" placeholder="Enter text to speak..."></textarea>
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Reference Audio</label>
        <input type="file" class="form-input" id="vc-ref-audio" accept="audio/*">
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Reference Text (transcript of the audio)</label>
        <textarea class="form-textarea" id="vc-ref-text" placeholder="What is being said in the reference audio..." style="min-height:60px;"></textarea>
      </div>
      <div class="form-group mb-4">
        <label class="form-label">Language</label>
        <select class="form-select" id="vc-language">${langOptions}</select>
      </div>
      <button class="btn btn-primary btn-lg w-full" id="vc-generate">Generate</button>
    </div>

    <!-- Result Area -->
    <div class="tts-result hidden" id="tts-result">
      <div class="tts-result-header">
        <span class="tts-result-label">Generated Audio</span>
        <a class="btn btn-secondary btn-sm" id="tts-download" download>Download</a>
      </div>
      <audio controls id="tts-audio" class="w-full"></audio>
    </div>

    <!-- Loading -->
    <div class="tts-loading hidden" id="tts-loading">
      <div class="spinner"></div>
      <span>Generating speech...</span>
    </div>

    <!-- History -->
    <div id="tts-history-section" class="${history.length ? '' : 'hidden'}">
      <div class="section-title" style="margin-top:24px;">Recent Generations</div>
      <div class="tts-history" id="tts-history"></div>
    </div>
  `;

  // Tab switching
  container.querySelectorAll('.tts-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      container.querySelectorAll('.tts-tab').forEach(t => t.classList.remove('active'));
      container.querySelectorAll('.tts-panel').forEach(p => p.classList.add('hidden'));
      tab.classList.add('active');
      container.querySelector(`#tab-${tab.dataset.tab}`).classList.remove('hidden');
    });
  });

  const resultEl = document.getElementById('tts-result');
  const audioEl = document.getElementById('tts-audio');
  const downloadEl = document.getElementById('tts-download');
  const loadingEl = document.getElementById('tts-loading');

  function showLoading() {
    loadingEl.classList.remove('hidden');
    resultEl.classList.add('hidden');
  }

  function hideLoading() {
    loadingEl.classList.add('hidden');
  }

  function showResult(filename, label) {
    const url = api.ttsAudioUrl(filename);
    audioEl.src = url;
    downloadEl.href = url;
    downloadEl.download = filename;
    resultEl.classList.remove('hidden');
    audioEl.play().catch(() => {});

    // Add to history
    history.unshift({ filename, label, url, time: new Date() });
    if (history.length > 20) history.pop();
    renderHistory();
  }

  function renderHistory() {
    const section = document.getElementById('tts-history-section');
    const el = document.getElementById('tts-history');
    if (!history.length) {
      section.classList.add('hidden');
      return;
    }
    section.classList.remove('hidden');
    el.innerHTML = history.map((h, i) => `
      <div class="tts-history-item card" data-idx="${i}">
        <div class="tts-history-info">
          <span class="tts-history-label">${escapeHtml(h.label)}</span>
          <span class="text-sm text-muted">${timeAgo(h.time)}</span>
        </div>
        <div class="tts-history-actions">
          <button class="btn btn-ghost btn-icon tts-history-play" data-url="${h.url}" title="Play">
            <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
          </button>
          <a class="btn btn-ghost btn-icon" href="${h.url}" download="${h.filename}" title="Download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </a>
        </div>
      </div>
    `).join('');

    el.querySelectorAll('.tts-history-play').forEach(btn => {
      btn.addEventListener('click', () => {
        audioEl.src = btn.dataset.url;
        resultEl.classList.remove('hidden');
        audioEl.play().catch(() => {});
      });
    });
  }

  // Custom Voice generate
  document.getElementById('cv-generate').addEventListener('click', async () => {
    const text = document.getElementById('cv-text').value.trim();
    const speaker = document.getElementById('cv-speaker').value;
    const language = document.getElementById('cv-language').value;
    const instruct = document.getElementById('cv-instruct').value.trim();

    if (!text) { toast('Enter some text', 'error'); return; }
    if (!speaker) { toast('Select a speaker', 'error'); return; }

    showLoading();
    try {
      const res = await api.ttsCustomVoice({ text, speaker, language, instruct });
      hideLoading();
      showResult(res.filename, `${speaker}: "${truncate(text, 40)}"`);
    } catch (e) {
      hideLoading();
      toast(e.message || 'Generation failed', 'error');
    }
  });

  // Voice Design generate
  document.getElementById('vd-generate').addEventListener('click', async () => {
    const text = document.getElementById('vd-text').value.trim();
    const instruct = document.getElementById('vd-instruct').value.trim();
    const language = document.getElementById('vd-language').value;

    if (!text) { toast('Enter some text', 'error'); return; }
    if (!instruct) { toast('Describe the voice style', 'error'); return; }

    showLoading();
    try {
      const res = await api.ttsDesign({ text, instruct, language });
      hideLoading();
      showResult(res.filename, `Design: "${truncate(instruct, 40)}"`);
    } catch (e) {
      hideLoading();
      toast(e.message || 'Generation failed', 'error');
    }
  });

  // Voice Clone generate
  document.getElementById('vc-generate').addEventListener('click', async () => {
    const text = document.getElementById('vc-text').value.trim();
    const refAudioInput = document.getElementById('vc-ref-audio');
    const refText = document.getElementById('vc-ref-text').value.trim();
    const language = document.getElementById('vc-language').value;

    if (!text) { toast('Enter some text', 'error'); return; }
    if (!refAudioInput.files.length) { toast('Upload a reference audio file', 'error'); return; }

    showLoading();
    try {
      const formData = new FormData();
      formData.append('text', text);
      formData.append('ref_text', refText);
      formData.append('language', language);
      formData.append('ref_audio', refAudioInput.files[0]);

      const res = await api.ttsCloneUpload(formData);
      hideLoading();
      showResult(res.filename, `Clone: "${truncate(text, 40)}"`);
    } catch (e) {
      hideLoading();
      toast(e.message || 'Generation failed', 'error');
    }
  });

  // Render any existing history
  renderHistory();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function truncate(str, len) {
  return str.length > len ? str.slice(0, len) + '...' : str;
}

function timeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

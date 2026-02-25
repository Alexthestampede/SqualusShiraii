import { api } from '../api.js';
import { toast } from '../components/toast.js';

export async function renderSettings(container) {
  let settings = {};
  try {
    settings = await api.getSettings();
  } catch (e) { /* use defaults */ }

  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Settings</h1>
    </div>

    <div class="section">
      <div class="section-title">LLM (Lyrics Generation)</div>
      <div class="card" style="padding: 16px;">
        <div class="form-group mb-4">
          <label class="form-label">Provider</label>
          <select class="form-select" id="set-llm-provider">
            <option value="ollama" ${settings.llm_provider === 'ollama' ? 'selected' : ''}>Ollama</option>
            <option value="lm_studio" ${settings.llm_provider === 'lm_studio' ? 'selected' : ''}>LM Studio</option>
            <option value="openai" ${settings.llm_provider === 'openai' ? 'selected' : ''}>OpenAI</option>
            <option value="claude" ${settings.llm_provider === 'claude' ? 'selected' : ''}>Claude</option>
            <option value="gemini" ${settings.llm_provider === 'gemini' ? 'selected' : ''}>Gemini</option>
          </select>
        </div>
        <div class="form-group mb-4">
          <label class="form-label">Base URL</label>
          <input class="form-input" id="set-llm-url" value="${settings.llm_base_url || 'http://localhost:11434'}"
            placeholder="http://localhost:11434">
        </div>
        <div class="form-group mb-4">
          <label class="form-label">API Key (cloud providers)</label>
          <input class="form-input" id="set-llm-key" type="password" value="${settings.llm_api_key || ''}"
            placeholder="Optional">
        </div>
        <div class="form-group">
          <label class="form-label">Model</label>
          <div class="flex gap-3">
            <select class="form-select" id="set-llm-model" style="flex:1;">
              ${settings.llm_model ? `<option value="${settings.llm_model}" selected>${settings.llm_model}</option>` : '<option value="">Select model...</option>'}
            </select>
            <button class="btn btn-secondary" id="set-llm-refresh">Refresh</button>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Image Generation (Draw Things)</div>
      <div class="card" style="padding: 16px;">
        <div class="form-group mb-4">
          <label class="form-label">gRPC Server</label>
          <div class="flex gap-3">
            <input class="form-input" id="set-grpc-server" value="${settings.grpc_server || '192.168.2.150:7859'}"
              placeholder="192.168.2.150:7859" style="flex:1;">
            <button class="btn btn-secondary" id="set-grpc-connect">Connect</button>
          </div>
        </div>
        <div class="form-group mb-4">
          <label class="form-label">Model</label>
          <div style="position:relative;" id="grpc-model-wrapper">
            <input class="form-input" id="set-grpc-model-search" autocomplete="off"
              placeholder="Search models..." value="">
            <input type="hidden" id="set-grpc-model" value="${settings.grpc_model || ''}">
            <div class="dropdown-list" id="grpc-model-dropdown"></div>
          </div>
          <span class="text-sm text-muted" id="grpc-model-hint">
            ${settings.grpc_model ? 'Selected: ' + settings.grpc_model : 'Connect to server to load models'}
          </span>
        </div>
        <div class="form-group mb-4">
          <label class="form-label">Preset</label>
          <select class="form-select" id="set-grpc-preset">
            <option value="">None (use manual settings)</option>
          </select>
          <span class="text-sm text-muted">Presets fill in steps, CFG, scheduler etc. Model is always separate.</span>
        </div>
        <div class="form-group mb-4">
          <label class="form-label">Negative Prompt</label>
          <input class="form-input" id="set-grpc-negative" value="${settings.grpc_negative_prompt || ''}"
            placeholder="e.g. blurry, low quality, text, watermark">
        </div>
        <div class="flex gap-3 mb-4" style="flex-wrap: wrap;">
          <div class="form-group" style="flex: 1; min-width: 100px;">
            <label class="form-label">Width</label>
            <input class="form-input" id="set-grpc-width" type="number" value="${settings.grpc_width || '1024'}" min="256" max="2048" step="64">
          </div>
          <div class="form-group" style="flex: 1; min-width: 100px;">
            <label class="form-label">Height</label>
            <input class="form-input" id="set-grpc-height" type="number" value="${settings.grpc_height || '1024'}" min="256" max="2048" step="64">
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Music Generation (ACE-Step)</div>
      <div class="card" style="padding: 16px;">
        <div class="form-group">
          <label class="form-label">API URL</label>
          <input class="form-input" id="set-acestep-url" value="${settings.acestep_url || 'http://127.0.0.1:8001'}"
            placeholder="http://127.0.0.1:8001">
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Text-to-Speech (Qwen3)</div>
      <div class="card" style="padding: 16px;">
        <div class="form-group">
          <label class="form-label">Model Size</label>
          <select class="form-select" id="set-tts-size">
            <option value="0.6B" ${settings.tts_model_size === '1.7B' ? '' : 'selected'}>0.6B (Faster, less VRAM)</option>
            <option value="1.7B" ${settings.tts_model_size === '1.7B' ? 'selected' : ''}>1.7B (Higher quality)</option>
          </select>
          <span class="text-sm text-muted">Voice Design mode always uses 1.7B (only size available).</span>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">General</div>
      <div class="card" style="padding: 16px;">
        <div class="form-group">
          <label class="form-label">Default Artist Name</label>
          <input class="form-input" id="set-artist" value="${settings.default_artist || 'Squalus Shiraii'}"
            placeholder="Artist name">
        </div>
      </div>
    </div>

    <button class="btn btn-primary btn-lg w-full mt-4" id="set-save">Save Settings</button>
  `;

  // --- Draw Things model search dropdown ---
  let grpcModels = [];  // [{file, name}, ...]
  const modelSearch = document.getElementById('set-grpc-model-search');
  const modelHidden = document.getElementById('set-grpc-model');
  const modelDropdown = document.getElementById('grpc-model-dropdown');
  const modelHint = document.getElementById('grpc-model-hint');

  function renderModelDropdown(filter) {
    const q = (filter || '').toLowerCase();
    const matches = grpcModels.filter(m =>
      m.name.toLowerCase().includes(q) || m.file.toLowerCase().includes(q)
    ).slice(0, 50);

    if (!matches.length) {
      modelDropdown.innerHTML = '<div class="dropdown-item disabled">No matches</div>';
      modelDropdown.classList.add('open');
      return;
    }

    modelDropdown.innerHTML = matches.map(m => `
      <div class="dropdown-item" data-file="${m.file}">${m.name}
        <span class="text-sm text-muted" style="display:block;font-size:0.75rem;">${m.file}</span>
      </div>
    `).join('');
    modelDropdown.classList.add('open');

    modelDropdown.querySelectorAll('.dropdown-item').forEach(el => {
      el.addEventListener('click', () => {
        modelHidden.value = el.dataset.file;
        modelSearch.value = el.querySelector('.text-sm') ?
          el.childNodes[0].textContent.trim() : el.textContent.trim();
        modelHint.textContent = 'Selected: ' + el.dataset.file;
        modelDropdown.classList.remove('open');
      });
    });
  }

  modelSearch.addEventListener('focus', () => {
    if (grpcModels.length) renderModelDropdown(modelSearch.value);
  });
  modelSearch.addEventListener('input', () => {
    if (grpcModels.length) renderModelDropdown(modelSearch.value);
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#grpc-model-wrapper')) {
      modelDropdown.classList.remove('open');
    }
  });

  // Set initial display name if model is already configured
  if (settings.grpc_model) {
    // Will be updated once models are loaded
    modelSearch.value = settings.grpc_model;
  }

  async function loadGrpcModels() {
    const btn = document.getElementById('set-grpc-connect');
    btn.disabled = true;
    btn.textContent = 'Connecting...';
    try {
      const result = await api.getGrpcModels();
      if (result.error) {
        toast(`Connection failed: ${result.error}`, 'error');
        btn.textContent = 'Connect';
        btn.disabled = false;
        return;
      }
      grpcModels = result.models || [];
      toast(`Connected! ${grpcModels.length} models available`, 'success');
      btn.textContent = 'Connected';
      btn.disabled = false;

      // Update search box display name if a model is already selected
      if (modelHidden.value) {
        const match = grpcModels.find(m => m.file === modelHidden.value);
        if (match) {
          modelSearch.value = match.name;
          modelHint.textContent = 'Selected: ' + match.file;
        }
      }
    } catch (e) {
      toast('Connection failed', 'error');
      btn.textContent = 'Connect';
      btn.disabled = false;
    }
  }

  // Connect button
  document.getElementById('set-grpc-connect').addEventListener('click', loadGrpcModels);

  // Auto-connect on page load
  loadGrpcModels();

  // Refresh LLM models
  document.getElementById('set-llm-refresh').addEventListener('click', async () => {
    try {
      const models = await api.getLlmModels();
      const select = document.getElementById('set-llm-model');
      const current = select.value;
      select.innerHTML = '<option value="">Select model...</option>';
      (Array.isArray(models) ? models : []).forEach(m => {
        const name = typeof m === 'string' ? m : m.name || m;
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        if (name === current) opt.selected = true;
        select.appendChild(opt);
      });
      toast(`Found ${models.length} models`, 'success');
    } catch (e) {
      toast('Failed to discover models', 'error');
    }
  });

  // Load presets into dropdown
  try {
    const presets = await api.getPresets();
    const select = document.getElementById('set-grpc-preset');
    presets.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.name || p;
      opt.textContent = `${p.name || p}${p.description ? ' - ' + p.description : ''}`;
      if (opt.value === settings.grpc_preset) opt.selected = true;
      select.appendChild(opt);
    });
  } catch (e) { /* presets optional */ }

  // Save
  document.getElementById('set-save').addEventListener('click', async () => {
    const data = {
      llm_provider: document.getElementById('set-llm-provider').value,
      llm_base_url: document.getElementById('set-llm-url').value.trim(),
      llm_api_key: document.getElementById('set-llm-key').value.trim(),
      llm_model: document.getElementById('set-llm-model').value,
      grpc_server: document.getElementById('set-grpc-server').value.trim(),
      grpc_model: modelHidden.value,
      grpc_preset: document.getElementById('set-grpc-preset').value,
      grpc_negative_prompt: document.getElementById('set-grpc-negative').value.trim(),
      grpc_width: document.getElementById('set-grpc-width').value,
      grpc_height: document.getElementById('set-grpc-height').value,
      acestep_url: document.getElementById('set-acestep-url').value.trim(),
      tts_model_size: document.getElementById('set-tts-size').value,
      default_artist: document.getElementById('set-artist').value.trim(),
    };

    try {
      await api.updateSettings(data);
      toast('Settings saved', 'success');
    } catch (e) {
      toast('Failed to save settings', 'error');
    }
  });
}

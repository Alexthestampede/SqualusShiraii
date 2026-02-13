import { api } from '../api.js';
import { renderPersonaCard } from '../components/persona-card.js';
import { toast } from '../components/toast.js';

const ICON_USER = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;

export async function renderPersonas(container) {
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Personas</h1>
      <button class="btn btn-primary" id="add-persona-btn">New</button>
    </div>
    <div class="persona-grid" id="persona-grid"></div>
  `;

  const grid = document.getElementById('persona-grid');

  try {
    const personas = await api.getPersonas();
    if (personas.length === 0) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          ${ICON_USER}
          <div class="empty-state-title">No personas</div>
          <div class="empty-state-text">Create a persona with a unique voice and portrait</div>
        </div>
      `;
    } else {
      personas.forEach(p => grid.appendChild(renderPersonaCard(p)));
    }
  } catch (e) {
    toast('Failed to load personas', 'error');
  }

  document.getElementById('add-persona-btn').addEventListener('click', () => {
    showPersonaModal(container);
  });
}


export async function renderPersonaDetail(container, personaId) {
  container.innerHTML = `<div class="text-center"><div class="spinner" style="margin: 48px auto;"></div></div>`;

  let persona;
  try {
    persona = await api.getPersona(personaId);
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-state-title">Persona not found</div></div>`;
    return;
  }

  const avatarHtml = persona.has_portrait
    ? `<img src="${api.portraitUrl(persona.id)}" alt="">`
    : ICON_USER;

  container.innerHTML = `
    <div class="page-header">
      <a href="#/personas" class="btn btn-secondary">Back</a>
    </div>

    <div class="detail-art">${avatarHtml}</div>

    <div class="section">
      <input class="form-input" id="pd-name" value="${persona.name || ''}" placeholder="Persona name"
        style="font-size: 20px; font-weight: 700; text-align: center; border: none; background: transparent;">
    </div>

    <div class="section">
      <div class="section-title">Description</div>
      <div class="card" style="padding: 12px;">
        <textarea class="form-textarea" id="pd-desc" rows="3"
          placeholder="Describe the persona's vocal style, character, mood..."
          style="background: transparent; border: none; width: 100%;">${persona.description || ''}</textarea>
      </div>
      <span class="text-sm text-muted">This description is prepended to the song caption when this persona is selected.</span>
    </div>

    <div class="section">
      <div class="section-title">Voice Reference</div>
      <div class="card" style="padding: 12px;">
        <div class="setting-row">
          <span class="setting-label">Reference Audio</span>
          <span class="setting-value">${persona.has_ref_audio ? 'Uploaded' : 'None'}</span>
        </div>
        ${persona.ref_text ? `
        <div class="setting-row">
          <span class="setting-label">Reference Text</span>
          <span class="setting-value text-sm">${persona.ref_text}</span>
        </div>
        ` : ''}
        <div class="setting-row">
          <span class="setting-label">Voice Prompt</span>
          <span class="setting-value">${persona.has_voice ? 'Built' : 'Not built'}</span>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Actions</div>
      <div class="flex gap-3" style="flex-wrap: wrap;">
        <button class="btn btn-secondary" id="pd-gen-portrait">
          ${persona.has_portrait ? 'Regenerate Portrait' : 'Generate Portrait'}
        </button>
        <button class="btn btn-secondary" id="pd-save">Save Changes</button>
        <button class="btn btn-danger" id="pd-delete">Delete</button>
      </div>
    </div>
  `;

  // Save changes
  document.getElementById('pd-save').addEventListener('click', async () => {
    try {
      await api.updatePersona(persona.id, {
        name: document.getElementById('pd-name').value.trim(),
        description: document.getElementById('pd-desc').value.trim(),
      });
      toast('Persona updated', 'success');
    } catch (e) {
      toast('Failed to update', 'error');
    }
  });

  // Generate portrait
  document.getElementById('pd-gen-portrait').addEventListener('click', async () => {
    const btn = document.getElementById('pd-gen-portrait');
    btn.disabled = true;
    btn.textContent = 'Generating...';
    try {
      const result = await api.generatePortrait(persona.id);
      if (result.error) {
        toast(result.error, 'error');
      } else {
        toast('Portrait generated!', 'success');
        renderPersonaDetail(container, personaId);
      }
    } catch (e) {
      toast('Portrait generation failed', 'error');
    }
    btn.disabled = false;
  });

  // Delete
  document.getElementById('pd-delete').addEventListener('click', async () => {
    if (!confirm(`Delete persona "${persona.name}" permanently?`)) return;
    try {
      await api.deletePersona(persona.id);
      toast('Persona deleted', 'success');
      window.location.hash = '#/personas';
    } catch (e) {
      toast('Failed to delete', 'error');
    }
  });
}


function showPersonaModal(pageContainer) {
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `
    <div class="modal">
      <h2 style="margin-bottom: 16px;">New Persona</h2>
      <div class="section">
        <div class="form-group">
          <label class="form-label">Name</label>
          <input class="form-input" id="persona-name" placeholder="Persona name">
        </div>
        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea class="form-textarea" id="persona-desc" rows="3"
            placeholder="Describe the persona's style and voice..."></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">Reference Audio</label>
          <input type="file" class="form-input" id="persona-audio" accept="audio/*">
        </div>
        <div class="form-group">
          <label class="form-label">Reference Text (what is said in the audio)</label>
          <input class="form-input" id="persona-ref-text" placeholder="Transcript of the reference audio">
        </div>
      </div>
      <div class="flex gap-3">
        <button class="btn btn-secondary" id="persona-cancel" style="flex:1;">Cancel</button>
        <button class="btn btn-primary" id="persona-save" style="flex:1;">Create</button>
      </div>
    </div>
  `;

  document.body.appendChild(backdrop);

  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) backdrop.remove();
  });

  document.getElementById('persona-cancel').addEventListener('click', () => backdrop.remove());

  document.getElementById('persona-save').addEventListener('click', async () => {
    const name = document.getElementById('persona-name').value.trim();
    if (!name) {
      toast('Name is required', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', document.getElementById('persona-desc').value.trim());
    formData.append('ref_text', document.getElementById('persona-ref-text').value.trim());

    const audioFile = document.getElementById('persona-audio').files[0];
    if (audioFile) formData.append('ref_audio', audioFile);

    try {
      const result = await api.createPersona(formData);
      toast('Persona created!', 'success');
      backdrop.remove();
      // Navigate to the new persona's detail page
      if (result.id) {
        window.location.hash = `#/personas/${result.id}`;
      } else {
        renderPersonas(pageContainer);
      }
    } catch (e) {
      toast('Failed to create persona', 'error');
    }
  });
}

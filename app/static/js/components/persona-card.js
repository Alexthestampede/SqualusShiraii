const ICON_USER = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
const ICON_MIC = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>`;

export function renderPersonaCard(persona) {
  const el = document.createElement('div');
  el.className = 'persona-card card';
  el.style.cursor = 'pointer';

  const avatar = persona.has_portrait
    ? `<img src="/api/personas/${persona.id}/portrait" class="persona-avatar" alt="">`
    : `<div class="persona-avatar">${ICON_USER}</div>`;

  const badges = [];
  if (persona.has_ref_audio) badges.push(`<span class="badge badge-sm">${ICON_MIC} Voice</span>`);

  el.innerHTML = `
    ${avatar}
    <div class="persona-name">${persona.name}</div>
    ${badges.length ? `<div class="persona-badges">${badges.join('')}</div>` : ''}
  `;

  el.addEventListener('click', () => {
    window.location.hash = `#/personas/${persona.id}`;
  });

  return el;
}

const BASE = '';

async function request(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

async function uploadForm(method, path, formData) {
  const res = await fetch(`${BASE}${path}`, { method, body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  // Songs
  getSongs: (q = '', offset = 0, limit = 50) =>
    request('GET', `/api/songs?q=${encodeURIComponent(q)}&offset=${offset}&limit=${limit}`),
  getSong: (id) => request('GET', `/api/songs/${id}`),
  updateSong: (id, data) => request('POST', `/api/songs/${id}`, data),
  deleteSong: (id) => request('DELETE', `/api/songs/${id}`),
  audioUrl: (id) => `/api/songs/${id}/audio`,
  artUrl: (id) => `/api/songs/${id}/art`,
  exportUrl: (id) => `/api/songs/${id}/export`,

  // Create
  createSimple: (data) => request('POST', '/api/create/simple', data),
  createCustom: (data) => request('POST', '/api/create/custom', data),

  // Lyrics
  generateLyrics: (data) => request('POST', '/api/lyrics/generate', data),
  formatLyrics: (data) => request('POST', '/api/lyrics/format', data),

  // Music
  generateMusic: (data) => request('POST', '/api/music/generate', data),
  repaintMusic: (data) => request('POST', '/api/music/repaint', data),

  // Art
  generateArt: (data) => request('POST', '/api/art/generate', data),
  getPresets: () => request('GET', '/api/art/presets'),

  // Personas
  getPersonas: () => request('GET', '/api/personas'),
  createPersona: (formData) => uploadForm('POST', '/api/personas', formData),
  getPersona: (id) => request('GET', `/api/personas/${id}`),
  updatePersona: (id, data) => request('PUT', `/api/personas/${id}`, data),
  deletePersona: (id) => request('DELETE', `/api/personas/${id}`),
  generatePortrait: (id, data) => request('POST', `/api/personas/${id}/generate-portrait`, data || {}),
  previewVoice: (id, data) => request('POST', `/api/personas/${id}/preview-voice`, data || {}),
  portraitUrl: (id) => `/api/personas/${id}/portrait`,

  // TTS
  ttsClone: (data) => request('POST', '/api/tts/clone', data),
  ttsCloneUpload: (formData) => uploadForm('POST', '/api/tts/clone-upload', formData),
  ttsDesign: (data) => request('POST', '/api/tts/design', data),
  ttsCustomVoice: (data) => request('POST', '/api/tts/custom-voice', data),
  ttsSpeakers: () => request('GET', '/api/tts/speakers'),
  ttsAudioUrl: (filename) => '/api/tts/audio/' + encodeURIComponent(filename),

  // Jobs
  getJob: (id) => request('GET', `/api/jobs/${id}`),
  streamJob: (id) => new EventSource(`/api/jobs/${id}/stream`),

  // Settings
  getSettings: () => request('GET', '/api/settings'),
  updateSettings: (data) => request('PUT', '/api/settings', data),
  getLlmModels: () => request('GET', '/api/settings/llm/models'),
  getGrpcModels: () => request('GET', '/api/settings/grpc/models'),
};

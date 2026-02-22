const BASE = '';

export async function uploadTrack(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/api/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteTrack(id) {
  const res = await fetch(`${BASE}/api/tracks/${id}`, { method: 'DELETE' });
  return res.json();
}

export function getWaveformUrl(id) {
  return `${BASE}/api/tracks/${id}/waveform`;
}

export async function getTransitions() {
  const res = await fetch(`${BASE}/api/transitions`);
  return res.json();
}

export async function getEffects() {
  const res = await fetch(`${BASE}/api/effects`);
  return res.json();
}

export async function renderPreview(params) {
  const res = await fetch(`${BASE}/api/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function renderMix(params) {
  const res = await fetch(`${BASE}/api/mix`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getMixDownloadUrl() {
  return `${BASE}/api/mix/download`;
}

export async function saveProject(state) {
  const res = await fetch(`${BASE}/api/project/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function loadProject(project) {
  const res = await fetch(`${BASE}/api/project/load`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

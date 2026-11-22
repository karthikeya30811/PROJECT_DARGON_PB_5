// API client: the ONLY module in the frontend that calls fetch. All URLs are relative (/api).
// Non-OK responses throw an Error with the server's detail (or statusText) and a numeric .status.

async function request(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let message = res.statusText || `Request failed (${res.status})`;
    try {
      const body = await res.json();
      const detail = body.detail || body.error || body.message;
      if (detail) message = typeof detail === 'string' ? detail : JSON.stringify(detail);
    } catch (_) {
      // Body was not JSON; keep the status text.
    }
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function postJson(path, payload) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function health() {
  return request('/api/health');
}

export function analyze(text, language) {
  return postJson('/api/analyze', { text, language });
}

export function answers(profile, answerMap) {
  return postJson('/api/answers', { profile, answers: answerMap });
}

// Not in the current backend contract; assumes GET /api/schemes/{id}.
export function getScheme(id) {
  return request(`/api/schemes/${encodeURIComponent(id)}`);
}

export function saveTracker(entry) {
  return postJson('/api/tracker', entry);
}

export function getTracker(userId) {
  return request(`/api/tracker/${encodeURIComponent(userId)}`);
}

export function transcribe(blob, language) {
  const form = new FormData();
  form.append('audio', blob, 'recording.webm');
  form.append('language', language);
  return request('/api/voice-evaluate', { method: 'POST', body: form });
}

export function reportOutdated(schemeId, note = '') {
  return postJson('/api/report-outdated', { scheme_id: schemeId, note });
}

export function icsUrl(userId) {
  return `/api/reminders/ics?user_id=${encodeURIComponent(userId)}`;
}

export function getUserId() {
  const KEY = 'cwy_user_id';
  let id = null;
  try {
    id = localStorage.getItem(KEY);
  } catch (_) {
    // Storage unavailable; fall through and use an in-memory id.
  }
  if (!id) {
    id =
      typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2) + Date.now().toString(36);
    try {
      localStorage.setItem(KEY, id);
    } catch (_) {
      // Storage unavailable; the id lasts for this page load only.
    }
  }
  return id;
}

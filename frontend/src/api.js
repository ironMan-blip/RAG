const API_BASE = 'http://localhost:8001/api';

// JSON from the backend. Throws on network failure (no .status) or a non-2xx reply:
// .status, plus .detail when the backend explained it in words (validation errors come as a list, so no detail)
export async function api(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : undefined;
    throw Object.assign(new Error(detail ?? `HTTP ${res.status}`), { status: res.status, detail });
  }
  return data;
}

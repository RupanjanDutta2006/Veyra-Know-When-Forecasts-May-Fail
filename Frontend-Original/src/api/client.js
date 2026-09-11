const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_API_KEY || '';

export async function apiRequest(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    ...(options.headers || {}),
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || 15000);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const body = await response.json().catch(() => null);

    if (!response.ok) {
      const errorMsg =
        body?.detail ||
        (Array.isArray(body?.detail) ? body.detail.map((e) => e.msg).join(', ') : null) ||
        body?.message ||
        `Request failed with HTTP ${response.status}`;
      const err = new Error(errorMsg);
      err.status = response.status;
      err.data = body;
      throw err;
    }

    return body;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out while waiting for backend response.');
    }
    throw error;
  }
}

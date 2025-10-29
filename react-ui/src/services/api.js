const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function sendQuery(query, batch) {
  const body = { query };
  if (batch) body.batch = batch;

  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json();
}

// Same-origin /api in production (Vercel serverless).
// In dev, Vite proxy forwards /api → localhost:8000.
const BASE = '/api'

async function request(path) {
  let res
  try {
    res = await fetch(`${BASE}${path}`)
  } catch {
    throw new Error(
      'Cannot reach the backend. If running locally, make sure the server is running: bash start.sh'
    )
  }

  if (!res.ok) {
    const err = await res.json().catch(() => null)
    if (err?.detail) throw new Error(err.detail)
    throw new Error(`Server error ${res.status}: ${res.statusText}`)
  }

  return res.json()
}

export const api = {
  predict: (ticker) => request(`/predict/${ticker}`),
  accuracy: (ticker) => request(`/accuracy/${ticker}`),
  featureImportance: () => request('/feature-importance'),
  calendar: () => request('/calendar'),
  health: () => request('/health'),
  trainStatus: () => request('/train/status'),
  triggerTrain: () =>
    fetch(`${BASE}/train`, { method: 'POST' }).then((r) => r.json()),
}

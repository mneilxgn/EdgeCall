// In production, VITE_API_URL points to the Railway backend.
// In dev, Vite's proxy forwards /api → localhost:8000.
const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

async function request(path) {
  let res
  try {
    res = await fetch(`${BASE}${path}`)
  } catch {
    throw new Error(
      'Cannot reach the EdgeCall backend. Make sure the backend server is running on port 8000 (run: bash start.sh), or set VITE_API_URL to your deployed backend URL.'
    )
  }

  if (!res.ok) {
    // Try to parse a JSON error message from FastAPI
    const err = await res.json().catch(() => null)
    if (err?.detail) throw new Error(err.detail)
    // 404 on /api/* usually means the backend isn't connected in this deployment
    if (res.status === 404) {
      throw new Error(
        'Backend not connected. Set VITE_API_URL in your Vercel environment variables to point to your deployed backend, then redeploy.'
      )
    }
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

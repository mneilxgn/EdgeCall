const BASE = '/api'

async function request(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
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

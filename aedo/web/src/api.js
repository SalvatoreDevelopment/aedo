// Client dell'API di Aedo. In dev, Vite inoltra /api al server FastAPI.

const BASE = '/api'

async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export const api = {
  campaigns: () => get('/campaigns'),
  campaign: (id) => get(`/campaigns/${id}`),
  inventory: (id) => get(`/campaigns/${id}/inventory`),
  relationships: (id) => get(`/campaigns/${id}/relationships`),
  objectives: (id) => get(`/campaigns/${id}/objectives`),
  events: (id) => get(`/campaigns/${id}/events`),
}

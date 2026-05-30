const BASE = import.meta.env.VITE_API_BASE || ''

class ApiClient {
  getUser() {
    return { id: 'admin', email: 'admin@intelhub.local', display_name: 'Admin', role: 'admin', tier: 'v4' }
  }

  async request(path, options = {}) {
    const url = `${BASE}${path}`
    const headers = { 'Content-Type': 'application/json', ...options.headers }
    const res = await fetch(url, { ...options, headers })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
    return { data, status: res.status }
  }

  get(path) { return this.request(path) }
  post(path, body) { return this.request(path, { method: 'POST', body: JSON.stringify(body) }) }
  put(path, body) { return this.request(path, { method: 'PUT', body: JSON.stringify(body) }) }
  delete(path) { return this.request(path, { method: 'DELETE' }) }
}

export const api = new ApiClient()

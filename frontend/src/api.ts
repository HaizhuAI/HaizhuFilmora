const BASE = ''

async function req(path: string, opts: RequestInit = {}) {
  const res = await fetch(BASE + path, { credentials: 'include', ...opts })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = j?.error?.message || j?.detail || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  const ct = res.headers.get('content-type') || ''
  return ct.includes('json') ? res.json() : res
}

export const api = {
  login: (password: string) => req('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) }),
  logout: () => req('/api/auth/logout', { method: 'POST' }),
  me: () => req('/api/auth/me'),
  health: () => req('/api/health'),

  listMedia: () => req('/api/media'),
  getMedia: (id: string) => req(`/api/media/${id}`),
  uploadMedia: (file: File) => {
    const fd = new FormData(); fd.append('file', file)
    return req('/api/media/upload', { method: 'POST', body: fd })
  },
  deleteMedia: (id: string) => req(`/api/media/${id}`, { method: 'DELETE' }),

  filters: () => req('/api/edit/filters'),
  stickers: () => req('/api/edit/stickers'),
  transitions: () => req('/api/edit/transitions'),
  probe: (id: string) => req(`/api/edit/probe/${id}`),
  applyEdit: (body: any) => req('/api/edit/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  applyEditAsync: (body: any) => req('/api/edit/apply_async', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  concat: (ids: string[]) => req('/api/edit/concat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ids) }),
  extractAudio: (id: string) => req(`/api/edit/audio?media_id=${id}`, { method: 'POST' }),
  makeGif: (id: string, p: any) => req(`/api/edit/gif?media_id=${id}&start=${p.start || 0}&duration=${p.duration || 3}&fps=${p.fps || 12}&width=${p.width || 480}`, { method: 'POST' }),

  subtitles: (body: any) => req('/api/ai/subtitles', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  remove: (body: any) => req('/api/ai/remove', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  autoclip: (body: any) => req('/api/ai/autoclip', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  t2v: (body: any) => req('/api/ai/t2v', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  job: (id: string) => req(`/api/ai/jobs/${id}`),

  listKeys: () => req('/api/keys'),
  createKey: (name: string) => req('/api/keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) }),
  deleteKey: (key: string) => req(`/api/keys/${encodeURIComponent(key)}`, { method: 'DELETE' })
}

export function fmtDuration(sec: number): string {
  if (!isFinite(sec) || sec <= 0) return '0:00'
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60)
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}
export function fmtSize(bytes: number): string {
  if (!bytes) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB']; let i = 0
  while (bytes >= 1024 && i < u.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(i ? 1 : 0)} ${u[i]}`
}

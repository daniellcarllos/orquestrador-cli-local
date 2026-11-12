import type { Execucao, Inventario, Plano } from './types'

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: { Accept: 'application/json' } })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error((data as { error?: string }).error ?? `HTTP ${r.status}`)
  return data as T
}

export const api = {
  historico: () => get<{ entries: Execucao[] }>('/api/history').then((d) => d.entries),
  inventario: (probe = true) => get<Inventario>(`/api/doctor?probe=${probe ? 1 : 0}`),
  politicas: () => get<{ policies: string[] }>('/api/policies').then((d) => d.policies),
  plano: (task: string, policy?: string) => {
    const q = new URLSearchParams({ task })
    if (policy) q.set('policy', policy)
    return get<Plano>(`/api/plan?${q}`)
  },
}

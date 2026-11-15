import type { Catalogo, Execucao, Inventario, Plano } from './types'

// O token vem no fragmento da URL impressa pelo `serve` (#token=...), que não é enviado ao servidor
// nem fica em logs. Guardado só nesta aba (sessionStorage) e removido da barra de endereço.
const CHAVE = 'orquestrador-token'
function lerToken(): string {
  const m = window.location.hash.match(/token=([A-Za-z0-9_-]+)/)
  if (m) {
    sessionStorage.setItem(CHAVE, m[1])
    history.replaceState(null, '', window.location.pathname + window.location.search)
  }
  return sessionStorage.getItem(CHAVE) ?? ''
}
const TOKEN = lerToken()
export const temToken = () => !!TOKEN

async function chamar<T>(url: string, metodo = 'GET', corpo?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: metodo,
    headers: { Accept: 'application/json', 'X-Painel-Token': TOKEN, ...(corpo !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error((data as { error?: string }).error ?? `HTTP ${r.status}`)
  return data as T
}

export interface InfoRepo {
  caminho: string
  git: boolean
  raiz?: string
  na_raiz?: boolean
  branch?: string | null
  branches?: string[]
  limpo?: boolean
  alteracoes?: number
  ultimo_commit?: string
}

export interface Ambiente {
  agno: boolean
  max_simultaneas: number
  politicas: string[]
  acoes: string[]
}

export type Fluxo = 'revisar' | 'analisar' | 'desenvolver' | 'equipe' | 'cli'

export interface PedidoAcao {
  acao: string
  params?: Record<string, string>
  aprovada?: boolean
}

export interface Pedido {
  fluxo: Fluxo
  repositorio: string
  texto?: string
  base?: string
  head?: string
  diff_arquivo?: string
  mcp?: { prompt_id?: string; projeto?: string; grupo?: string }
  max_areas?: number
  teste?: string
  max_subtarefas?: number
  modo?: string
  agente?: string
  politica?: string
  timeout?: number
  config?: { simulado?: boolean; teto_usd?: number | string; teto_tokens?: number | string; teto_dia_usd?: number | string; nivel_forcado?: string }
  acoes?: PedidoAcao[]
}

export interface PlanoApi {
  comando: string
  simulado?: boolean
  teto_usd?: number
  teto_tokens?: number
  papeis?: Record<string, { nivel: string; provedor?: string; modelo?: string; erro?: string }>
  acoes?: string[]
  // modo CLI
  agent?: string
  model?: string | null
  complexity?: string
  risk?: string
  rationale?: string
}

export interface Job {
  id: string
  fluxo: Fluxo
  titulo: string
  started_at: string
  status: 'executando' | 'ok' | 'interrompido' | 'erro' | 'cancelado'
  execucao: string | null
  codigo: number | null
  duracao_ms: number
  log: string[]
  saida: string
}

export interface Resultado {
  meta: Execucao & { tarefa?: string; acoes?: { acao: string; status: string; detalhe: string }[]; modelos_sem_preco?: string[] }
  markdown: string
  estruturado: unknown
  propostas: { nome: string; caminho: string; base_commit: string; patch_sha256: string; bytes: number }[]
  pasta: string
}

export const api = {
  historico: () => chamar<{ entries: Execucao[] }>('/api/history').then((d) => d.entries),
  inventario: (probe = true) => chamar<Inventario>(`/api/doctor?probe=${probe ? 1 : 0}`),
  catalogo: () => chamar<Catalogo>('/api/catalogo'),
  salvarCatalogo: (c: unknown) => chamar<Catalogo>('/api/catalogo', 'PUT', c),
  restaurarCatalogo: () => chamar<Catalogo>('/api/catalogo', 'DELETE'),
  ambiente: () => chamar<Ambiente>('/api/ambiente'),
  politicas: () => chamar<{ policies: string[] }>('/api/policies').then((d) => d.policies),
  plano: (task: string, policy?: string) => {
    const q = new URLSearchParams({ task })
    if (policy) q.set('policy', policy)
    return chamar<Plano>(`/api/plan?${q}`)
  },
  repositorio: (caminho: string) => chamar<InfoRepo>(`/api/repositorio?${new URLSearchParams({ caminho })}`),
  favoritos: () => chamar<{ favoritos: string[] }>('/api/repositorios').then((d) => d.favoritos),
  salvarFavoritos: (favoritos: string[]) => chamar<{ favoritos: string[] }>('/api/repositorios', 'PUT', { favoritos }).then((d) => d.favoritos),
  planoExecucao: (p: Pedido) => chamar<PlanoApi>('/api/plano', 'POST', p),
  executar: (p: Pedido) => chamar<Job>('/api/execucoes', 'POST', p),
  execucoes: () => chamar<{ execucoes: Job[]; ativas: number }>('/api/execucoes'),
  cancelar: (id: string) => chamar<Job>(`/api/execucoes/${id}/cancelar`, 'POST', {}),
  resultado: (execucao: string) => chamar<Resultado>(`/api/resultados/${execucao}`),
  acao: (execucao: string, acao: PedidoAcao) =>
    chamar<{ ok: boolean; acoes?: { acao: string; status: string; detalhe: string }[]; saida?: string }>(
      `/api/resultados/${execucao}/acao`, 'POST', { acao, confirmado: true }),
  aplicar: (execucao: string, proposta: string, sha256: string, repositorio: string) =>
    chamar<{ ok: boolean; saida: string }>(`/api/resultados/${execucao}/aplicar`, 'POST', { proposta, sha256, repositorio, confirmado: true }),
}

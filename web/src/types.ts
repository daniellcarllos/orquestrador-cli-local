export type Agente = 'codex' | 'claude' | 'gemini' | 'api'

export interface EtapaExec {
  papel: string
  nivel: 'leve' | 'medio' | 'forte'
  provedor: string
  modelo: string
  status: string
  tokens_entrada: number
  tokens_saida: number
  custo_usd: number | null
  duracao_ms: number
  rodada: number
}

export interface Execucao {
  id: string
  action?: string
  modo?: 'api'
  status?: string
  started_at?: string
  agent: Agente
  policy_version: string
  model: string | null
  usage: unknown
  duration_ms: number
  exit_code: number | null
  timed_out: boolean
  truncated: boolean
  custo_usd?: number | null
  tokens?: number | null
  etapas?: EtapaExec[]
}

export interface Capacidade {
  available: boolean
  version?: string | null
  model_flag?: boolean | null
  sandbox_flag?: boolean | null
}

export interface Inventario {
  agents: Record<'codex' | 'claude' | 'gemini', Capacidade>
  probed: boolean
}

export interface Catalogo {
  versao: string | null
  niveis: Record<string, { provedor: string; modelo: string }>
  provedores: Record<string, boolean>
}

export interface Plano {
  agent: Agente
  complexity: string
  risk: 'baixo' | 'alto'
  policy_version: string
  rationale: string
  scope: string
  model: string | null
  task_type: string
  routing_mode: string
  usage: string
}

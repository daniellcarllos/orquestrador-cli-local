export type Agente = 'codex' | 'claude' | 'gemini'

export interface Execucao {
  id: string
  action?: 'run' | 'prepare'
  started_at?: string
  agent: Agente
  policy_version: string
  model: string | null
  usage: unknown
  duration_ms: number
  exit_code: number | null
  timed_out: boolean
  truncated: boolean
}

export interface Capacidade {
  available: boolean
  version?: string | null
  help_available?: boolean
  model_flag?: boolean | null
  json_flag?: boolean | null
  sandbox_flag?: boolean | null
  session_flag?: boolean | null
}

export interface Inventario {
  agents: Record<Agente, Capacidade>
  probed: boolean
}

export interface Plano {
  agent: Agente
  complexity: 'simples' | 'média' | 'alta'
  risk: 'baixo' | 'alto'
  policy_version: string
  rationale: string
  scope: string
  model: string | null
  task_type: string
  routing_mode: string
  usage: string
}

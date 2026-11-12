import type { Agente, Execucao } from '../types'

export const JANELA_ATIVO_MS = 10 * 60 * 1000

export interface Estatistica {
  total: number
  ok: number
  falhas: number
  duracaoMediaMs: number
  ultima: Execucao | null
  modeloFrequente: string | null
  ativo: boolean
}

export function sucesso(e: Execucao): boolean {
  return !e.timed_out && e.exit_code === 0
}

export function quando(e: Execucao): Date | null {
  return e.started_at ? new Date(e.started_at) : null
}

export function calcular(execucoes: Execucao[], agora = Date.now()): Estatistica {
  const total = execucoes.length
  const ok = execucoes.filter(sucesso).length
  const duracaoMediaMs = total ? Math.round(execucoes.reduce((s, e) => s + (e.duration_ms || 0), 0) / total) : 0
  const ultima = execucoes[0] ?? null
  const contagem = new Map<string, number>()
  for (const e of execucoes) if (e.model) contagem.set(e.model, (contagem.get(e.model) ?? 0) + 1)
  const modeloFrequente = [...contagem.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null
  const data = ultima ? quando(ultima) : null
  const ativo = !!data && agora - data.getTime() < JANELA_ATIVO_MS
  return { total, ok, falhas: total - ok, duracaoMediaMs, ultima, modeloFrequente, ativo }
}

export function porAgente(execucoes: Execucao[], agente: Agente): Execucao[] {
  return execucoes.filter((e) => e.agent === agente && (e.action ?? 'run') === 'run')
}

export function preparacoes(execucoes: Execucao[]): Execucao[] {
  return execucoes.filter((e) => e.action === 'prepare')
}

export function formatarDuracao(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`
}

export function formatarData(e: Execucao): string {
  const d = quando(e)
  if (!d) return 'sem data'
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function relativo(e: Execucao, agora = Date.now()): string {
  const d = quando(e)
  if (!d) return 'sem data'
  const s = Math.max(0, Math.round((agora - d.getTime()) / 1000))
  if (s < 60) return `há ${s} s`
  if (s < 3600) return `há ${Math.floor(s / 60)} min`
  if (s < 86_400) return `há ${Math.floor(s / 3600)} h`
  return `há ${Math.floor(s / 86_400)} d`
}

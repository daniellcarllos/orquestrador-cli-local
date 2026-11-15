import type { EtapaExec, Execucao } from '../types'
import { postoDaEtapa, type Papel } from './setores'

export const JANELA_ATIVO_MS = 10 * 60 * 1000

export interface Estatistica {
  total: number
  ok: number
  falhas: number
  duracaoMediaMs: number
  tokens: number
  custoUsd: number
  semPreco: boolean
  ultimaEm: string | null
  modeloFrequente: string | null
  ativo: boolean
}

const VAZIA: Estatistica = {
  total: 0, ok: 0, falhas: 0, duracaoMediaMs: 0, tokens: 0, custoUsd: 0, semPreco: false,
  ultimaEm: null, modeloFrequente: null, ativo: false,
}

export function sucesso(e: Execucao): boolean {
  if (e.modo === 'api') return e.status === 'ok'
  return !e.timed_out && e.exit_code === 0
}

export function quando(iso?: string | null): Date | null {
  return iso ? new Date(iso) : null
}

function maisFrequente(valores: (string | null | undefined)[]): string | null {
  const c = new Map<string, number>()
  for (const v of valores) if (v) c.set(v, (c.get(v) ?? 0) + 1)
  return [...c.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null
}

function ativo(iso: string | null, agora: number): boolean {
  const d = quando(iso)
  return !!d && agora - d.getTime() < JANELA_ATIVO_MS
}

/** Estatística de um posto da equipe de API, somando as etapas que caem nele. */
export function porPosto(execucoes: Execucao[], posto: Papel, agora = Date.now()): Estatistica {
  const etapas: { e: EtapaExec; em: string | null }[] = []
  for (const ex of execucoes) {
    if (ex.modo !== 'api') continue
    for (const e of ex.etapas ?? []) if (postoDaEtapa(e.papel) === posto) etapas.push({ e, em: ex.started_at ?? null })
  }
  if (!etapas.length) return VAZIA
  const ok = etapas.filter(({ e }) => e.status === 'ok').length
  const ultimaEm = etapas.map((x) => x.em).filter(Boolean).sort().at(-1) ?? null
  return {
    total: etapas.length,
    ok,
    falhas: etapas.length - ok,
    duracaoMediaMs: Math.round(etapas.reduce((s, { e }) => s + e.duracao_ms, 0) / etapas.length),
    tokens: etapas.reduce((s, { e }) => s + e.tokens_entrada + e.tokens_saida, 0),
    custoUsd: etapas.reduce((s, { e }) => s + (e.custo_usd ?? 0), 0),
    semPreco: etapas.some(({ e }) => e.custo_usd === null),
    ultimaEm,
    modeloFrequente: maisFrequente(etapas.map(({ e }) => e.modelo)),
    ativo: ativo(ultimaEm, agora),
  }
}

/** Estatística de execuções inteiras (Arquivo: todas; Terminais: só modo CLI). */
export function porExecucoes(execucoes: Execucao[], agora = Date.now()): Estatistica {
  if (!execucoes.length) return VAZIA
  const ok = execucoes.filter(sucesso).length
  const ultimaEm = execucoes.map((e) => e.started_at ?? null).filter(Boolean).sort().at(-1) ?? null
  return {
    total: execucoes.length,
    ok,
    falhas: execucoes.length - ok,
    duracaoMediaMs: Math.round(execucoes.reduce((s, e) => s + (e.duration_ms || 0), 0) / execucoes.length),
    tokens: execucoes.reduce((s, e) => s + (e.tokens ?? 0), 0),
    custoUsd: execucoes.reduce((s, e) => s + (e.custo_usd ?? 0), 0),
    semPreco: execucoes.some((e) => e.modo === 'api' && (e.custo_usd == null || (e.etapas ?? []).some((x) => x.custo_usd === null))),
    ultimaEm,
    modeloFrequente: maisFrequente(execucoes.flatMap((e) => (e.etapas?.length ? e.etapas.map((x) => x.modelo) : [e.model]))),
    ativo: ativo(ultimaEm, agora),
  }
}

export function formatarDuracao(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`
}

export function formatarCusto(usd: number, semPreco = false): string {
  if (!usd && semPreco) return 'sem preço'
  return `US$ ${usd < 0.01 && usd > 0 ? usd.toFixed(4) : usd.toFixed(2)}${semPreco ? '*' : ''}`
}

export function formatarTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)} mil` : String(n)
}

export function formatarData(iso?: string | null): string {
  const d = quando(iso)
  if (!d) return 'sem data'
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function relativo(iso: string | null, agora = Date.now()): string {
  const d = quando(iso)
  if (!d) return 'nunca'
  const s = Math.max(0, Math.round((agora - d.getTime()) / 1000))
  if (s < 60) return `há ${s} s`
  if (s < 3600) return `há ${Math.floor(s / 60)} min`
  if (s < 86_400) return `há ${Math.floor(s / 3600)} h`
  return `há ${Math.floor(s / 86_400)} d`
}

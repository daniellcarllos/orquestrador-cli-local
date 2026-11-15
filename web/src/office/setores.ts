import type { Sprite } from '../pixel/palette'
import * as P from '../pixel/personagens'
import * as M from '../pixel/furniture'

export type Papel = 'portaria' | 'coordenador' | 'triagem' | 'planejador' | 'analista' | 'revisor' | 'implementador' | 'arquivo' | 'terminais'

export interface Setor {
  id: Papel
  nome: string
  personagem: P.Personagem
  sprite: Sprite[]
  mobilia: Sprite[]
  cor: string
  nivel?: 'leve' | 'medio' | 'forte' // nível padrão do papel na orquestração por API
  descricao: string
}

const setor = (s: Omit<Setor, 'sprite'>): Setor => ({ ...s, sprite: P.quadros(s.personagem) })

export const SETORES: Setor[] = [
  setor({
    id: 'portaria', nome: 'Portaria', personagem: P.GUARDA, mobilia: [M.CATRACA, M.PLANTA], cor: '#2e6fd9',
    descricao: 'Nada passa sem aprovação: --approve libera chamadas e gasto; ações externas exigem SIM ou --aprovar-acoes.',
  }),
  setor({
    id: 'coordenador', nome: 'Coordenação', personagem: P.COORDENADORA, mobilia: [M.ESCRIVANINHA, M.QUADRO], cor: '#9e9e9e',
    nivel: 'forte',
    descricao: 'Modelo forte. Consolida o trabalho dos outros postos, resolve contradições e decide. Também lidera o modo equipe.',
  }),
  setor({
    id: 'triagem', nome: 'Triagem', personagem: P.RECEPCIONISTA, mobilia: [M.BANDEJA, M.MESA], cor: '#f2c14e',
    nivel: 'leve',
    descricao: 'Modelo leve. Classifica tipo, complexidade e risco, e escolhe as áreas. Risco alto escala a revisão de segurança.',
  }),
  setor({
    id: 'planejador', nome: 'Planejamento', personagem: P.ARQUITETA, mobilia: [M.QUADRO, M.MESA], cor: '#4dd0e1',
    nivel: 'forte',
    descricao: 'Modelo forte. Divide o objetivo em subtarefas independentes, cada uma com seus arquivos e critérios de aceite.',
  }),
  setor({
    id: 'analista', nome: 'Análise', personagem: P.CARTOGRAFA, mobilia: [M.MAPA, M.ESTANTE], cor: '#2bb3a0',
    nivel: 'medio',
    descricao: 'Modelo médio. Mapeia cada área do código em paralelo: responsabilidade, dependências e riscos.',
  }),
  setor({
    id: 'revisor', nome: 'Revisão', personagem: P.INSPETORA, mobilia: [M.LUPA, M.MESA, M.MONITOR], cor: '#4caf50',
    nivel: 'medio',
    descricao: 'Modelo médio, três em paralelo: segurança, bugs e qualidade. Cada achado cita arquivo e linha.',
  }),
  setor({
    id: 'implementador', nome: 'Oficina', personagem: P.ENGENHEIRO, mobilia: [M.BIGORNA, M.CAIXA_PATCH, M.RACK], cor: '#e8732a',
    nivel: 'medio',
    descricao: 'Modelo médio. Implementa cada subtarefa numa cópia isolada; o patch é testado e revisado antes de chegar a você.',
  }),
  setor({
    id: 'arquivo', nome: 'Arquivo', personagem: P.ARQUIVISTA, mobilia: [M.ARQUIVO, M.ARQUIVO], cor: '#a0713f',
    descricao: 'Histórico de execuções com tokens e custo por etapa. Guarda só metadados; respostas ficam na pasta privada de cada execução.',
  }),
  setor({
    id: 'terminais', nome: 'Sala dos terminais', personagem: P.OPERADORA, mobilia: [M.MESA, M.MONITOR, M.MONITOR], cor: '#7b3fa0',
    descricao: 'Modo CLI: Codex, Claude Code e Gemini CLI com a sessão de cada assinatura. Console de roteamento sem custo.',
  }),
]

/** Papel registrado numa etapa ("revisor:bugs", "membro:analista", "lider") → posto do escritório. */
export function postoDaEtapa(papel: string): Papel {
  const [base, sub] = papel.split(':')
  if (base === 'lider') return 'coordenador'
  if (base === 'membro' && sub) return postoDaEtapa(sub)
  const conhecidos: Papel[] = ['coordenador', 'triagem', 'planejador', 'analista', 'revisor', 'implementador']
  return (conhecidos as string[]).includes(base) ? (base as Papel) : 'coordenador'
}

export const SETOR: Record<Papel, Setor> = Object.fromEntries(SETORES.map((s) => [s.id, s])) as Record<Papel, Setor>

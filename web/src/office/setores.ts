import type { Sprite } from '../pixel/palette'
import * as H from '../pixel/heroes'
import * as M from '../pixel/furniture'
import type { Agente } from '../types'

export type Papel = 'portaria' | 'direcao' | 'arquivo' | 'agente' | 'oficina'

export interface Setor {
  id: string
  papel: Papel
  agente?: Agente
  nome: string
  heroi: string
  codinome: string
  sprite: Sprite[]
  mobilia: Sprite[]
  cor: string // cor de destaque do setor
  descricao: string
}

export const SETORES: Setor[] = [
  {
    id: 'portaria',
    papel: 'portaria',
    nome: 'Portaria',
    heroi: 'Capitão América',
    codinome: 'Aprovação',
    sprite: H.CAPITAO_AMERICA,
    mobilia: [M.ESCUDO, M.PLANTA],
    cor: '#2e6fd9',
    descricao: 'Nada passa sem --approve. Cada execução ou leitura do MCP exige autorização explícita.',
  },
  {
    id: 'direcao',
    papel: 'direcao',
    nome: 'Direção',
    heroi: 'Nick Fury',
    codinome: 'Roteamento',
    sprite: H.NICK_FURY,
    mobilia: [M.ESCRIVANINHA_FURY],
    cor: '#9e9e9e',
    descricao: 'Classifica a tarefa (simples, média, alta) e escolhe o agente conforme a política.',
  },
  {
    id: 'arquivo',
    papel: 'arquivo',
    nome: 'Arquivo',
    heroi: 'Viúva Negra',
    codinome: 'Histórico',
    sprite: H.VIUVA_NEGRA,
    mobilia: [M.ARQUIVO, M.ARQUIVO],
    cor: '#e8732a',
    descricao: 'Guarda só metadados das execuções: id, data, agente, política, duração e status.',
  },
  {
    id: 'codex',
    papel: 'agente',
    agente: 'codex',
    nome: 'Setor Codex',
    heroi: 'Homem de Ferro',
    codinome: 'Codex CLI',
    sprite: H.HOMEM_DE_FERRO,
    mobilia: [M.MESA, M.MONITOR, M.RACK],
    cor: '#d7263d',
    descricao: 'Oficina de alta tecnologia. Executa em sandbox read-only; escreve só em cópia (workspace-write).',
  },
  {
    id: 'claude',
    papel: 'agente',
    agente: 'claude',
    nome: 'Setor Claude',
    heroi: 'Doutor Estranho',
    codinome: 'Claude Code',
    sprite: H.DOUTOR_ESTRANHO,
    mobilia: [M.MESA, M.MONITOR, M.ESTANTE, M.PORTAL],
    cor: '#7b3fa0',
    descricao: 'Biblioteca restrita: modo --restricted, sem ferramentas na análise; só arquivos na preparação.',
  },
  {
    id: 'gemini',
    papel: 'agente',
    agente: 'gemini',
    nome: 'Setor Gemini',
    heroi: 'Thor',
    codinome: 'Gemini CLI',
    sprite: H.THOR,
    mobilia: [M.MESA, M.MONITOR, M.MARTELO],
    cor: '#f2c14e',
    descricao: 'Modo plan (somente leitura). Ainda não participa da preparação de patches.',
  },
  {
    id: 'oficina',
    papel: 'oficina',
    nome: 'Oficina de patches',
    heroi: 'Hulk',
    codinome: 'prepare / apply',
    sprite: H.HULK,
    mobilia: [M.BIGORNA, M.CAIXA_PATCH],
    cor: '#4caf50',
    descricao: 'Patches nascem numa cópia temporária e só entram no repositório após revisão e hash conferido.',
  },
]

export const SETOR_POR_AGENTE: Record<Agente, Setor> = Object.fromEntries(
  SETORES.filter((s) => s.agente).map((s) => [s.agente, s]),
) as Record<Agente, Setor>

import { useEffect, useState } from 'react'
import { Sprite } from '../pixel/Sprite'
import { MONITOR, MONITOR_ATIVO } from '../pixel/furniture'
import type { Setor } from './setores'
import { formatarCusto, formatarDuracao, formatarTokens, relativo, type Estatistica } from './estatisticas'

export type Situacao = 'trabalhando' | 'ocioso' | 'fora' | 'presente'

interface Props {
  setor: Setor
  situacao: Situacao
  estat?: Estatistica
  modelo?: string | null
  rodape?: string
  selecionado: boolean
  aoSelecionar: () => void
  children?: React.ReactNode
}

const ROTULO: Record<Situacao, string> = {
  trabalhando: 'TRABALHANDO',
  ocioso: 'OCIOSO',
  fora: 'FORA DO AR',
  presente: 'EM SERVIÇO',
}

export function Sala({ setor, situacao, estat, modelo, rodape, selecionado, aoSelecionar, children }: Props) {
  const [quadro, setQuadro] = useState(0)
  useEffect(() => {
    // pisca rápido quando trabalha; devagar quando ocioso
    const ritmo = situacao === 'trabalhando' ? 700 : 2200
    const t = setInterval(() => setQuadro((q) => (q + 1) % 2), ritmo)
    return () => clearInterval(t)
  }, [situacao])

  return (
    <section
      className={`sala sala-${situacao} ${selecionado ? 'sala-selecionada' : ''}`}
      style={{ ['--cor' as string]: setor.cor }}
      onClick={(e) => { e.stopPropagation(); aoSelecionar() }}
      aria-label={setor.nome}
    >
      <header className="sala-cabecalho">
        <span className="sala-nome">{setor.nome}</span>
        <span className={`placa placa-${situacao}`}>{ROTULO[situacao]}</span>
      </header>

      <div className="sala-piso">
        <div className="sala-parede" />
        <div className="sala-mobilia">
          {setor.mobilia.map((m, i) => (
            <Sprite key={i} grade={m === MONITOR && situacao === 'trabalhando' ? MONITOR_ATIVO : m} escala={3} className="movel" />
          ))}
        </div>
        <div className={`personagem ${situacao === 'fora' ? 'personagem-ausente' : ''}`}>
          <Sprite grade={setor.sprite[situacao === 'fora' ? 0 : quadro]} escala={4} titulo={setor.personagem.nome} />
          <span className="cracha">{setor.personagem.nome}</span>
        </div>
      </div>

      <footer className="sala-rodape">
        {setor.nivel && (
          <div className="codinome">
            nível {setor.nivel}{modelo ? ` · ${modelo}` : ''}
          </div>
        )}
        {rodape && <div className="codinome">{rodape}</div>}
        {estat && (
          <dl className="placar">
            <div><dt>Chamadas</dt><dd>{estat.total}</dd></div>
            <div><dt>OK</dt><dd className="ok">{estat.ok}</dd></div>
            <div><dt>Falhas</dt><dd className={estat.falhas ? 'erro' : ''}>{estat.falhas}</dd></div>
            <div><dt>Tokens</dt><dd>{formatarTokens(estat.tokens)}</dd></div>
            <div><dt>Custo</dt><dd>{estat.total ? formatarCusto(estat.custoUsd, estat.semPreco) : '–'}</dd></div>
            <div><dt>Média</dt><dd>{estat.total ? formatarDuracao(estat.duracaoMediaMs) : '–'}</dd></div>
            <div><dt>Última</dt><dd>{relativo(estat.ultimaEm)}</dd></div>
            <div className="largo"><dt>Modelo mais usado</dt><dd>{estat.modeloFrequente ?? '–'}</dd></div>
          </dl>
        )}
        {children}
      </footer>
    </section>
  )
}

import { useEffect, useState } from 'react'
import { Sprite } from '../pixel/Sprite'
import { MONITOR, MONITOR_ATIVO } from '../pixel/furniture'
import type { Setor } from './setores'
import type { Capacidade } from '../types'
import { formatarDuracao, relativo, type Estatistica } from './estatisticas'

export type Situacao = 'trabalhando' | 'ocioso' | 'ausente' | 'presente'

interface Props {
  setor: Setor
  situacao: Situacao
  estat?: Estatistica
  capacidade?: Capacidade
  selecionado: boolean
  aoSelecionar: () => void
  children?: React.ReactNode
}

const ROTULO: Record<Situacao, string> = {
  trabalhando: 'TRABALHANDO',
  ocioso: 'OCIOSO',
  ausente: 'AUSENTE',
  presente: 'EM SERVIÇO',
}

export function Sala({ setor, situacao, estat, capacidade, selecionado, aoSelecionar, children }: Props) {
  const [quadro, setQuadro] = useState(0)
  useEffect(() => {
    const ritmo = situacao === 'trabalhando' ? 350 : 900
    const t = setInterval(() => setQuadro((q) => (q + 1) % 2), ritmo)
    return () => clearInterval(t)
  }, [situacao])

  const sprite = setor.sprite[situacao === 'ausente' ? 0 : quadro]

  return (
    <section
      className={`sala sala-${situacao} ${selecionado ? 'sala-selecionada' : ''}`}
      style={{ ['--cor' as string]: setor.cor }}
      onClick={aoSelecionar}
      aria-label={setor.nome}
    >
      <header className="sala-cabecalho">
        <span className="sala-nome">{setor.nome}</span>
        <span className={`placa placa-${situacao}`}>{ROTULO[situacao]}</span>
      </header>

      <div className="sala-piso">
        <div className="sala-parede" />
        <div className="sala-mobilia">
          {setor.mobilia.map((m, i) => {
            const grade = m === MONITOR && situacao === 'trabalhando' ? MONITOR_ATIVO : m
            return <Sprite key={i} grade={grade} escala={3} className="movel" />
          })}
        </div>
        <div className={`personagem ${situacao === 'ausente' ? 'personagem-ausente' : ''}`}>
          <Sprite grade={sprite} escala={4} titulo={setor.heroi} />
          <span className="cracha">{setor.heroi}</span>
        </div>
      </div>

      <footer className="sala-rodape">
        <div className="codinome">{setor.codinome}</div>
        {estat && (
          <dl className="placar">
            <div><dt>Execuções</dt><dd>{estat.total}</dd></div>
            <div><dt>OK</dt><dd className="ok">{estat.ok}</dd></div>
            <div><dt>Falhas</dt><dd className={estat.falhas ? 'erro' : ''}>{estat.falhas}</dd></div>
            <div><dt>Média</dt><dd>{estat.total ? formatarDuracao(estat.duracaoMediaMs) : '–'}</dd></div>
            <div><dt>Última</dt><dd>{estat.ultima ? relativo(estat.ultima) : 'nunca'}</dd></div>
            <div><dt>Modelo</dt><dd>{estat.modeloFrequente ?? 'padrão'}</dd></div>
          </dl>
        )}
        {capacidade && (
          <div className="capacidade">
            {capacidade.available ? `v${capacidade.version ?? '?'}` : 'não instalado'}
            {capacidade.available && capacidade.model_flag && ' · --model'}
            {capacidade.available && capacidade.sandbox_flag && ' · sandbox'}
          </div>
        )}
        {children}
      </footer>
    </section>
  )
}

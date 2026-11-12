import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { Execucao, Inventario } from './types'
import { SETORES, type Setor } from './office/setores'
import { Sala, type Situacao } from './office/Sala'
import { calcular, porAgente, preparacoes, sucesso } from './office/estatisticas'
import { Direcao } from './panels/Direcao'
import { Portaria } from './panels/Portaria'
import { Historico } from './panels/Historico'

const INTERVALO_HISTORICO = 5000
const INTERVALO_INVENTARIO = 60_000

export default function App() {
  const [execucoes, setExecucoes] = useState<Execucao[]>([])
  const [inventario, setInventario] = useState<Inventario | null>(null)
  const [politicas, setPoliticas] = useState<string[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [selecionado, setSelecionado] = useState<string | null>(null)
  const [agora, setAgora] = useState(Date.now())

  useEffect(() => {
    const carregar = () =>
      api.historico().then((h) => { setExecucoes(h); setErro(null); setAgora(Date.now()) }).catch((e: Error) => setErro(e.message))
    carregar()
    const t = setInterval(carregar, INTERVALO_HISTORICO)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const carregar = () => api.inventario(true).then(setInventario).catch(() => undefined)
    carregar()
    api.politicas().then(setPoliticas).catch(() => undefined)
    const t = setInterval(carregar, INTERVALO_INVENTARIO)
    return () => clearInterval(t)
  }, [])

  const estatPorSetor = useMemo(() => {
    const m = new Map<string, ReturnType<typeof calcular>>()
    for (const s of SETORES) {
      if (s.agente) m.set(s.id, calcular(porAgente(execucoes, s.agente), agora))
      if (s.papel === 'oficina') m.set(s.id, calcular(preparacoes(execucoes), agora))
      if (s.papel === 'arquivo') m.set(s.id, calcular(execucoes, agora))
    }
    return m
  }, [execucoes, agora])

  const situacao = (s: Setor): Situacao => {
    const estat = estatPorSetor.get(s.id)
    if (s.agente) {
      const cap = inventario?.agents[s.agente]
      if (cap && !cap.available) return 'ausente'
      return estat?.ativo ? 'trabalhando' : 'ocioso'
    }
    if (s.papel === 'oficina' || s.papel === 'arquivo') return estat?.ativo ? 'trabalhando' : 'presente'
    return 'presente'
  }

  const total = execucoes.length
  const falhas = execucoes.filter((e) => !sucesso(e)).length
  const setorSelecionado = SETORES.find((s) => s.id === selecionado)
  const filtroAgente = setorSelecionado?.agente ?? null

  return (
    <div className="escritorio">
      <header className="topo">
        <div className="titulo">
          <h1>ESCRITÓRIO DO ORQUESTRADOR</h1>
          <span className="subtitulo">modo single · somente leitura · 127.0.0.1</span>
        </div>
        <div className="totais">
          <span>execuções <b>{total}</b></span>
          <span>falhas <b className={falhas ? 'erro' : ''}>{falhas}</b></span>
          <span>CLIs <b>{inventario ? Object.values(inventario.agents).filter((a) => a.available).length : '…'}/3</b></span>
          <span className={erro ? 'erro' : 'ok'}>{erro ? `API: ${erro}` : 'API ok'}</span>
        </div>
      </header>

      <main className="andar" onClick={() => setSelecionado(null)}>
        {SETORES.map((s) => (
          <Sala
            key={s.id}
            setor={s}
            situacao={situacao(s)}
            estat={estatPorSetor.get(s.id)}
            capacidade={s.agente ? inventario?.agents[s.agente] : undefined}
            selecionado={selecionado === s.id}
            aoSelecionar={() => setSelecionado((atual) => (atual === s.id ? null : s.id))}
          >
            {s.papel === 'portaria' && <Portaria execucoes={execucoes} />}
            {s.papel === 'direcao' && <Direcao politicas={politicas} />}
            {selecionado === s.id && <p className="descricao">{s.descricao}</p>}
          </Sala>
        ))}
      </main>

      <Historico execucoes={execucoes} filtroAgente={filtroAgente} />

      <footer className="rodape">
        Dados de <code>~/.local/state/orquestrador-cli-local/history.jsonl</code>. O painel não executa agentes: use a CLI com <code>--approve</code>.
      </footer>
    </div>
  )
}

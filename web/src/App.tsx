import { useEffect, useState } from 'react'
import { api, temToken, type Ambiente } from './api'
import type { Execucao } from './types'
import { Escritorio } from './telas/Escritorio'
import { NovaTarefa } from './telas/NovaTarefa'
import { Execucoes } from './telas/Execucoes'
import { Configuracoes } from './telas/Configuracoes'
import { ComoUsar } from './telas/ComoUsar'

type Aba = 'escritorio' | 'nova' | 'execucoes' | 'configuracoes' | 'ajuda'
const ABAS: { id: Aba; nome: string }[] = [
  { id: 'nova', nome: 'Nova tarefa' },
  { id: 'execucoes', nome: 'Execuções' },
  { id: 'escritorio', nome: 'Escritório' },
  { id: 'configuracoes', nome: 'Configurações' },
  { id: 'ajuda', nome: 'Como usar' },
]

export default function App() {
  const [aba, setAba] = useState<Aba>(() => {
    const daUrl = new URLSearchParams(window.location.search).get('aba') as Aba | null
    return (daUrl && ABAS.some((a) => a.id === daUrl) ? daUrl : (localStorage.getItem('orquestrador-aba') as Aba)) || 'nova'
  })
  const [historico, setHistorico] = useState<Execucao[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const [ambiente, setAmbiente] = useState<Ambiente | null>(null)
  const [jobInicial, setJobInicial] = useState<string | null>(null)

  useEffect(() => { localStorage.setItem('orquestrador-aba', aba) }, [aba])
  useEffect(() => {
    if (!temToken()) return
    const carregar = () => api.historico().then((h) => { setHistorico(h); setErro(null) }).catch((e: Error) => setErro(e.message))
    carregar()
    api.ambiente().then(setAmbiente).catch(() => undefined)
    const t = setInterval(carregar, 4000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="escritorio">
      <header className="topo">
        <div className="titulo">
          <h1>ORQUESTRADOR DE AGENTES</h1>
          <span className="subtitulo">equipe por API (Agno) + terminais por assinatura · 127.0.0.1</span>
        </div>
        <nav className="abas">
          {ABAS.map((a) => (
            <button key={a.id} className={aba === a.id ? 'ativo' : ''} onClick={() => setAba(a.id)}>{a.nome}</button>
          ))}
        </nav>
      </header>

      {!temToken() ? (
        <section className="cartao">
          <h2>Painel sem token</h2>
          <p>Abra o endereço completo exibido no terminal pelo comando abaixo (ele termina com <code>#token=...</code>).</p>
          <pre className="log">.venv/bin/python -m orchestrator serve</pre>
        </section>
      ) : (
        <>
          {aba === 'nova' && <NovaTarefa ambiente={ambiente} aoIniciar={(id) => { setJobInicial(id); setAba('execucoes') }} />}
          {aba === 'execucoes' && <Execucoes historico={historico} selecionadoInicial={jobInicial} />}
          {aba === 'escritorio' && <Escritorio execucoes={historico} erro={erro} aoAbrirExecucoes={() => setAba('execucoes')} />}
          {aba === 'configuracoes' && <Configuracoes />}
          {aba === 'ajuda' && <ComoUsar />}
        </>
      )}

      <footer className="rodape">
        Dados em <code>~/.local/state/orquestrador-cli-local/</code>. Nada executa sem a sua confirmação. Personagens originais criados para este projeto.
      </footer>
    </div>
  )
}

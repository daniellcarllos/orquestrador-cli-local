import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { Catalogo, Execucao, Inventario } from '../types'
import { SETORES, type Papel, type Setor } from '../office/setores'
import { Sala, type Situacao } from '../office/Sala'
import { formatarCusto, porExecucoes, porPosto, sucesso, type Estatistica } from '../office/estatisticas'
import { Direcao } from '../panels/Direcao'
import { Portaria } from '../panels/Portaria'
import { Historico } from '../panels/Historico'

const INTERVALO_INVENTARIO = 60_000
const POSTOS_API: Papel[] = ['coordenador', 'triagem', 'planejador', 'analista', 'revisor', 'implementador']

export function Escritorio({ execucoes, erro, aoAbrirExecucoes }: { execucoes: Execucao[]; erro: string | null; aoAbrirExecucoes: () => void }) {
  const [inventario, setInventario] = useState<Inventario | null>(null)
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [politicas, setPoliticas] = useState<string[]>([])
  const [selecionado, setSelecionado] = useState<Papel | null>(null)
  const [agora, setAgora] = useState(Date.now())

  useEffect(() => { setAgora(Date.now()) }, [execucoes])

  useEffect(() => {
    const carregar = () => {
      api.inventario(true).then(setInventario).catch(() => undefined)
      api.catalogo().then(setCatalogo).catch(() => undefined)
    }
    carregar()
    api.politicas().then(setPoliticas).catch(() => undefined)
    const t = setInterval(carregar, INTERVALO_INVENTARIO)
    return () => clearInterval(t)
  }, [])

  const cli = useMemo(() => execucoes.filter((e) => e.modo !== 'api'), [execucoes])
  const estat = useMemo(() => {
    const m = new Map<Papel, Estatistica>()
    for (const p of POSTOS_API) m.set(p, porPosto(execucoes, p, agora))
    m.set('arquivo', porExecucoes(execucoes, agora))
    m.set('terminais', porExecucoes(cli, agora))
    return m
  }, [execucoes, cli, agora])

  const algumProvedor = catalogo ? Object.values(catalogo.provedores).some(Boolean) : false
  const modeloDo = (s: Setor) => (s.nivel && catalogo?.niveis[s.nivel]?.modelo) || null

  const situacao = (s: Setor): Situacao => {
    const e = estat.get(s.id)
    if (s.nivel) {
      if (catalogo && !algumProvedor && !e?.total) return 'fora'
      return e?.ativo ? 'trabalhando' : 'ocioso'
    }
    if (s.id === 'terminais') {
      const algumaCli = inventario ? Object.values(inventario.agents).some((a) => a.available) : true
      if (!algumaCli) return 'fora'
      return e?.ativo ? 'trabalhando' : 'ocioso'
    }
    if (s.id === 'arquivo') return e?.ativo ? 'trabalhando' : 'presente'
    return 'presente'
  }

  const rodape = (s: Setor): string | undefined => {
    if (s.id === 'terminais' && inventario) {
      return Object.entries(inventario.agents)
        .map(([k, v]) => `${k} ${v.available ? (v.version ? `v${v.version}` : 'ok') : 'ausente'}`).join(' · ')
    }
    if (s.nivel && catalogo && !algumProvedor) return 'sem chave de API: use --simulado'
    return undefined
  }

  const custoTotal = execucoes.reduce((t, e) => t + (e.custo_usd ?? 0), 0)
  const falhas = execucoes.filter((e) => !sucesso(e)).length
  const semPreco = execucoes.some((e) => e.etapas?.some((x) => x.custo_usd === null))

  return (
    <div className="tela" onClick={() => setSelecionado(null)}>
      <div className="faixa">
        <span>execuções <b>{execucoes.length}</b></span>
        <span>falhas <b className={falhas ? 'erro' : ''}>{falhas}</b></span>
        <span>custo <b>{formatarCusto(custoTotal, semPreco)}</b></span>
        <span>provedores <b>{catalogo ? Object.entries(catalogo.provedores).filter(([, v]) => v).map(([k]) => k).join(', ') || 'nenhum' : '...'}</b></span>
        <span className={erro ? 'erro' : 'ok'}>{erro ? `API: ${erro}` : 'API ok'}</span>
        <button className="botao secundario" onClick={(e) => { e.stopPropagation(); aoAbrirExecucoes() }}>ver execuções</button>
      </div>

      <main className="andar">
        {SETORES.map((s) => (
          <Sala
            key={s.id}
            setor={s}
            situacao={situacao(s)}
            estat={estat.get(s.id)}
            modelo={modeloDo(s)}
            rodape={rodape(s)}
            selecionado={selecionado === s.id}
            aoSelecionar={() => setSelecionado((atual) => (atual === s.id ? null : s.id))}
          >
            {s.id === 'portaria' && <Portaria execucoes={execucoes} />}
            {s.id === 'terminais' && <Direcao politicas={politicas} />}
            {selecionado === s.id && <p className="descricao">{s.descricao}</p>}
          </Sala>
        ))}
      </main>

      <Historico execucoes={execucoes} posto={selecionado} />

    </div>
  )
}

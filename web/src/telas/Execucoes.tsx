import { useEffect, useState } from 'react'
import { api, type Job, type PedidoAcao, type Resultado } from '../api'
import type { Execucao } from '../types'
import { Markdown } from '../Markdown'
import { SETOR, postoDaEtapa } from '../office/setores'
import { formatarCusto, formatarData, formatarDuracao, formatarTokens } from '../office/estatisticas'
import { Sprite } from '../pixel/Sprite'
import { lerPreferencias } from '../preferencias'

const ROTULO: Record<string, string> = {
  executando: 'EXECUTANDO', ok: 'PRONTA', interrompido: 'INTERROMPIDA', erro: 'ERRO', cancelado: 'CANCELADA',
}

interface Item { chave: string; job?: Job; execucao?: string; titulo: string; fluxo: string; quando?: string; status: string }

export function Execucoes({ historico, selecionadoInicial }: { historico: Execucao[]; selecionadoInicial: string | null }) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [selecionado, setSelecionado] = useState<string | null>(selecionadoInicial)

  useEffect(() => {
    const carregar = () => api.execucoes().then((d) => setJobs(d.execucoes)).catch(() => undefined)
    carregar()
    const t = setInterval(carregar, 1500)
    return () => clearInterval(t)
  }, [])
  useEffect(() => { if (selecionadoInicial) setSelecionado(selecionadoInicial) }, [selecionadoInicial])

  // execuções desta sessão (jobs) + histórico de execuções por API anteriores
  const vistos = new Set(jobs.map((j) => j.execucao).filter(Boolean))
  const itens: Item[] = [
    ...jobs.map((j) => ({ chave: j.id, job: j, execucao: j.execucao ?? undefined, titulo: j.titulo, fluxo: j.fluxo, quando: j.started_at, status: j.status })),
    ...historico.filter((e) => e.modo === 'api' && !vistos.has(e.id)).slice(0, 40)
      .map((e) => ({ chave: e.id, execucao: e.id, titulo: e.action ?? '', fluxo: e.action ?? '', quando: e.started_at, status: e.status ?? '' })),
  ]
  const atual = itens.find((i) => i.chave === selecionado) ?? itens[0]

  return (
    <div className="tela execucoes">
      <aside className="cartao lista-execucoes">
        <h2>Execuções</h2>
        {itens.length === 0 && <p className="vazio">Nenhuma execução ainda. Comece em Nova tarefa.</p>}
        <ul>
          {itens.map((i) => (
            <li key={i.chave} className={`${atual?.chave === i.chave ? 'ativo' : ''} status-${i.status}`} onClick={() => setSelecionado(i.chave)}>
              <span className={`placa placa-${i.status === 'executando' ? 'trabalhando' : i.status === 'ok' ? 'presente' : 'fora'}`}>{ROTULO[i.status] ?? i.status.toUpperCase()}</span>
              <b>{i.fluxo}</b>
              <span className="miudo">{i.titulo}</span>
              <span className="miudo">{formatarData(i.quando)}</span>
            </li>
          ))}
        </ul>
      </aside>
      <section className="detalhe">{atual ? <Detalhe item={atual} /> : null}</section>
    </div>
  )
}

function Detalhe({ item }: { item: Item }) {
  const [res, setRes] = useState<Resultado | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const job = item.job
  const execucao = item.execucao

  useEffect(() => {
    setRes(null); setErro(null)
    if (!execucao) return
    let vivo = true
    const carregar = () => api.resultado(execucao).then((r) => vivo && setRes(r)).catch((e: Error) => vivo && setErro(e.message))
    carregar()
    const t = job?.status === 'executando' ? setInterval(carregar, 1500) : undefined
    return () => { vivo = false; if (t) clearInterval(t) }
  }, [execucao, job?.status])

  const etapas = res?.meta.etapas ?? []
  return (
    <>
      <div className="cartao">
        <div className="linha entre">
          <h2>{item.fluxo} {item.titulo && item.titulo !== item.fluxo ? `· ${item.titulo}` : ''}</h2>
          {job?.status === 'executando' && <button className="botao perigo" onClick={() => api.cancelar(job.id)}>Cancelar</button>}
        </div>
        <p className="miudo">
          {ROTULO[item.status] ?? item.status} · {formatarData(item.quando)}
          {job && ` · ${formatarDuracao(job.duracao_ms)}`}
          {res?.meta.custo_usd != null && ` · ${formatarCusto(res.meta.custo_usd, (res.meta.modelos_sem_preco ?? []).length > 0)}`}
          {res?.meta.tokens != null && ` · ${formatarTokens(res.meta.tokens)} tokens`}
        </p>
        {etapas.length > 0 && (
          <ol className="linha-tempo">
            {etapas.map((x, i) => {
              const s = SETOR[postoDaEtapa(x.papel)]
              return (
                <li key={i} style={{ ['--cor' as string]: s.cor }} className={x.status === 'ok' ? '' : x.status === 'pendente' ? 'etapa-andando' : 'etapa-falha'}>
                  <Sprite grade={s.sprite[0]} escala={2} titulo={s.personagem.nome} />
                  <div>
                    <b>{x.papel}</b>{x.rodada > 1 ? ` (rodada ${x.rodada})` : ''}
                    <div className="miudo">{x.nivel} · {x.modelo}</div>
                    <div className="miudo">{formatarTokens(x.tokens_entrada + x.tokens_saida)} tokens · {x.custo_usd == null ? 'sem preço' : formatarCusto(x.custo_usd)} · {formatarDuracao(x.duracao_ms)}</div>
                    <div className={x.status === 'ok' ? 'ok' : x.status === 'pendente' ? 'piscando' : 'erro'}>{x.status === 'pendente' ? 'trabalhando...' : x.status}</div>
                  </div>
                </li>
              )
            })}
          </ol>
        )}
        {job?.status === 'executando' && !etapas.length && <p className="piscando">preparando...</p>}
        {job && job.log.length > 0 && job.status !== 'ok' && (
          <details open={job.status !== 'executando'}><summary>Log</summary><pre className="log">{job.log.join('\n')}</pre></details>
        )}
        {erro && !job && <p className="erro">{erro}</p>}
      </div>

      {job?.fluxo === 'cli' && job.saida && (
        <div className="cartao"><h3>Resposta</h3><pre className="log">{job.saida}</pre></div>
      )}
      {res?.markdown && (
        <div className="cartao resultado"><Markdown texto={res.markdown} /><p className="miudo">Arquivos em {res.pasta}</p></div>
      )}
      {res && res.propostas.length > 0 && <Propostas res={res} />}
      {res && res.meta.status === 'ok' && execucao && <AcoesPosteriores execucao={execucao} res={res} />}
    </>
  )
}

function Propostas({ res }: { res: Resultado }) {
  const [repo, setRepo] = useState(lerPreferencias().ultimo_repositorio)
  const [confirmar, setConfirmar] = useState<Resultado['propostas'][number] | null>(null)
  const [saida, setSaida] = useState<string | null>(null)
  const aplicar = async () => {
    if (!confirmar) return
    try {
      const r = await api.aplicar(res.meta.id, confirmar.nome, confirmar.patch_sha256, repo)
      setSaida(`${r.ok ? 'Aplicado.' : 'Falhou.'}\n${r.saida}`)
    } catch (e) { setSaida((e as Error).message) }
    setConfirmar(null)
  }
  return (
    <div className="cartao">
      <h3>Patches propostos</h3>
      <p className="miudo">Cada patch foi gerado numa cópia isolada. Revise antes de aplicar; a aplicação exige o mesmo commit base e árvore limpa.</p>
      <label className="campo"><span>Repositório onde aplicar</span><input value={repo} onChange={(e) => setRepo(e.target.value)} /></label>
      <table>
        <thead><tr><th>Proposta</th><th>Tamanho</th><th>SHA-256</th><th></th></tr></thead>
        <tbody>
          {res.propostas.map((p) => (
            <tr key={p.nome}>
              <td>{p.nome}</td><td>{p.bytes} bytes</td><td className="miudo">{p.patch_sha256.slice(0, 16)}...</td>
              <td><button className="botao secundario" onClick={() => setConfirmar(p)}>Aplicar</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="miudo">Para revisar: abra {res.pasta}/&lt;proposta&gt;/changes.patch</p>
      {saida && <pre className="log">{saida}</pre>}
      {confirmar && (
        <div className="modal" onClick={() => setConfirmar(null)}>
          <div className="modal-caixa" onClick={(e) => e.stopPropagation()}>
            <h2>Aplicar patch no repositório?</h2>
            <ul className="resumo">
              <li><span>Proposta</span><b>{confirmar.nome}</b></li>
              <li><span>Repositório</span><b>{repo}</b></li>
              <li><span>SHA-256</span><b className="miudo">{confirmar.patch_sha256}</b></li>
            </ul>
            <p className="aviso">Isso altera arquivos do repositório. Confirme que revisou o changes.patch.</p>
            <div className="linha">
              <button className="botao secundario" onClick={() => setConfirmar(null)}>Voltar</button>
              <button className="botao perigo" onClick={aplicar}>Aplicar patch</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const ACOES_POSTERIORES: { acao: string; nome: string; params: string[] }[] = [
  { acao: 'comentar_pr_azure', nome: 'Comentar na PR do Azure DevOps', params: ['org', 'projeto', 'repo', 'pr'] },
  { acao: 'comentar_pr_github', nome: 'Comentar na PR do GitHub', params: ['repo', 'pr'] },
  { acao: 'salvar_na_biblioteca', nome: 'Salvar na biblioteca MCP', params: ['titulo', 'projeto'] },
  { acao: 'notificar', nome: 'Notificar', params: [] },
]

function AcoesPosteriores({ execucao, res }: { execucao: string; res: Resultado }) {
  const pendentes = (res.meta.acoes ?? []).filter((a) => a.status !== 'ok')
  const [escolhida, setEscolhida] = useState(ACOES_POSTERIORES[0])
  const [params, setParams] = useState<Record<string, string>>({})
  const [confirmar, setConfirmar] = useState(false)
  const [saida, setSaida] = useState<string | null>(null)
  const executar = async () => {
    const pedido: PedidoAcao = { acao: escolhida.acao, params }
    try {
      const r = await api.acao(execucao, pedido)
      setSaida((r.acoes ?? []).map((a) => `${a.acao}: ${a.status} · ${a.detalhe}`).join('\n') || r.saida || '')
    } catch (e) { setSaida((e as Error).message) }
    setConfirmar(false)
  }
  return (
    <div className="cartao">
      <h3>Ações sobre o resultado</h3>
      {pendentes.length > 0 && <p className="aviso">Pendentes: {pendentes.map((a) => `${a.acao} (${a.status})`).join(', ')}</p>}
      <div className="grade-3">
        <label className="campo"><span>Ação</span>
          <select value={escolhida.acao} onChange={(e) => { setEscolhida(ACOES_POSTERIORES.find((a) => a.acao === e.target.value)!); setParams({}) }}>
            {ACOES_POSTERIORES.map((a) => <option key={a.acao} value={a.acao}>{a.nome}</option>)}
          </select></label>
        {escolhida.params.map((p) => (
          <label key={p} className="campo"><span>{p}</span><input value={params[p] ?? ''} onChange={(e) => setParams({ ...params, [p]: e.target.value })} /></label>
        ))}
      </div>
      <button className="botao" onClick={() => setConfirmar(true)}>Revisar e executar</button>
      {saida && <pre className="log">{saida}</pre>}
      {confirmar && (
        <div className="modal" onClick={() => setConfirmar(false)}>
          <div className="modal-caixa larga" onClick={(e) => e.stopPropagation()}>
            <h2>{escolhida.nome}</h2>
            <p className="miudo">Este é o texto que será enviado (com segredos redigidos):</p>
            <div className="previa"><Markdown texto={res.markdown} /></div>
            <div className="linha">
              <button className="botao secundario" onClick={() => setConfirmar(false)}>Voltar</button>
              <button className="botao perigo" onClick={executar}>Enviar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

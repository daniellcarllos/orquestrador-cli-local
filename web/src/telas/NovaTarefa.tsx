import { useEffect, useMemo, useState } from 'react'
import { api, type Ambiente, type Fluxo, type InfoRepo, type Pedido, type PedidoAcao, type PlanoApi } from '../api'
import { lerPreferencias, salvarPreferencias } from '../preferencias'
import { SETOR, type Papel } from '../office/setores'
import { Sprite } from '../pixel/Sprite'

interface OpcaoFluxo {
  id: Fluxo
  nome: string
  posto: Papel
  resumo: string
  texto?: string // rótulo do campo de texto principal
  api: boolean
}

const FLUXOS: OpcaoFluxo[] = [
  { id: 'revisar', nome: 'Revisar código', posto: 'revisor', api: true,
    resumo: 'Triagem, três revisores em paralelo (segurança, bugs, qualidade) e consolidação com veredito.' },
  { id: 'analisar', nome: 'Analisar código', posto: 'analista', api: true, texto: 'Pergunta sobre o código',
    resumo: 'A triagem escolhe as áreas, um analista por área em paralelo, e o coordenador responde.' },
  { id: 'desenvolver', nome: 'Desenvolver em paralelo', posto: 'implementador', api: true, texto: 'Objetivo',
    resumo: 'Plano em subtarefas, implementação em cópias isoladas, testes e revisão. Gera patches para você aplicar.' },
  { id: 'equipe', nome: 'Equipe (tarefa aberta)', posto: 'coordenador', api: true, texto: 'Tarefa',
    resumo: 'Time do Agno: líder com modelo forte delega para analista, revisor e planejador.' },
  { id: 'cli', nome: 'Terminal (assinatura)', posto: 'terminais', api: false, texto: 'Tarefa',
    resumo: 'Uma CLI autenticada (Codex, Claude Code ou Gemini) em modo somente leitura. Sem custo de API.' },
]

const ACOES_INFO: Record<string, { nome: string; externa: boolean; params: { chave: string; rotulo: string; dica?: string }[] }> = {
  notificar: { nome: 'Notificar ao terminar', externa: false, params: [] },
  comentar_pr_azure: { nome: 'Comentar na PR do Azure DevOps', externa: true, params: [
    { chave: 'org', rotulo: 'Organização' }, { chave: 'projeto', rotulo: 'Projeto' },
    { chave: 'repo', rotulo: 'Repositório' }, { chave: 'pr', rotulo: 'Nº da PR' }] },
  comentar_pr_github: { nome: 'Comentar na PR do GitHub', externa: true, params: [
    { chave: 'repo', rotulo: 'dono/repositório' }, { chave: 'pr', rotulo: 'Nº da PR' }] },
  salvar_na_biblioteca: { nome: 'Salvar na biblioteca MCP', externa: true, params: [
    { chave: 'titulo', rotulo: 'Título (sem espaços)', dica: 'use-hifens' }, { chave: 'projeto', rotulo: 'Projeto' }] },
}

export function NovaTarefa({ ambiente, aoIniciar }: { ambiente: Ambiente | null; aoIniciar: (jobId: string) => void }) {
  const pref = useMemo(lerPreferencias, [])
  const [fluxo, setFluxo] = useState<Fluxo>('revisar')
  const [repositorio, setRepositorio] = useState(pref.ultimo_repositorio)
  const [info, setInfo] = useState<InfoRepo | null>(null)
  const [erroRepo, setErroRepo] = useState<string | null>(null)
  const [favoritos, setFavoritos] = useState<string[]>([])
  const [texto, setTexto] = useState('')
  const [base, setBase] = useState('')
  const [head, setHead] = useState('')
  const [diff, setDiff] = useState('')
  const [mcp, setMcp] = useState({ prompt_id: '', projeto: '', grupo: '' })
  const [maxAreas, setMaxAreas] = useState('4')
  const [teste, setTeste] = useState('')
  const [maxSub, setMaxSub] = useState('4')
  const [modo, setModo] = useState('coordinate')
  const [agente, setAgente] = useState('')
  const [politica, setPolitica] = useState('')
  const [cfg, setCfg] = useState({ simulado: pref.simulado, teto_usd: pref.teto_usd, teto_tokens: pref.teto_tokens,
    teto_dia_usd: pref.teto_dia_usd, nivel_forcado: pref.nivel_forcado })
  const [acoes, setAcoes] = useState<Record<string, PedidoAcao & { ativa: boolean }>>({})
  const [plano, setPlano] = useState<PlanoApi | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [confirmar, setConfirmar] = useState(false)

  const opcao = FLUXOS.find((f) => f.id === fluxo)!

  useEffect(() => { api.favoritos().then(setFavoritos).catch(() => undefined) }, [])

  useEffect(() => {
    setPlano(null)
    if (!repositorio.startsWith('/')) { setInfo(null); return }
    const t = setTimeout(() => {
      api.repositorio(repositorio)
        .then((i) => {
          setInfo(i); setErroRepo(null)
          if (i.branches?.length && !base) setBase(i.branches.find((b) => ['main', 'master', 'develop'].includes(b)) ?? '')
          if (i.branch && !head) setHead(i.branch)
        })
        .catch((e: Error) => { setInfo(null); setErroRepo(e.message) })
    }, 400)
    return () => clearTimeout(t)
  }, [repositorio]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => setPlano(null), [fluxo, texto, base, head, diff, cfg, acoes, agente, politica, modo, teste])

  const pedido = (): Pedido => {
    const p: Pedido = { fluxo, repositorio, texto: texto || undefined }
    if (fluxo === 'revisar') {
      if (diff) p.diff_arquivo = diff
      else { p.base = base; p.head = head || undefined }
      if (mcp.prompt_id) p.mcp = mcp
    }
    if (fluxo === 'analisar') p.max_areas = Number(maxAreas)
    if (fluxo === 'desenvolver') { p.teste = teste || undefined; p.max_subtarefas = Number(maxSub) }
    if (fluxo === 'equipe') p.modo = modo
    if (fluxo === 'cli') { p.agente = agente || undefined; p.politica = politica || undefined }
    if (opcao.api) {
      p.config = { simulado: cfg.simulado, teto_usd: cfg.teto_usd, teto_tokens: cfg.teto_tokens,
        teto_dia_usd: cfg.teto_dia_usd || undefined, nivel_forcado: cfg.nivel_forcado || undefined }
      p.acoes = Object.values(acoes).filter((a) => a.ativa).map(({ acao, params, aprovada }) => ({ acao, params, aprovada }))
    }
    return p
  }

  const verPlano = async () => {
    setOcupado(true); setErro(null)
    try { setPlano(await api.planoExecucao(pedido())) } catch (e) { setErro((e as Error).message) } finally { setOcupado(false) }
  }

  const executar = async () => {
    setOcupado(true); setErro(null)
    try {
      const job = await api.executar(pedido())
      salvarPreferencias({ ...cfg, ultimo_repositorio: repositorio })
      setConfirmar(false)
      aoIniciar(job.id)
    } catch (e) { setErro((e as Error).message); setConfirmar(false) } finally { setOcupado(false) }
  }

  const favoritar = async () => {
    const lista = favoritos.includes(info?.caminho ?? '') ? favoritos.filter((f) => f !== info?.caminho) : [info!.caminho, ...favoritos]
    setFavoritos(await api.salvarFavoritos(lista))
  }

  const acaoAtiva = (nome: string) => acoes[nome]?.ativa ?? false
  const mudarAcao = (nome: string, parcial: Partial<PedidoAcao & { ativa: boolean }>) =>
    setAcoes((a) => ({ ...a, [nome]: { ...{ params: {}, aprovada: false, ativa: false }, ...a[nome], ...parcial, acao: nome } }))

  const externasAprovadas = Object.values(acoes).filter((a) => a.ativa && a.aprovada && ACOES_INFO[a.acao].externa)
  const semAgno = opcao.api && ambiente && !ambiente.agno

  return (
    <div className="tela nova-tarefa">
      <section className="cartao">
        <h2>1. O que fazer</h2>
        <div className="fluxos">
          {FLUXOS.map((f) => {
            const s = SETOR[f.posto]
            return (
              <button key={f.id} className={`fluxo ${fluxo === f.id ? 'ativo' : ''}`} style={{ ['--cor' as string]: s.cor }} onClick={() => setFluxo(f.id)}>
                <Sprite grade={s.sprite[0]} escala={3} titulo={s.personagem.nome} />
                <span className="fluxo-nome">{f.nome}</span>
                <span className="miudo">{f.resumo}</span>
              </button>
            )
          })}
        </div>
        {semAgno && <p className="aviso">O extra de API não está instalado no Python deste painel. Rode o serve com <code>.venv/bin/python -m orchestrator serve</code>.</p>}
      </section>

      <section className="cartao">
        <h2>2. Repositório</h2>
        <div className="linha">
          <label className="campo cresce">
            <span>Caminho absoluto</span>
            <input value={repositorio} onChange={(e) => setRepositorio(e.target.value)} placeholder="/Users/voce/projetos/meu-repo" list="favoritos" />
            <datalist id="favoritos">{favoritos.map((f) => <option key={f} value={f} />)}</datalist>
          </label>
          {info && <button className="botao secundario" onClick={favoritar}>{favoritos.includes(info.caminho) ? 'remover dos favoritos' : '+ favoritar'}</button>}
        </div>
        {favoritos.length > 0 && (
          <div className="chips">{favoritos.map((f) => <button key={f} className="chip" onClick={() => setRepositorio(f)}>{f.split('/').slice(-2).join('/')}</button>)}</div>
        )}
        {erroRepo && <p className="erro">{erroRepo}</p>}
        {info && (
          <p className="miudo info-repo">
            {info.git
              ? <>git · branch <b>{info.branch ?? '?'}</b> · {info.limpo ? <span className="ok">limpo</span> : <span className="erro">{info.alteracoes} alterações</span>}{info.na_raiz ? '' : ' · não é a raiz'} · {info.ultimo_commit}</>
              : <span className="erro">não é um repositório git (revisar por branch e desenvolver exigem git)</span>}
          </p>
        )}
        {fluxo === 'desenvolver' && info?.git && (!info.limpo || !info.na_raiz) && (
          <p className="aviso">Desenvolver exige a raiz de um repositório sem alterações pendentes.</p>
        )}
      </section>

      <section className="cartao">
        <h2>3. Detalhes</h2>
        {opcao.texto && (
          <label className="campo">
            <span>{opcao.texto}</span>
            <textarea rows={3} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={4000} />
          </label>
        )}
        {fluxo === 'revisar' && (
          <>
            <div className="grade-2">
              <label className="campo"><span>Base (comparar com)</span>
                <select value={base} onChange={(e) => setBase(e.target.value)} disabled={!!diff}>
                  <option value="">—</option>{info?.branches?.map((b) => <option key={b}>{b}</option>)}
                </select></label>
              <label className="campo"><span>Head (alterações)</span>
                <select value={head} onChange={(e) => setHead(e.target.value)} disabled={!!diff}>
                  <option value="">HEAD</option>{info?.branches?.map((b) => <option key={b}>{b}</option>)}
                </select></label>
            </div>
            <label className="campo"><span>Ou arquivo de diff (caminho absoluto)</span>
              <input value={diff} onChange={(e) => setDiff(e.target.value)} placeholder="/caminho/pr.diff" /></label>
            <details>
              <summary>Diretrizes da biblioteca MCP (opcional)</summary>
              <div className="grade-3">
                <label className="campo"><span>ID do prompt</span><input value={mcp.prompt_id} onChange={(e) => setMcp({ ...mcp, prompt_id: e.target.value })} placeholder="93d6961d2a" /></label>
                <label className="campo"><span>Projeto</span><input value={mcp.projeto} onChange={(e) => setMcp({ ...mcp, projeto: e.target.value })} placeholder="Code Review" /></label>
                <label className="campo"><span>Grupo</span><input value={mcp.grupo} onChange={(e) => setMcp({ ...mcp, grupo: e.target.value })} placeholder="rodo next" /></label>
              </div>
            </details>
          </>
        )}
        {fluxo === 'analisar' && (
          <label className="campo curto"><span>Máximo de áreas em paralelo</span>
            <input type="number" min={1} max={8} value={maxAreas} onChange={(e) => setMaxAreas(e.target.value)} /></label>
        )}
        {fluxo === 'desenvolver' && (
          <div className="grade-2">
            <label className="campo"><span>Comando de teste (opcional)</span>
              <input value={teste} onChange={(e) => setTeste(e.target.value)} placeholder="pytest -q · dotnet test · npm test" /></label>
            <label className="campo"><span>Máximo de subtarefas</span>
              <input type="number" min={1} max={6} value={maxSub} onChange={(e) => setMaxSub(e.target.value)} /></label>
          </div>
        )}
        {fluxo === 'equipe' && (
          <label className="campo curto"><span>Modo do time</span>
            <select value={modo} onChange={(e) => setModo(e.target.value)}>
              <option value="coordinate">coordenar: divide e delega</option>
              <option value="route">encaminhar: um especialista responde</option>
              <option value="broadcast">todos: mesma tarefa para todos e síntese</option>
            </select></label>
        )}
        {fluxo === 'cli' && (
          <div className="grade-2">
            <label className="campo"><span>Agente</span>
              <select value={agente} onChange={(e) => setAgente(e.target.value)}>
                <option value="">automático (pela política)</option>
                <option value="claude">Claude Code</option><option value="codex">Codex</option><option value="gemini">Gemini CLI</option>
              </select></label>
            <label className="campo"><span>Política</span>
              <select value={politica} onChange={(e) => setPolitica(e.target.value)}>
                <option value="">ordem padrão</option>{ambiente?.politicas.map((p) => <option key={p}>{p}</option>)}
              </select></label>
          </div>
        )}
      </section>

      {opcao.api && (
        <section className="cartao">
          <h2>4. Configurações desta execução</h2>
          <div className="grade-3">
            <label className="campo check"><input type="checkbox" checked={cfg.simulado} onChange={(e) => setCfg({ ...cfg, simulado: e.target.checked })} />
              <span>Modo simulado (sem chave, sem custo)</span></label>
            <label className="campo"><span>Teto por execução (US$)</span>
              <input type="number" step="0.05" min="0.01" value={cfg.teto_usd} onChange={(e) => setCfg({ ...cfg, teto_usd: e.target.value })} /></label>
            <label className="campo"><span>Teto de tokens</span>
              <input type="number" step="10000" min="1000" value={cfg.teto_tokens} onChange={(e) => setCfg({ ...cfg, teto_tokens: e.target.value })} /></label>
            <label className="campo"><span>Teto do dia (US$, opcional)</span>
              <input type="number" step="0.5" min="0" value={cfg.teto_dia_usd} onChange={(e) => setCfg({ ...cfg, teto_dia_usd: e.target.value })} /></label>
            <label className="campo"><span>Nível dos modelos</span>
              <select value={cfg.nivel_forcado} onChange={(e) => setCfg({ ...cfg, nivel_forcado: e.target.value })}>
                <option value="">por papel (econômico)</option>
                <option value="forte">tudo no forte (comparação)</option>
                <option value="medio">tudo no médio</option>
                <option value="leve">tudo no leve</option>
              </select></label>
          </div>

          <h3>Ações ao terminar</h3>
          <div className="acoes">
            {Object.entries(ACOES_INFO).map(([nome, info]) => (
              <div key={nome} className={`acao ${acaoAtiva(nome) ? 'ativa' : ''}`}>
                <label className="campo check">
                  <input type="checkbox" checked={acaoAtiva(nome)} onChange={(e) => mudarAcao(nome, { ativa: e.target.checked })} />
                  <span>{info.nome}{info.externa ? ' · efeito externo' : ''}</span>
                </label>
                {acaoAtiva(nome) && info.params.length > 0 && (
                  <div className="grade-4">
                    {info.params.map((p) => (
                      <label key={p.chave} className="campo"><span>{p.rotulo}</span>
                        <input value={acoes[nome]?.params?.[p.chave] ?? ''} placeholder={p.dica}
                          onChange={(e) => mudarAcao(nome, { params: { ...acoes[nome]?.params, [p.chave]: e.target.value } })} /></label>
                    ))}
                  </div>
                )}
                {acaoAtiva(nome) && info.externa && (
                  <label className="campo check">
                    <input type="checkbox" checked={acoes[nome]?.aprovada ?? false} onChange={(e) => mudarAcao(nome, { aprovada: e.target.checked })} />
                    <span>Executar automaticamente ao terminar (sem revisar o texto antes)</span>
                  </label>
                )}
              </div>
            ))}
          </div>
          <p className="miudo">Ações externas não aprovadas ficam pendentes: você revisa o resultado e dispara na tela de Execuções.</p>
        </section>
      )}

      <section className="cartao rodape-acoes">
        {erro && <p className="erro">{erro}</p>}
        <div className="linha">
          <button className="botao secundario" onClick={verPlano} disabled={ocupado || !repositorio}>Ver plano (sem custo)</button>
          <button className="botao" onClick={() => setConfirmar(true)} disabled={ocupado || !repositorio || !!semAgno}>Executar</button>
        </div>
        {plano && <TabelaPlano plano={plano} />}
      </section>

      {confirmar && (
        <div className="modal" onClick={() => setConfirmar(false)}>
          <div className="modal-caixa" onClick={(e) => e.stopPropagation()}>
            <h2>Confirmar execução</h2>
            <ul className="resumo">
              <li><span>Fluxo</span><b>{opcao.nome}</b></li>
              <li><span>Repositório</span><b>{repositorio}</b></li>
              {opcao.api && <li><span>Modelos</span><b>{cfg.simulado ? 'SIMULADO (sem custo)' : `reais, até US$ ${cfg.teto_usd}`}</b></li>}
              {!opcao.api && <li><span>Custo</span><b>cota da sua assinatura</b></li>}
              {externasAprovadas.length > 0 && <li><span>Ações automáticas</span><b className="erro">{externasAprovadas.map((a) => ACOES_INFO[a.acao].nome).join(', ')}</b></li>}
            </ul>
            <p className="miudo">O código e o diff do repositório serão enviados ao provedor do modelo, com segredos redigidos.</p>
            <div className="linha">
              <button className="botao secundario" onClick={() => setConfirmar(false)}>Voltar</button>
              <button className="botao" onClick={executar} disabled={ocupado}>Aprovar e executar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function TabelaPlano({ plano }: { plano: PlanoApi }) {
  if (plano.comando === 'cli') {
    return (
      <div className="plano">
        <p>Agente <b>{plano.agent}</b>{plano.model ? ` / ${plano.model}` : ''} · nível {plano.complexity} · risco {plano.risk}</p>
        <p className="miudo">{plano.rationale}</p>
      </div>
    )
  }
  return (
    <div className="plano">
      <p>{plano.simulado ? 'Simulado' : 'Chamadas reais'} · teto US$ {plano.teto_usd} · {plano.teto_tokens?.toLocaleString('pt-BR')} tokens</p>
      <table>
        <thead><tr><th>Papel</th><th>Nível</th><th>Modelo</th></tr></thead>
        <tbody>
          {Object.entries(plano.papeis ?? {}).map(([papel, v]) => (
            <tr key={papel}><td>{papel}</td><td>{v.nivel}</td><td className={v.erro ? 'erro' : ''}>{v.erro ?? `${v.provedor} / ${v.modelo}`}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

import { Fragment, useState } from 'react'
import type { Execucao } from '../types'
import { SETOR, postoDaEtapa, type Papel } from '../office/setores'
import { formatarCusto, formatarData, formatarDuracao, formatarTokens, sucesso } from '../office/estatisticas'
import { Sprite } from '../pixel/Sprite'

type Filtro = 'todos' | 'api' | 'cli' | 'falhas'

const CLI_NOMES: Record<string, string> = { codex: 'Codex', claude: 'Claude Code', gemini: 'Gemini CLI' }

export function Historico({ execucoes, posto }: { execucoes: Execucao[]; posto: Papel | null }) {
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const [aberta, setAberta] = useState<string | null>(null)

  const lista = execucoes.filter((e) => {
    if (posto === 'terminais' && e.modo === 'api') return false
    if (posto && posto !== 'terminais' && posto !== 'arquivo' && posto !== 'portaria'
      && !(e.etapas ?? []).some((x) => postoDaEtapa(x.papel) === posto)) return false
    if (filtro === 'api') return e.modo === 'api'
    if (filtro === 'cli') return e.modo !== 'api'
    if (filtro === 'falhas') return !sucesso(e)
    return true
  })

  return (
    <section className="historico">
      <header className="historico-cabecalho">
        <h2>Registro de execuções{posto ? ` · ${SETOR[posto].nome}` : ''}</h2>
        <div className="filtros">
          {(['todos', 'api', 'cli', 'falhas'] as Filtro[]).map((f) => (
            <button key={f} className={filtro === f ? 'ativo' : ''} onClick={() => setFiltro(f)}>{f}</button>
          ))}
        </div>
      </header>
      {lista.length === 0 ? (
        <p className="vazio">
          Nenhuma execução registrada. Experimente <code>orchestrator revisar --cwd . --base main --simulado --approve</code>.
        </p>
      ) : (
        <table>
          <thead>
            <tr><th>Quando</th><th>Fluxo</th><th>Modo</th><th>Etapas</th><th>Modelos</th><th>Tokens</th><th>Custo</th><th>Duração</th><th>Status</th></tr>
          </thead>
          <tbody>
            {lista.map((e) => {
              const ok = sucesso(e)
              const api = e.modo === 'api'
              const modelos = api ? [...new Set((e.etapas ?? []).map((x) => x.modelo))] : [e.model ?? 'padrão']
              const semPreco = (e.etapas ?? []).some((x) => x.custo_usd === null)
              return (
                <Fragment key={e.id}>
                  <tr className={`${ok ? '' : 'linha-falha'} ${api ? 'clicavel' : ''}`} onClick={() => api && setAberta(aberta === e.id ? null : e.id)}>
                    <td>{formatarData(e.started_at)}</td>
                    <td>{api ? '+ ' : ''}{e.action ?? 'run'}</td>
                    <td>{api ? 'API' : CLI_NOMES[e.agent] ?? e.agent}</td>
                    <td>{api ? e.etapas?.length ?? 0 : 1}</td>
                    <td className="miudo">{modelos.join(', ')}</td>
                    <td>{api ? formatarTokens(e.tokens ?? 0) : '–'}</td>
                    <td>{api ? formatarCusto(e.custo_usd ?? 0, semPreco) : 'assinatura'}</td>
                    <td>{formatarDuracao(e.duration_ms)}</td>
                    <td className={ok ? 'ok' : 'erro'}>
                      {api ? (e.status ?? '?').toUpperCase() : e.timed_out ? 'TEMPO ESGOTADO' : ok ? 'OK' : `ERRO ${e.exit_code ?? '?'}`}
                    </td>
                  </tr>
                  {aberta === e.id && (
                    <tr className="linha-tempo-linha">
                      <td colSpan={9}>
                        <ol className="linha-tempo">
                          {(e.etapas ?? []).map((x, i) => {
                            const s = SETOR[postoDaEtapa(x.papel)]
                            return (
                              <li key={i} style={{ ['--cor' as string]: s.cor }} className={x.status === 'ok' ? '' : 'etapa-falha'}>
                                <Sprite grade={s.sprite[0]} escala={2} titulo={s.personagem.nome} />
                                <div>
                                  <b>{x.papel}</b>{x.rodada > 1 ? ` (rodada ${x.rodada})` : ''}
                                  <div className="miudo">{x.nivel} · {x.modelo}</div>
                                  <div className="miudo">
                                    {formatarTokens(x.tokens_entrada)} entrada · {formatarTokens(x.tokens_saida)} saída · {x.custo_usd == null ? 'sem preço' : formatarCusto(x.custo_usd)} · {formatarDuracao(x.duracao_ms)}
                                  </div>
                                  <div className={x.status === 'ok' ? 'ok' : 'erro'}>{x.status}</div>
                                </div>
                              </li>
                            )
                          })}
                        </ol>
                        <p className="miudo">Resposta completa e meta.json em ~/.local/state/orquestrador-cli-local/execucoes/{e.id}/</p>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      )}
      <p className="miudo">* custo parcial: há modelos sem preço configurado no catálogo.</p>
    </section>
  )
}

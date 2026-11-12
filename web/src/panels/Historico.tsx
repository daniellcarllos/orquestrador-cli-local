import { useState } from 'react'
import type { Execucao } from '../types'
import { SETOR_POR_AGENTE } from '../office/setores'
import { formatarData, formatarDuracao, sucesso } from '../office/estatisticas'
import { Sprite } from '../pixel/Sprite'

type Filtro = 'todos' | 'run' | 'prepare' | 'falhas'

export function Historico({ execucoes, filtroAgente }: { execucoes: Execucao[]; filtroAgente: string | null }) {
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const lista = execucoes.filter((e) => {
    if (filtroAgente && e.agent !== filtroAgente) return false
    if (filtro === 'run') return (e.action ?? 'run') === 'run'
    if (filtro === 'prepare') return e.action === 'prepare'
    if (filtro === 'falhas') return !sucesso(e)
    return true
  })

  return (
    <section className="historico">
      <header className="historico-cabecalho">
        <h2>Registro de execuções{filtroAgente ? ` · ${SETOR_POR_AGENTE[filtroAgente as keyof typeof SETOR_POR_AGENTE]?.heroi}` : ''}</h2>
        <div className="filtros">
          {(['todos', 'run', 'prepare', 'falhas'] as Filtro[]).map((f) => (
            <button key={f} className={filtro === f ? 'ativo' : ''} onClick={() => setFiltro(f)}>{f}</button>
          ))}
        </div>
      </header>
      {lista.length === 0 ? (
        <p className="vazio">Nenhuma execução registrada. Rode <code>python3 -m orchestrator run "tarefa" --approve</code> para aparecer aqui.</p>
      ) : (
        <table>
          <thead>
            <tr><th></th><th>Quando</th><th>Ação</th><th>Agente</th><th>Modelo</th><th>Política</th><th>Duração</th><th>Status</th><th>Id</th></tr>
          </thead>
          <tbody>
            {lista.map((e) => {
              const setor = SETOR_POR_AGENTE[e.agent]
              const ok = sucesso(e)
              return (
                <tr key={e.id} className={ok ? '' : 'linha-falha'}>
                  <td>{setor && <Sprite grade={setor.sprite[0]} escala={1} />}</td>
                  <td>{formatarData(e)}</td>
                  <td>{e.action ?? 'run'}</td>
                  <td style={{ color: setor?.cor }}>{setor?.heroi ?? e.agent}</td>
                  <td>{e.model ?? 'padrão'}</td>
                  <td>{e.policy_version}</td>
                  <td>{formatarDuracao(e.duration_ms)}</td>
                  <td className={ok ? 'ok' : 'erro'}>
                    {e.timed_out ? 'TEMPO ESGOTADO' : ok ? 'OK' : `ERRO ${e.exit_code ?? '?'}`}{e.truncated ? ' · truncado' : ''}
                  </td>
                  <td className="miudo">{e.id.slice(0, 8)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}

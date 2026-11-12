import type { Execucao } from '../types'

/** Portões de aprovação: tudo que passou por aqui foi autorizado explicitamente na CLI. */
export function Portaria({ execucoes }: { execucoes: Execucao[] }) {
  const runs = execucoes.filter((e) => (e.action ?? 'run') === 'run').length
  const prepares = execucoes.filter((e) => e.action === 'prepare').length
  return (
    <div className="portaria">
      <ul className="portoes">
        <li><code>--approve</code><span>execuções liberadas</span><b>{runs}</b></li>
        <li><code>--approve</code><span>preparações em cópia</span><b>{prepares}</b></li>
        <li><code>--approve-mcp</code><span>leituras da biblioteca</span><b>sob demanda</b></li>
        <li><code>--approve-sha256</code><span>patches aplicados</span><b>manual</b></li>
      </ul>
      <p className="miudo">Sem a flag, o orquestrador só mostra o plano. O painel nunca executa nada.</p>
    </div>
  )
}

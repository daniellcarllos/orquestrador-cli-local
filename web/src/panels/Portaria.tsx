import type { Execucao } from '../types'

/** Portões de aprovação: tudo que passou por aqui foi autorizado explicitamente no terminal. */
export function Portaria({ execucoes }: { execucoes: Execucao[] }) {
  const api = execucoes.filter((e) => e.modo === 'api').length
  const cli = execucoes.length - api
  return (
    <div className="portaria">
      <ul className="portoes">
        <li><code>--approve</code><span>execuções por API liberadas</span><b>{api}</b></li>
        <li><code>--approve</code><span>execuções de terminal</span><b>{cli}</b></li>
        <li><code>SIM</code><span>ações externas (PR, biblioteca)</span><b>uma a uma</b></li>
        <li><code>--teto-usd</code><span>gasto máximo por execução</span><b>sempre</b></li>
      </ul>
      <p className="miudo">Sem aprovação, o orquestrador só mostra o plano. O painel nunca executa nada.</p>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Plano } from '../types'
import { SETOR_POR_AGENTE } from '../office/setores'

/** Console da Direção: classifica uma tarefa sem executar nada. */
export function Direcao({ politicas }: { politicas: string[] }) {
  const [tarefa, setTarefa] = useState('Revisar o diff .NET/C#')
  const [politica, setPolitica] = useState('')
  const [plano, setPlano] = useState<Plano | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)

  useEffect(() => {
    if (!politica && politicas.length) setPolitica(politicas[0])
  }, [politicas, politica])

  useEffect(() => {
    if (!tarefa.trim()) return
    const t = setTimeout(() => {
      setCarregando(true)
      api
        .plano(tarefa, politica || undefined)
        .then((p) => { setPlano(p); setErro(null) })
        .catch((e: Error) => { setPlano(null); setErro(e.message) })
        .finally(() => setCarregando(false))
    }, 350)
    return () => clearTimeout(t)
  }, [tarefa, politica])

  const setor = plano ? SETOR_POR_AGENTE[plano.agent] : null

  return (
    <div className="direcao" onClick={(e) => e.stopPropagation()}>
      <label className="campo">
        <span>Tarefa</span>
        <input value={tarefa} onChange={(e) => setTarefa(e.target.value)} maxLength={4000} />
      </label>
      <label className="campo">
        <span>Política</span>
        <select value={politica} onChange={(e) => setPolitica(e.target.value)}>
          <option value="">(sem política: ordem padrão)</option>
          {politicas.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
      <div className="decisao">
        {carregando && <span className="piscando">consultando…</span>}
        {erro && <span className="erro">{erro}</span>}
        {plano && !carregando && (
          <>
            <div>&gt;&gt; <strong style={{ color: setor?.cor }}>{setor?.heroi}</strong> ({plano.agent}{plano.model ? ` / ${plano.model}` : ''})</div>
            <div>nível <b>{plano.complexity}</b> · risco <b className={plano.risk === 'alto' ? 'erro' : ''}>{plano.risk}</b> · tipo <b>{plano.task_type}</b></div>
            <div className="miudo">{plano.rationale}</div>
          </>
        )}
      </div>
    </div>
  )
}

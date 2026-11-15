import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Catalogo, ModeloNivel } from '../types'
import { lerPreferencias, salvarPreferencias, type Preferencias } from '../preferencias'

const NIVEIS = ['leve', 'medio', 'forte'] as const
const PROVEDORES = { anthropic: 'ANTHROPIC_API_KEY', google: 'GOOGLE_API_KEY', openai: 'OPENAI_API_KEY' } as const
const USO: Record<string, string> = {
  leve: 'triagem e classificação',
  medio: 'análise, revisão e implementação',
  forte: 'planejamento, coordenação e líder do time',
}

export function Configuracoes() {
  const [cat, setCat] = useState<Catalogo | null>(null)
  const [niveis, setNiveis] = useState<Record<string, ModeloNivel>>({})
  const [precos, setPrecos] = useState<Record<string, { entrada: string; saida: string }>>({})
  const [msg, setMsg] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [pref, setPref] = useState<Preferencias>(lerPreferencias())
  const [favoritos, setFavoritos] = useState<string[]>([])

  const aplicar = (c: Catalogo) => {
    setCat(c)
    setNiveis(c.niveis)
    const p: Record<string, { entrada: string; saida: string }> = {}
    const modelos = new Set([...Object.values(c.niveis).map((n) => n.modelo), ...Object.keys(c.precos_por_milhao)])
    for (const m of modelos) {
      const v = c.precos_por_milhao[m]
      p[m] = { entrada: v?.entrada?.toString() ?? '', saida: v?.saida?.toString() ?? '' }
    }
    setPrecos(p)
  }

  useEffect(() => {
    api.catalogo().then(aplicar).catch((e: Error) => setErro(e.message))
    api.favoritos().then(setFavoritos).catch(() => undefined)
  }, [])

  const salvar = async () => {
    if (!cat) return
    setErro(null); setMsg(null)
    const precosNum: Record<string, { entrada: number | null; saida: number | null }> = {}
    for (const [m, v] of Object.entries(precos)) {
      precosNum[m] = { entrada: v.entrada === '' ? null : Number(v.entrada), saida: v.saida === '' ? null : Number(v.saida) }
    }
    for (const n of Object.values(niveis)) if (!precosNum[n.modelo]) precosNum[n.modelo] = { entrada: null, saida: null }
    try {
      aplicar(await api.salvarCatalogo({ versao: `usuario-${new Date().toISOString().slice(0, 10)}`, niveis,
        alternativos: cat.alternativos ?? {}, precos_por_milhao: precosNum }))
      setMsg('Catálogo salvo. As próximas execuções usam estes modelos e preços.')
    } catch (e) { setErro((e as Error).message) }
  }

  const restaurar = async () => {
    aplicar(await api.restaurarCatalogo())
    setMsg('Catálogo padrão do projeto restaurado.')
  }

  const mudarPref = (p: Partial<Preferencias>) => setPref(salvarPreferencias(p))
  const removerFavorito = async (f: string) => setFavoritos(await api.salvarFavoritos(favoritos.filter((x) => x !== f)))

  return (
    <div className="tela configuracoes">
      <section className="cartao">
        <h2>Provedores de API</h2>
        <ul className="provedores">
          {Object.entries(PROVEDORES).map(([p, variavel]) => (
            <li key={p}>
              <b>{p}</b>
              <span className={cat?.provedores[p] ? 'ok' : 'erro'}>{cat?.provedores[p] ? 'chave configurada' : 'sem chave'}</span>
              <code>{variavel}</code>
            </li>
          ))}
        </ul>
        <p className="miudo">
          Por segurança, as chaves não são digitadas aqui: defina a variável no terminal antes de iniciar o painel e reinicie o serve.
        </p>
        <pre className="log">{`export ANTHROPIC_API_KEY=...   # de um gerenciador de senhas, não do histórico
.venv/bin/python -m orchestrator serve`}</pre>
      </section>

      <section className="cartao">
        <div className="linha entre">
          <h2>Modelos por nível</h2>
          <span className="miudo">{cat?.do_usuario ? 'catálogo personalizado' : 'catálogo padrão do projeto'}</span>
        </div>
        <table>
          <thead><tr><th>Nível</th><th>Usado em</th><th>Provedor</th><th>Modelo</th></tr></thead>
          <tbody>
            {NIVEIS.map((n) => (
              <tr key={n}>
                <td><b>{n}</b></td>
                <td className="miudo">{USO[n]}</td>
                <td>
                  <select value={niveis[n]?.provedor ?? 'anthropic'} onChange={(e) => setNiveis({ ...niveis, [n]: { ...niveis[n], provedor: e.target.value } })}>
                    {Object.keys(PROVEDORES).map((p) => <option key={p}>{p}</option>)}
                  </select>
                </td>
                <td>
                  <input value={niveis[n]?.modelo ?? ''} onChange={(e) => {
                    const modelo = e.target.value
                    setNiveis({ ...niveis, [n]: { ...niveis[n], modelo } })
                    if (modelo && !precos[modelo]) setPrecos({ ...precos, [modelo]: { entrada: '', saida: '' } })
                  }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3>Preços (US$ por milhão de tokens)</h3>
        <p className="miudo">Preencha com a tabela oficial do provedor. Sem preço, o custo não é calculado e o teto em dólar não limita; o teto de tokens continua valendo.</p>
        <table>
          <thead><tr><th>Modelo</th><th>Entrada</th><th>Saída</th></tr></thead>
          <tbody>
            {Object.entries(precos).filter(([m]) => Object.values(niveis).some((n) => n.modelo === m)).map(([m, v]) => (
              <tr key={m}>
                <td>{m}</td>
                <td><input type="number" min="0" step="0.01" value={v.entrada} onChange={(e) => setPrecos({ ...precos, [m]: { ...v, entrada: e.target.value } })} /></td>
                <td><input type="number" min="0" step="0.01" value={v.saida} onChange={(e) => setPrecos({ ...precos, [m]: { ...v, saida: e.target.value } })} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {erro && <p className="erro">{erro}</p>}
        {msg && <p className="ok">{msg}</p>}
        <div className="linha">
          <button className="botao" onClick={salvar}>Salvar catálogo</button>
          {cat?.do_usuario && <button className="botao secundario" onClick={restaurar}>Restaurar padrão</button>}
        </div>
      </section>

      <section className="cartao">
        <h2>Padrões das novas tarefas</h2>
        <div className="grade-3">
          <label className="campo check"><input type="checkbox" checked={pref.simulado} onChange={(e) => mudarPref({ simulado: e.target.checked })} />
            <span>Começar em modo simulado</span></label>
          <label className="campo"><span>Teto por execução (US$)</span>
            <input type="number" step="0.05" value={pref.teto_usd} onChange={(e) => mudarPref({ teto_usd: e.target.value })} /></label>
          <label className="campo"><span>Teto de tokens</span>
            <input type="number" step="10000" value={pref.teto_tokens} onChange={(e) => mudarPref({ teto_tokens: e.target.value })} /></label>
          <label className="campo"><span>Teto do dia (US$)</span>
            <input type="number" step="0.5" value={pref.teto_dia_usd} onChange={(e) => mudarPref({ teto_dia_usd: e.target.value })} /></label>
          <label className="campo"><span>Nível dos modelos</span>
            <select value={pref.nivel_forcado} onChange={(e) => mudarPref({ nivel_forcado: e.target.value })}>
              <option value="">por papel (econômico)</option><option value="forte">tudo no forte</option>
              <option value="medio">tudo no médio</option><option value="leve">tudo no leve</option>
            </select></label>
        </div>
        <p className="miudo">Salvos neste navegador. Cada tarefa pode mudar esses valores antes de executar.</p>
      </section>

      <section className="cartao">
        <h2>Repositórios favoritos</h2>
        {favoritos.length === 0 ? <p className="vazio">Nenhum. Use + favoritar na tela Nova tarefa.</p> : (
          <ul className="favoritos">
            {favoritos.map((f) => <li key={f}><span>{f}</span><button className="botao secundario" onClick={() => removerFavorito(f)}>remover</button></li>)}
          </ul>
        )}
      </section>
    </div>
  )
}

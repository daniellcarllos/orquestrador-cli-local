import type { ReactNode } from 'react'

// Renderizador mínimo e seguro: só cria elementos React (nada de HTML vindo do resultado).
function inline(texto: string): ReactNode[] {
  const partes: ReactNode[] = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let ultimo = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = re.exec(texto))) {
    if (m.index > ultimo) partes.push(texto.slice(ultimo, m.index))
    const t = m[0]
    partes.push(t.startsWith('**') ? <b key={i++}>{t.slice(2, -2)}</b> : <code key={i++}>{t.slice(1, -1)}</code>)
    ultimo = m.index + t.length
  }
  if (ultimo < texto.length) partes.push(texto.slice(ultimo))
  return partes
}

export function Markdown({ texto }: { texto: string }) {
  const blocos: ReactNode[] = []
  let lista: ReactNode[] = []
  let codigo: string[] | null = null
  const fecharLista = () => {
    if (lista.length) blocos.push(<ul key={`l${blocos.length}`}>{lista}</ul>)
    lista = []
  }
  texto.split('\n').forEach((linha, n) => {
    if (linha.startsWith('```')) {
      if (codigo) {
        blocos.push(<pre key={`c${n}`}>{codigo.join('\n')}</pre>)
        codigo = null
      } else {
        fecharLista()
        codigo = []
      }
      return
    }
    if (codigo) return void codigo.push(linha)
    const h = linha.match(/^(#{1,3})\s+(.*)/)
    if (h) {
      fecharLista()
      const Tag = (`h${h[1].length + 2}`) as 'h3' | 'h4' | 'h5'
      blocos.push(<Tag key={n}>{inline(h[2])}</Tag>)
    } else if (/^\s*[-*]\s+/.test(linha)) {
      const sub = /^\s{2,}/.test(linha)
      lista.push(<li key={n} className={sub ? 'sub' : ''}>{inline(linha.replace(/^\s*[-*]\s+/, ''))}</li>)
    } else if (linha.trim()) {
      fecharLista()
      blocos.push(<p key={n}>{inline(linha)}</p>)
    } else {
      fecharLista()
    }
  })
  fecharLista()
  if (codigo) blocos.push(<pre key="cfim">{(codigo as string[]).join('\n')}</pre>)
  return <div className="markdown">{blocos}</div>
}

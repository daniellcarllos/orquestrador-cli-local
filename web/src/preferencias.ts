// Padrões de execução guardados no navegador (não contêm segredos).
export interface Preferencias {
  simulado: boolean
  teto_usd: string
  teto_tokens: string
  teto_dia_usd: string
  nivel_forcado: string
  ultimo_repositorio: string
}

const CHAVE = 'orquestrador-preferencias'
export const PADRAO: Preferencias = {
  simulado: true, teto_usd: '0.50', teto_tokens: '400000', teto_dia_usd: '', nivel_forcado: '', ultimo_repositorio: '',
}

export function lerPreferencias(): Preferencias {
  try {
    return { ...PADRAO, ...JSON.parse(localStorage.getItem(CHAVE) ?? '{}') }
  } catch {
    return PADRAO
  }
}

export function salvarPreferencias(p: Partial<Preferencias>): Preferencias {
  const novo = { ...lerPreferencias(), ...p }
  localStorage.setItem(CHAVE, JSON.stringify(novo))
  return novo
}

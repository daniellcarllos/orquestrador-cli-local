// Paleta de 16 bits compartilhada por todos os sprites. "." é transparente.
export const PALETA: Record<string, string> = {
  k: '#1a1a2e', // contorno / preto
  w: '#f4f4f4', // branco
  r: '#d7263d', // vermelho
  R: '#8b1a2b', // vermelho escuro
  y: '#f2c14e', // dourado
  Y: '#b8860b', // dourado escuro
  b: '#2e6fd9', // azul
  B: '#1b3f8f', // azul escuro
  g: '#4caf50', // verde
  G: '#2e7d32', // verde escuro
  s: '#f1c7a3', // pele clara
  d: '#8d5524', // pele escura
  h: '#5b3a1a', // cabelo castanho
  o: '#e8732a', // laranja / ruivo
  p: '#7b3fa0', // roxo
  c: '#4dd0e1', // ciano
  e: '#9e9e9e', // cinza
  E: '#5a5a5a', // cinza escuro
  t: '#2bb3a0', // verde-água
  m: '#a0713f', // madeira
  n: '#3a2a1a', // madeira escura
}

export type Sprite = string[] // linhas de mesmo comprimento, um caractere por pixel

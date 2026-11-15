import type { Sprite } from './palette'

// Personagens originais do escritório, 12x16 pixels. `olhos` indica a linha e as colunas
// dos olhos, usados para a animação de piscar (segundo quadro).

export interface Personagem {
  nome: string
  base: Sprite
  olhos: [number, number[]]
  pele: string
}

export const GUARDA: Personagem = {
  nome: 'Guarda',
  pele: 's',
  olhos: [4, [4, 7]],
  base: [
    '...kkkkkk...',
    '..kBBBBBBk..',
    '.kkkkykkkkk.',
    '..kssssssk..',
    '..kskssksk..',
    '..kssssssk..',
    '...kssssk...',
    '..kbbbbbbk..',
    '.kbbybbbbbk.',
    '.kbbbbbbmmk.',
    '.ksbbbbbmwk.',
    '..kbbbbbbk..',
    '..kBBkkBBk..',
    '..kBBk.kBBk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const COORDENADORA: Personagem = {
  nome: 'Coordenadora',
  pele: 'd',
  olhos: [4, [4, 7]],
  base: [
    '....kkkk....',
    '...knnnnk...',
    '..knnnnnnk..',
    '.cknddddnk..',
    '.ckdkddkdk..',
    '..kddddddk..',
    '...kddddk...',
    '..kEEwwEEk..',
    '.kEEEwwEEEk.',
    '.kEEErrEEEk.',
    '.kdEEEEEEdk.',
    '..kEEEEEEk..',
    '..kEEkkEEk..',
    '..kEEk.kEEk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const RECEPCIONISTA: Personagem = {
  nome: 'Recepcionista',
  pele: 's',
  olhos: [4, [4, 7]],
  base: [
    '....kkkk....',
    '...khhhhk...',
    '..khhhhhhk..',
    '..khsssshk..',
    '..kskssksk..',
    '..khsssshk..',
    '..kh.kk.hk..',
    '..kyyyyyyk..',
    '.kyyyyyyyyk.',
    '.kyyyyyykrk.',
    '.ksyyyyykRk.',
    '..kbbbbbbk..',
    '..kbbkkbbk..',
    '..kbbk.kbbk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const CARTOGRAFA: Personagem = {
  nome: 'Cartógrafa',
  pele: 's',
  olhos: [4, [4, 7]],
  base: [
    '....kkkk....',
    '...koooook..',
    '..kooooook..',
    '..kossssok..',
    '..kskssksk..',
    '..kossssok..',
    '...kssssk...',
    '..ktwwwwtk..',
    '.kttwwwwttk.',
    '.kttwwwwtkkk',
    '.ksttttttkck',
    '..kttttttkk.',
    '..kmmkkmmk..',
    '..kmmk.kmmk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const INSPETORA: Personagem = {
  nome: 'Inspetora',
  pele: 'd',
  olhos: [4, [4, 7]],
  base: [
    '....kkkk....',
    '...kEEEEk...',
    '..kEEEEEEk..',
    '..kEddddEk..',
    '..kkwkkwkk..',
    '..kddddddk..',
    '...kddddk...',
    '..kgwwwwgk..',
    '.kggwwwwggk.',
    '.kggwwwwgwk.',
    '.kdgggggwwk.',
    '..kggggggk..',
    '..kBBkkBBk..',
    '..kBBk.kBBk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const ARQUITETA: Personagem = {
  nome: 'Arquiteta',
  pele: 's',
  olhos: [4, [4, 7]],
  base: [
    '....kkkk....',
    '...kRRRRk...',
    '..kRRRRRRk..',
    '..kRssssRk..',
    '..kskssksk..',
    '..kRssssRk..',
    '...kssssk...',
    '..kwwccwwk..',
    '.kwwwccwwwk.',
    '.kwwwwwwbbk.',
    '.kswwwwwbbk.',
    '..kwwwwwwk..',
    '..kEEkkEEk..',
    '..kEEk.kEEk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const ENGENHEIRO: Personagem = {
  nome: 'Engenheiro',
  pele: 'd',
  olhos: [4, [4, 7]],
  base: [
    '...kkkkkk...',
    '..kyyyyyyk..',
    '.kyyyyyyyyk.',
    '..kddddddk..',
    '..kdkddkdk..',
    '..kddddddk..',
    '...kddddk...',
    '..koowwook..',
    '.koooooooke.',
    '.koooooookE.',
    '.kdoooooook.',
    '..kooooook..',
    '..kooookook.',
    '..kook.kook.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const ARQUIVISTA: Personagem = {
  nome: 'Arquivista',
  pele: 's',
  olhos: [4, [4, 7]],
  base: [
    '....kkkk....',
    '...keeeek...',
    '..keeeeeek..',
    '..kessssek..',
    '..kskssksk..',
    '..kssssssk..',
    '...kseesk...',
    '..kggmmggk..',
    '.kggmmmmggk.',
    '.kgmmmmmmgk.',
    '.ksmmmmmmsk.',
    '..kmmmmmmk..',
    '..kBBkkBBk..',
    '..kBBk.kBBk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

export const OPERADORA: Personagem = {
  nome: 'Operadora de terminais',
  pele: 's',
  olhos: [4, [4, 7]],
  base: [
    '....kkkk....',
    '...knnnnk...',
    '.kknnnnnnkk.',
    '.kpknssnkpk.',
    '.kpskssksp..',
    '..kssssssk..',
    '...kssssk...',
    '..kppppppk..',
    '.kppppppppk.',
    '.kpppwwpppk.',
    '.kspppppppk.',
    '..kppppppk..',
    '..kBBkkBBk..',
    '..kBBk.kBBk.',
    '..kkkk.kkkk.',
    '............',
  ],
}

/** Dois quadros: parado e piscando. */
export function quadros(p: Personagem): Sprite[] {
  const [linha, colunas] = p.olhos
  const piscando = p.base.map((l, i) => {
    if (i !== linha) return l
    const c = l.split('')
    for (const col of colunas) c[col] = p.pele
    return c.join('')
  })
  return [p.base, piscando]
}

export const TODOS = [GUARDA, COORDENADORA, RECEPCIONISTA, CARTOGRAFA, INSPETORA, ARQUITETA, ENGENHEIRO, ARQUIVISTA, OPERADORA]

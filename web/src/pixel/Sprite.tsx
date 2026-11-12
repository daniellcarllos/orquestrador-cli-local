import { useEffect, useRef } from 'react'
import { PALETA, type Sprite as Grade } from './palette'

interface Props {
  grade: Grade
  escala?: number
  titulo?: string
  className?: string
}

/** Desenha uma grade de caracteres num canvas, sem suavização (pixel perfeito). */
export function Sprite({ grade, escala = 4, titulo, className }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const largura = Math.max(...grade.map((l) => l.length))
  const altura = grade.length

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    grade.forEach((linha, y) => {
      for (let x = 0; x < linha.length; x++) {
        const cor = PALETA[linha[x]]
        if (!cor) continue
        ctx.fillStyle = cor
        ctx.fillRect(x * escala, y * escala, escala, escala)
      }
    })
  }, [grade, escala])

  return (
    <canvas
      ref={ref}
      width={largura * escala}
      height={altura * escala}
      className={className}
      title={titulo}
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      style={{ imageRendering: 'pixelated', display: 'block' }}
    />
  )
}

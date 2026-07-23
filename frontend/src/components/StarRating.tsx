import { useState } from 'react'

interface StarRatingProps {
  value: number | null
  onChange: (value: number | null) => void
  disabled?: boolean
  /** rótulo do botão que limpa a nota (ex.: "sem nota") */
  clearLabel: string
  ariaLabel?: string
}

const STARS = [1, 2, 3, 4, 5] as const
const STAR_PATH =
  'M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z'

function StarShape({ fill }: { fill: 'full' | 'half' | 'empty' }) {
  const width = fill === 'full' ? '100%' : fill === 'half' ? '50%' : '0%'
  return (
    <span className="star-rating__shape" aria-hidden="true">
      <svg viewBox="0 0 24 24" className="star-rating__outline">
        <path d={STAR_PATH} />
      </svg>
      <span className="star-rating__clip" style={{ width }}>
        <svg viewBox="0 0 24 24" className="star-rating__filled">
          <path d={STAR_PATH} />
        </svg>
      </span>
    </span>
  )
}

/* Seleção de nota por estrelas com meia-estrela (0,5 a 5,0). Substitui o
   <select> nativo — no celular o picker do sistema fica feio e fora do estilo.
   Cada estrela tem duas áreas de toque: metade esquerda marca X,5 e a direita
   marca X,0. */
export function StarRating({
  value,
  onChange,
  disabled = false,
  clearLabel,
  ariaLabel,
}: StarRatingProps) {
  const [hover, setHover] = useState<number | null>(null)
  const active = hover ?? value ?? 0

  return (
    <div className="star-rating" role="radiogroup" aria-label={ariaLabel}>
      <div className="star-rating__stars" onMouseLeave={() => setHover(null)}>
        {STARS.map((star) => {
          const fill = active >= star ? 'full' : active >= star - 0.5 ? 'half' : 'empty'
          return (
            <span key={star} className="star-rating__star" data-fill={fill}>
              <StarShape fill={fill} />
              {!disabled && (
                <>
                  <button
                    type="button"
                    className="star-rating__hit star-rating__hit--half"
                    aria-label={(star - 0.5).toFixed(1)}
                    aria-pressed={value === star - 0.5}
                    onClick={() => onChange(star - 0.5)}
                    onMouseEnter={() => setHover(star - 0.5)}
                  />
                  <button
                    type="button"
                    className="star-rating__hit star-rating__hit--full"
                    aria-label={star.toFixed(1)}
                    aria-pressed={value === star}
                    onClick={() => onChange(star)}
                    onMouseEnter={() => setHover(star)}
                  />
                </>
              )}
            </span>
          )
        })}
      </div>
      <div className="star-rating__meta">
        <span className="star-rating__value">
          {value === null ? clearLabel : value.toFixed(1)}
        </span>
        {value !== null && !disabled && (
          <button
            type="button"
            className="star-rating__clear"
            onClick={() => onChange(null)}
          >
            {clearLabel}
          </button>
        )}
      </div>
    </div>
  )
}

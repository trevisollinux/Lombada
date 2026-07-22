import type { CSSProperties } from 'react'

import type { Locale } from '../../i18n'
import type { ShelfReading } from '../../types/reading'
import { formatAuthor } from '../../utils/text'

interface SpineShelfProps {
  readings: ShelfReading[]
  locale: Locale
  onOpen: (reading: ShelfReading) => void
}

/* Mesmo hash do app legado: cor estável por título+autor, para a mesma
   lombada aparecer igual na estante, no share card e no v1. */
function bookHue(title: string, author: string): number {
  const text = `${title} ${author}`
  let hash = 0
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) % 360
  return hash
}

type SpineEra = 'couro' | 'vintage' | 'matte'

interface SpineSpec {
  hue: number
  width: number
  height: number
  era: SpineEra
  lean: number
  sat: number
  lig: number
  foil: string
  page: string
}

function spineSpec(reading: ShelfReading): SpineSpec {
  const hue = bookHue(reading.titulo || '', reading.autor || '')
  const pages = reading.paginas && reading.paginas > 0 ? reading.paginas : 0
  const np = pages ? Math.max(0, Math.min(1, (pages - 80) / 620)) : 0.45
  const width = Math.round(33 + np * 26)
  const height = Math.round(Math.min(210, 154 + ((hue % 100) / 100) * 54 + np * 8))
  // ano da OBRA primeiro, como no v1 — é ele que decide couro/vintage/matte;
  // sem ele toda lombada caía em "matte" (viva demais perto do legado)
  const year = reading.ano_obra ?? reading.ano ?? 0
  const era: SpineEra =
    year > 0 && year < 1970 ? 'couro' : year >= 1970 && year < 2000 ? 'vintage' : 'matte'
  // de vez em quando um livro tomba de leve, como numa estante de verdade
  const lean = hue % 11 === 4 ? (hue % 2 === 0 ? -1 : 1) : 0
  return {
    hue,
    width,
    height,
    era,
    lean,
    sat: era === 'couro' ? 30 : era === 'vintage' ? 42 : 54,
    lig: era === 'couro' ? 26 : era === 'vintage' ? 33 : 42,
    foil: era === 'couro' ? '#e7c877' : era === 'vintage' ? '#f0e6c8' : '#f6f1e6',
    page: era === 'couro' ? '#cdbd92' : era === 'vintage' ? '#e2d9bd' : '#efe9d6',
  }
}

export function SpineShelf({ readings, locale, onOpen }: SpineShelfProps) {
  return (
    <div className="spine-shelf" role="list">
      {readings.map((reading) => {
        const spec = spineSpec(reading)
        const titulo = (reading.titulo || '').trim() || '—'
        const autor = formatAuthor(reading.autor)
        const editora = (reading.editora || '').trim()
        // título auto-ajustado pela altura livre, como nas lombadas reais:
        // título longo fica com letra menor pra caber inteiro
        const zonaAutor = autor ? Math.min(44, Math.round(spec.height * 0.24)) : 10
        const zonaFoot = (editora ? 20 : 0) + (reading.nota ? 14 : 6)
        const tmax = Math.max(40, spec.height - zonaAutor - zonaFoot - 16)
        const tfs = Math.max(8, Math.min(13, Math.round(tmax / Math.max(1, titulo.length) / 0.62)))
        const style = {
          '--w': `${spec.width}px`,
          '--h': `${spec.height}px`,
          '--hue': spec.hue,
          '--sat': `${spec.sat}%`,
          '--lig': `${spec.lig}%`,
          '--foil': spec.foil,
          '--page': spec.page,
          '--tfs': `${tfs}px`,
          '--tmax': `${tmax}px`,
        } as CSSProperties
        return (
          <span className="spine-slot" role="listitem" key={reading.leitura_id}>
            <button
              type="button"
              className="spine"
              data-era={spec.era}
              data-lean={spec.lean !== 0 ? spec.lean : undefined}
              style={style}
              title={autor ? `${titulo} — ${autor}` : titulo}
              onClick={() => onOpen(reading)}
            >
              {autor && <span className="spine__author">{autor}</span>}
              <span className="spine__title">{titulo}</span>
              {(editora || reading.nota) && (
                <span className="spine__foot">
                  {editora && <span className="spine__publisher">{editora}</span>}
                  {reading.nota ? (
                    <span className="spine__stars">★ {reading.nota.toLocaleString(locale)}</span>
                  ) : null}
                </span>
              )}
              {reading.status === 'Lendo' && <span className="spine__ribbon" aria-hidden="true" />}
            </button>
          </span>
        )
      })}
    </div>
  )
}

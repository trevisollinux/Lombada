import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import type { ShelfReading, ShelfView } from '../../types/reading'
import { shelfText } from './shelfI18n'
import { formatAuthor } from '../../utils/text'

interface ShelfBookCardProps {
  reading: ShelfReading
  view: ShelfView
  locale: Locale
  onOpen: (reading: ShelfReading) => void
}

function stars(rating: number | null): string {
  if (rating === null || rating <= 0) return ''
  const full = Math.floor(rating)
  const half = rating - full >= 0.5
  return `${'★'.repeat(full)}${half ? '½' : ''}`
}

function statusSlug(status: string): string {
  const normalized = status.trim().toLowerCase()
  if (normalized === 'lido') return 'lido'
  if (normalized === 'lendo') return 'lendo'
  if (normalized === 'quero ler') return 'quero'
  return 'outro'
}

export function ShelfBookCard({ reading, view, locale, onOpen }: ShelfBookCardProps) {
  const meta = [reading.editora, reading.ano, reading.tradutor].filter(Boolean)
  const rating = stars(reading.nota)

  return (
    <article className={`shelf-book shelf-book--${view}`}>
      <button
        className="shelf-book__open"
        type="button"
        onClick={() => onOpen(reading)}
        aria-label={`${shelfText(locale, 'open_detail')}: ${reading.titulo}`}
      >
        <BookCover
          title={reading.titulo}
          author={reading.autor}
          url={reading.capa_url}
          className="shelf-book__cover"
        />
        <span className="shelf-book__body">
          <span className={`shelf-book__status shelf-book__status--${statusSlug(reading.status)}`}>
            {reading.status}
          </span>
          <strong>{reading.titulo}</strong>
          <span className="shelf-book__author">{formatAuthor(reading.autor) || '—'}</span>
          {meta.length > 0 && <span className="shelf-book__meta">{meta.join(' · ')}</span>}
          <span className="shelf-book__footer">
            <span className={rating ? 'shelf-book__rating' : 'shelf-book__rating is-empty'}>
              {rating || shelfText(locale, 'no_rating')}
            </span>
            <Icon name="arrow" size={17} />
          </span>
        </span>
      </button>
    </article>
  )
}

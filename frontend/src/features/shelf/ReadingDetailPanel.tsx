import { useEffect } from 'react'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import type { ShelfReading } from '../../types/reading'
import { shelfText } from './shelfI18n'

interface ReadingDetailPanelProps {
  reading: ShelfReading | null
  locale: Locale
  onClose: () => void
}

function ratingLabel(value: number | null): string {
  if (value === null) return '—'
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function ReadingDetailPanel({ reading, locale, onClose }: ReadingDetailPanelProps) {
  useEffect(() => {
    if (!reading) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previous
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose, reading])

  if (!reading) return null

  const editionMeta = [
    reading.editora,
    reading.ano,
    reading.idioma,
    reading.paginas ? `${reading.paginas} ${shelfText(locale, 'pages')}` : '',
  ].filter(Boolean)

  return (
    <div className="reading-detail-layer">
      <button
        className="reading-detail-backdrop"
        type="button"
        aria-label={shelfText(locale, 'close_detail')}
        onClick={onClose}
      />
      <aside
        className="reading-detail"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reading-detail-title"
      >
        <div className="reading-detail__topbar">
          <span className="reading-detail__status">{reading.status}</span>
          <button className="icon-button" type="button" onClick={onClose}>
            <Icon name="close" />
            <span className="sr-only">{shelfText(locale, 'close_detail')}</span>
          </button>
        </div>

        <div className="reading-detail__hero">
          <BookCover
            title={reading.titulo}
            author={reading.autor}
            url={reading.capa_url}
            className="reading-detail__cover"
          />
          <div>
            <p className="eyebrow">{shelfText(locale, 'edition')}</p>
            <h2 id="reading-detail-title">{reading.titulo}</h2>
            <p className="reading-detail__author">{reading.autor || '—'}</p>
            {editionMeta.length > 0 && (
              <p className="reading-detail__edition-meta">{editionMeta.join(' · ')}</p>
            )}
          </div>
        </div>

        <dl className="reading-detail__facts">
          <div>
            <dt>{shelfText(locale, 'rating')}</dt>
            <dd>{ratingLabel(reading.nota)}</dd>
          </div>
          <div>
            <dt>{shelfText(locale, 'publisher')}</dt>
            <dd>{reading.editora || '—'}</dd>
          </div>
          <div>
            <dt>{shelfText(locale, 'translator')}</dt>
            <dd>{reading.tradutor || '—'}</dd>
          </div>
          <div>
            <dt>{shelfText(locale, 'isbn')}</dt>
            <dd>{reading.isbn || '—'}</dd>
          </div>
        </dl>

        <section className="reading-detail__review">
          <div className="reading-detail__section-heading">
            <h3>{shelfText(locale, 'review')}</h3>
            <div className="reading-detail__badges">
              <span>{reading.publico ? shelfText(locale, 'public_review') : shelfText(locale, 'private_review')}</span>
              {reading.spoiler && <span className="is-warning">{shelfText(locale, 'spoiler')}</span>}
            </div>
          </div>
          <p>{reading.relato || shelfText(locale, 'no_review')}</p>
        </section>

        {(reading.tenho_edicao || reading.quero_edicao) && (
          <div className="reading-detail__relations">
            {reading.tenho_edicao && <span>{shelfText(locale, 'owned')}</span>}
            {reading.quero_edicao && <span>{shelfText(locale, 'wanted')}</span>}
          </div>
        )}

        <a className="button button--secondary reading-detail__legacy" href="/">
          {shelfText(locale, 'open_legacy')}
          <Icon name="external" size={16} />
        </a>
      </aside>
    </div>
  )
}

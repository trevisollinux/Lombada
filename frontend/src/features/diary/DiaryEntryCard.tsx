import { useState } from 'react'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import { memoriesText } from '../memories/memoriesI18n'
import type { Locale } from '../../i18n'
import { deleteDiaryEntry } from '../../services/api'
import type { DiaryEntry } from '../../types/diary'
import { diaryText } from './diaryI18n'

interface DiaryEntryCardProps {
  entry: DiaryEntry
  locale: Locale
  onEdit: (entry: DiaryEntry) => void
  onShare: (entry: DiaryEntry) => void
  onDeleted: (entryId: number) => void
}

function parseUtcDate(value: string): Date {
  if (!value) return new Date(Number.NaN)
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

function progressSummary(entry: DiaryEntry, locale: Locale): string {
  if (entry.progresso_tipo === 'pagina' && entry.pagina) {
    return `${diaryText(locale, 'page')} ${entry.pagina}`
  }
  if (entry.progresso_tipo === 'porcentagem' && entry.porcentagem !== null) {
    return `${entry.porcentagem}%`
  }
  if (entry.progresso_tipo === 'capitulo' && entry.capitulo) {
    return entry.capitulo
  }
  return diaryText(locale, 'free')
}

export function DiaryEntryCard({ entry, locale, onEdit, onShare, onDeleted }: DiaryEntryCardProps) {
  const [deleteArmed, setDeleteArmed] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const date = parseUtcDate(entry.created_at)
  const dateLabel = Number.isNaN(date.getTime())
    ? ''
    : new Intl.DateTimeFormat(locale, {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(date)

  async function handleDelete() {
    if (!deleteArmed) {
      setDeleteArmed(true)
      setError(null)
      return
    }
    if (deleting) return

    setDeleting(true)
    setError(null)
    try {
      await deleteDiaryEntry(entry.id)
      onDeleted(entry.id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : diaryText(locale, 'delete_error'))
      setDeleteArmed(false)
      setDeleting(false)
    }
  }

  const delta = entry.paginas_delta

  return (
    <article className="diary-entry">
      <div className="diary-entry__date" aria-hidden="true">
        <strong>{Number.isNaN(date.getTime()) ? '—' : String(date.getDate()).padStart(2, '0')}</strong>
        <span>{Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat(locale, { month: 'short' }).format(date)}</span>
      </div>

      <span className="diary-entry__line" aria-hidden="true" />

      <div className="diary-entry__card">
        <div className="diary-entry__book">
          <BookCover
            title={entry.titulo || 'Lombada'}
            author={entry.autor || ''}
            url={entry.capa_url}
            className="diary-entry__cover"
          />
          <div>
            <p className="eyebrow">{progressSummary(entry, locale)}</p>
            <h2>{entry.titulo || 'Lombada'}</h2>
            <p>{entry.autor || '—'}</p>
          </div>
        </div>

        <div className="diary-entry__meta">
          <time dateTime={entry.created_at}>{dateLabel}</time>
          <span>{entry.publico ? diaryText(locale, 'public') : diaryText(locale, 'private')}</span>
          {entry.spoiler && <span className="is-warning">{diaryText(locale, 'spoiler')}</span>}
          {entry.origem === 'li_mais' && <span>{diaryText(locale, 'origin_more')}</span>}
        </div>

        {entry.progresso_tipo === 'capitulo' && entry.pagina_estimada && (
          <p className="diary-entry__estimate">
            {diaryText(locale, 'estimated_page')}: {entry.pagina_estimada}
          </p>
        )}

        {delta !== null && delta !== 0 && (
          <p className="diary-entry__delta">
            {Math.abs(delta)} {delta > 0 ? diaryText(locale, 'pages_advanced') : diaryText(locale, 'pages_returned')}
          </p>
        )}

        <p className={`diary-entry__note${entry.nota ? '' : ' is-empty'}`}>
          {entry.nota || diaryText(locale, 'no_note')}
        </p>

        {error && <p className="diary-entry__error" role="alert">{error}</p>}

        <div className="diary-entry__actions">
          <button type="button" className="text-button" onClick={() => onShare(entry)} disabled={deleting}>
            <Icon name="memory" size={15} />
            {memoriesText(locale, 'share_card')}
          </button>
          <button type="button" className="text-button" onClick={() => onEdit(entry)} disabled={deleting}>
            {diaryText(locale, 'edit')}
          </button>
          {deleteArmed && (
            <button type="button" className="text-button" onClick={() => setDeleteArmed(false)} disabled={deleting}>
              {diaryText(locale, 'keep')}
            </button>
          )}
          <button
            type="button"
            className={`diary-entry__remove${deleteArmed ? ' is-armed' : ''}`}
            onClick={() => void handleDelete()}
            disabled={deleting}
          >
            {deleting
              ? diaryText(locale, 'removing')
              : deleteArmed
                ? diaryText(locale, 'confirm_remove')
                : diaryText(locale, 'remove')}
          </button>
        </div>
      </div>
    </article>
  )
}

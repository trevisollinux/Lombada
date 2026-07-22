import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import type { ReadingProgressSummary } from '../../types/features'
import type { ShelfReading } from '../../types/reading'
import { getReadingProgress } from './progressApi'
import { ProgressQuickDialog } from './ProgressQuickDialog'
import { progressText } from './progressI18n'
import { formatAuthor } from '../../utils/text'

interface ReadingRitualCardProps {
  reading: ShelfReading
  locale: Locale
}

export function ReadingRitualCard({ reading, locale }: ReadingRitualCardProps) {
  const [summary, setSummary] = useState<ReadingProgressSummary | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setSummary(await getReadingProgress(reading.leitura_id, signal))
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      setSummary(null)
    }
  }, [reading.leitura_id])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const progressLabel = summary?.pagina_atual !== null && summary?.pagina_atual !== undefined
    ? summary.paginas_total
      ? progressText(locale, 'page_of', { current: summary.pagina_atual, total: summary.paginas_total })
      : `${progressText(locale, 'page')} ${summary.pagina_atual}`
    : summary?.porcentagem !== null && summary?.porcentagem !== undefined
      ? progressText(locale, 'percent_complete', { value: summary.porcentagem })
      : null

  return (
    <>
      <section className="reading-ritual" aria-labelledby="reading-ritual-title">
        <BookCover title={reading.titulo} author={reading.autor} url={reading.capa_url} className="reading-ritual__cover" />
        <div className="reading-ritual__copy">
          <p className="eyebrow">{progressText(locale, 'continue_reading')}</p>
          <h2 id="reading-ritual-title">{reading.titulo}</h2>
          <p className="reading-ritual__author">{formatAuthor(reading.autor) || '—'}</p>
          {progressLabel && <strong className="reading-ritual__position">{progressLabel}</strong>}
          <div className="reading-ritual__metrics">
            {summary && <span>{summary.sessoes} {progressText(locale, 'sessions')}</span>}
            {summary?.paginas_7d !== null && summary?.paginas_7d !== undefined && (
              <span>{summary.paginas_7d} {progressText(locale, 'pages_last_week')}</span>
            )}
            {summary?.paginas_restantes !== null && summary?.paginas_restantes !== undefined && (
              <span>{progressText(locale, 'remaining', { value: summary.paginas_restantes })}</span>
            )}
          </div>
          <p>{progressText(locale, 'continue_copy')}</p>
          <div className="reading-ritual__actions">
            <button className="button button--primary" type="button" onClick={() => setDialogOpen(true)}>
              <Icon name="plus" size={17} />
              {progressText(locale, 'log_more')}
            </button>
            <Link className="button button--secondary" to="/diario">
              {progressText(locale, 'open_diary')}
            </Link>
          </div>
        </div>
      </section>

      <ProgressQuickDialog
        reading={dialogOpen ? reading : null}
        locale={locale}
        onClose={() => setDialogOpen(false)}
        onLogged={() => void load()}
      />
    </>
  )
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { BookCover } from '../components/BookCover'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { buildLibraryRecap, periodLabel, progressLabel } from '../features/memories/memoryData'
import { memoriesText } from '../features/memories/memoriesI18n'
import { ShareCardDialog } from '../features/memories/ShareCardDialog'
import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'
import { ApiError, getPeriodRecap, getShelf } from '../services/api'
import type { PeriodRecap, RecapPeriod, ShareCardPayload } from '../types/memories'
import type { ShelfReading } from '../types/reading'

const MAX_OFFSET = 12

export function MemoriesPage() {
  const { locale, t } = usePreferences()
  const { account } = useSession()
  const [readings, setReadings] = useState<ShelfReading[]>([])
  const [shelfStatus, setShelfStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [shelfError, setShelfError] = useState<string | null>(null)
  const [period, setPeriod] = useState<RecapPeriod>('week')
  const [offset, setOffset] = useState(0)
  const [recap, setRecap] = useState<PeriodRecap | null>(null)
  const [recapStatus, setRecapStatus] = useState<'loading' | 'ready' | 'unavailable' | 'error'>('loading')
  const [recapError, setRecapError] = useState<string | null>(null)
  const [recapReloadVersion, setRecapReloadVersion] = useState(0)
  const [sharePayload, setSharePayload] = useState<ShareCardPayload | null>(null)

  const libraryRecap = useMemo(() => buildLibraryRecap(readings), [readings])
  const handle = account?.handle || ''

  const loadShelf = useCallback(async (signal?: AbortSignal) => {
    setShelfStatus('loading')
    setShelfError(null)
    try {
      const payload = await getShelf(signal)
      setReadings(Array.isArray(payload) ? payload : [])
      setShelfStatus('ready')
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      setShelfError(cause instanceof Error ? cause.message : memoriesText(locale, 'card_error'))
      setShelfStatus('error')
    }
  }, [locale])

  useEffect(() => {
    const controller = new AbortController()
    void loadShelf(controller.signal)
    return () => controller.abort()
  }, [loadShelf])

  useEffect(() => {
    const controller = new AbortController()
    setRecapStatus('loading')
    setRecapError(null)
    void getPeriodRecap(period, offset, controller.signal)
      .then((payload) => {
        setRecap(payload)
        setRecapStatus('ready')
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setRecap(null)
        if (cause instanceof ApiError && cause.status === 404) {
          setRecapStatus('unavailable')
          return
        }
        setRecapError(cause instanceof Error ? cause.message : memoriesText(locale, 'card_error'))
        setRecapStatus('error')
      })
    return () => controller.abort()
  }, [locale, offset, period, recapReloadVersion])

  function changePeriod(next: RecapPeriod) {
    setPeriod(next)
    setOffset(0)
  }

  function navigatePeriod(delta: number) {
    setOffset((current) => Math.max(0, Math.min(MAX_OFFSET, current + delta)))
  }

  const periodTitle = recap?.is_current
    ? memoriesText(locale, recap.period === 'week' ? 'current_week' : 'current_month')
    : memoriesText(locale, 'period_title')

  return (
    <section className="page page--memories">
      <PageHeader
        eyebrow={memoriesText(locale, 'eyebrow')}
        title={memoriesText(locale, 'title')}
        description={memoriesText(locale, 'copy')}
        aside={<span className="stage-stamp">10 · compartilhar</span>}
      />

      <section className="memories-period" aria-labelledby="memories-period-title">
        <header className="memories-section-heading">
          <div>
            <p className="eyebrow">{memoriesText(locale, 'eyebrow')}</p>
            <h2 id="memories-period-title">{memoriesText(locale, 'period_title')}</h2>
            <p>{memoriesText(locale, 'period_copy')}</p>
          </div>
          <div className="memories-period-tabs" role="tablist">
            {(['week', 'month'] as RecapPeriod[]).map((value) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={period === value}
                className={period === value ? 'is-active' : ''}
                onClick={() => changePeriod(value)}
              >
                {memoriesText(locale, value)}
              </button>
            ))}
          </div>
        </header>

        {recapStatus === 'loading' && <PeriodLoading />}

        {recapStatus === 'unavailable' && (
          <div className="memories-state">
            <Icon name="diary" size={30} />
            <p>{memoriesText(locale, 'period_unavailable')}</p>
          </div>
        )}

        {recapStatus === 'error' && (
          <div className="memories-state memories-state--error" role="alert">
            <Icon name="refresh" size={30} />
            <p>{recapError}</p>
            <button className="button button--secondary" type="button" onClick={() => setRecapReloadVersion((current) => current + 1)}>
              <Icon name="refresh" size={16} />
              {t('retry')}
            </button>
          </div>
        )}

        {recapStatus === 'ready' && recap && (
          <>
            <div className="memories-period-nav">
              <button
                type="button"
                disabled={!recap.can_go_older}
                aria-label={memoriesText(locale, 'previous')}
                onClick={() => navigatePeriod(1)}
              >
                ←
              </button>
              <div>
                <strong>{periodTitle}</strong>
                <span>{periodLabel(recap, locale)} · {memoriesText(locale, recap.is_complete ? 'completed_period' : 'period_in_progress')}</span>
              </div>
              <button
                type="button"
                disabled={!recap.can_go_newer}
                aria-label={memoriesText(locale, 'next')}
                onClick={() => navigatePeriod(-1)}
              >
                →
              </button>
            </div>

            {recap.state === 'empty' ? (
              <div className="memories-state memories-state--empty">
                <span aria-hidden="true">◌</span>
                <p>{memoriesText(locale, recap.is_current ? 'period_empty_current' : 'period_empty_past')}</p>
                <Link className="button button--secondary" to="/diario">{memoriesText(locale, 'open_diary')}</Link>
              </div>
            ) : (
              <>
                <div className="memories-metrics">
                  <MemoryMetric value={recap.sessions} label={memoriesText(locale, 'sessions')} locale={locale} />
                  <MemoryMetric value={recap.active_days} label={memoriesText(locale, 'active_days')} locale={locale} />
                  <MemoryMetric value={recap.books_touched} label={memoriesText(locale, 'books_touched')} locale={locale} />
                  <MemoryMetric
                    value={recap.page_sessions_calculable > 0 ? recap.pages_advanced : recap.sessions}
                    label={memoriesText(locale, recap.page_sessions_calculable > 0 ? 'pages_advanced' : 'updates')}
                    locale={locale}
                    emphasis
                  />
                </div>

                {recap.highlights.length > 0 && (
                  <div className="memories-period-books">
                    <h3>{memoriesText(locale, 'highlights')}</h3>
                    <div>
                      {recap.highlights.map((book) => {
                        const progress = progressLabel(book.last_progress, locale)
                        return (
                          <article key={book.reading_id}>
                            <BookCover title={book.title} author={book.author} url={book.cover_url} />
                            <div>
                              <h4>{book.title}</h4>
                              <p>{book.author}</p>
                              <small>
                                {book.sessions.toLocaleString(locale)} {memoriesText(locale, 'sessions')}
                                {book.pages_advanced > 0 ? ` · +${book.pages_advanced.toLocaleString(locale)} ${memoriesText(locale, 'pages_advanced')}` : ''}
                                {progress ? ` · ${progress}` : ''}
                              </small>
                            </div>
                          </article>
                        )
                      })}
                    </div>
                  </div>
                )}

                <div className="memories-actions">
                  <button
                    className="button button--primary"
                    type="button"
                    onClick={() => setSharePayload({ kind: 'period', recap, handle })}
                  >
                    {memoriesText(locale, 'share_card')}
                  </button>
                  <Link className="button button--secondary" to="/diario">{memoriesText(locale, 'open_diary')}</Link>
                </div>
              </>
            )}
          </>
        )}
      </section>

      <section className="memories-library" aria-labelledby="memories-library-title">
        <header className="memories-section-heading">
          <div>
            <p className="eyebrow">{memoriesText(locale, 'eyebrow')}</p>
            <h2 id="memories-library-title">{memoriesText(locale, 'library_title')}</h2>
            <p>{memoriesText(locale, 'library_copy')}</p>
          </div>
        </header>

        {shelfStatus === 'loading' && <LibraryLoading />}

        {shelfStatus === 'error' && (
          <div className="memories-state memories-state--error" role="alert">
            <p>{shelfError}</p>
            <button className="button button--secondary" type="button" onClick={() => void loadShelf()}>
              <Icon name="refresh" size={16} />
              {t('retry')}
            </button>
          </div>
        )}

        {shelfStatus === 'ready' && libraryRecap.readBooks.length === 0 && (
          <div className="memories-state memories-state--empty">
            <span aria-hidden="true">◇</span>
            <p>{memoriesText(locale, 'library_empty')}</p>
            <Link className="button button--secondary" to="/estante">{memoriesText(locale, 'library_title')}</Link>
          </div>
        )}

        {shelfStatus === 'ready' && libraryRecap.readBooks.length > 0 && (
          <>
            <div className="library-recap-hero">
              <div className="library-recap-number">
                <strong>{libraryRecap.readBooks.length}</strong>
                <span>{memoriesText(locale, 'books_read')}</span>
              </div>
              <div className="library-recap-covers">
                {libraryRecap.readBooks.slice(0, 7).map((reading) => (
                  <BookCover key={reading.leitura_id} title={reading.titulo} author={reading.autor} url={reading.capa_url} />
                ))}
              </div>
            </div>

            <div className="library-recap-facts">
              {libraryRecap.pages > 0 && (
                <article><span>{memoriesText(locale, 'pages_read')}</span><strong>{libraryRecap.pages.toLocaleString(locale)}</strong></article>
              )}
              {libraryRecap.topAuthor && (
                <article><span>{memoriesText(locale, 'top_author')}</span><strong>{libraryRecap.topAuthor.name}</strong><small>{libraryRecap.topAuthor.books.length.toLocaleString(locale)} {memoriesText(locale, 'books_read')}</small></article>
              )}
              {libraryRecap.averageRating !== null && (
                <article><span>{memoriesText(locale, 'average_rating')}</span><strong>{libraryRecap.averageRating.toLocaleString(locale, { maximumFractionDigits: 1 })}</strong></article>
              )}
              {libraryRecap.favorite && (
                <article><span>{memoriesText(locale, 'favorite')}</span><strong>{libraryRecap.favorite.titulo}</strong><small>{libraryRecap.favorite.autor}</small></article>
              )}
            </div>

            <div className="memories-actions">
              <button
                className="button button--primary"
                type="button"
                onClick={() => setSharePayload({ kind: 'library', recap: libraryRecap, handle })}
              >
                {memoriesText(locale, 'share_card')}
              </button>
              <Link className="button button--secondary" to="/estante">{memoriesText(locale, 'library_title')}</Link>
            </div>
          </>
        )}
      </section>

      <ShareCardDialog payload={sharePayload} locale={locale} onClose={() => setSharePayload(null)} />
    </section>
  )
}

function MemoryMetric({
  value,
  label,
  locale,
  emphasis = false,
}: {
  value: number
  label: string
  locale: string
  emphasis?: boolean
}) {
  return (
    <article className={emphasis ? 'is-emphasis' : ''}>
      <strong>{value.toLocaleString(locale)}</strong>
      <span>{label}</span>
    </article>
  )
}

function PeriodLoading() {
  return (
    <div className="memories-loading" aria-busy="true">
      <span className="memories-loading__nav" />
      <div className="memories-loading__metrics">{Array.from({ length: 4 }, (_, index) => <i key={index} />)}</div>
      <div className="memories-loading__books">{Array.from({ length: 4 }, (_, index) => <i key={index} />)}</div>
    </div>
  )
}

function LibraryLoading() {
  return (
    <div className="library-recap-loading" aria-busy="true">
      <strong />
      <div>{Array.from({ length: 5 }, (_, index) => <i key={index} />)}</div>
    </div>
  )
}

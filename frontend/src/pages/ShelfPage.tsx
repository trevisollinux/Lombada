import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { ReadingDetailPanel } from '../features/shelf/ReadingDetailPanel'
import { ShelfBookCard } from '../features/shelf/ShelfBookCard'
import { shelfText, type ShelfTextKey } from '../features/shelf/shelfI18n'
import { usePreferences } from '../providers/PreferencesProvider'
import { getShelf } from '../services/api'
import type { ShelfReading, ShelfView } from '../types/reading'

const VIEW_KEY = 'lombada_view_estante'

type ShelfFilter = 'all' | 'read' | 'reading' | 'want' | 'other'

interface FilterOption {
  id: ShelfFilter
  label: ShelfTextKey
  matches: (status: string) => boolean
}

const filters: FilterOption[] = [
  { id: 'all', label: 'all', matches: () => true },
  { id: 'read', label: 'read', matches: (status) => status === 'Lido' },
  { id: 'reading', label: 'reading', matches: (status) => status === 'Lendo' },
  { id: 'want', label: 'want', matches: (status) => status === 'Quero ler' },
  {
    id: 'other',
    label: 'other',
    matches: (status) => !['Lido', 'Lendo', 'Quero ler'].includes(status),
  },
]

function initialView(): ShelfView {
  return localStorage.getItem(VIEW_KEY) === 'list' || localStorage.getItem(VIEW_KEY) === 'lista'
    ? 'list'
    : 'grid'
}

export function ShelfPage() {
  const { locale, t } = usePreferences()
  const [readings, setReadings] = useState<ShelfReading[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<ShelfFilter>('all')
  const [view, setViewState] = useState<ShelfView>(initialView)
  const [selected, setSelected] = useState<ShelfReading | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading')
    setError(null)
    try {
      const payload = await getShelf(signal)
      setReadings(Array.isArray(payload) ? payload : [])
      setStatus('ready')
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      setError(cause instanceof Error ? cause.message : shelfText(locale, 'error'))
      setStatus('error')
    }
  }, [locale])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const counts = useMemo(() => {
    return Object.fromEntries(
      filters.map((option) => [
        option.id,
        readings.filter((reading) => option.matches(reading.status)).length,
      ]),
    ) as Record<ShelfFilter, number>
  }, [readings])

  const visibleReadings = useMemo(() => {
    const active = filters.find((option) => option.id === filter) ?? filters[0]
    return readings.filter((reading) => active.matches(reading.status))
  }, [filter, readings])

  function setView(nextView: ShelfView) {
    setViewState(nextView)
    localStorage.setItem(VIEW_KEY, nextView === 'list' ? 'lista' : 'grade')
  }

  return (
    <section className="page page--shelf">
      <PageHeader
        eyebrow={t('shelf_eyebrow')}
        title={t('shelf_title')}
        description={
          status === 'ready'
            ? `${readings.length} ${shelfText(locale, 'books_count')}`
            : t('shelf_copy')
        }
        aside={<span className="stage-stamp">03 · dados reais</span>}
      />

      <div className="shelf-toolbar">
        <div className="shelf-filters" role="group" aria-label={t('shelf_title')}>
          {filters.map((option) => {
            const count = counts[option.id]
            if (option.id === 'other' && count === 0) return null
            return (
              <button
                key={option.id}
                type="button"
                className={filter === option.id ? 'is-active' : ''}
                aria-pressed={filter === option.id}
                onClick={() => setFilter(option.id)}
              >
                <span>{shelfText(locale, option.label)}</span>
                <small>{count}</small>
              </button>
            )
          })}
        </div>

        <div className="shelf-view-toggle" role="group" aria-label="Visualização">
          <button
            type="button"
            className={view === 'grid' ? 'is-active' : ''}
            aria-pressed={view === 'grid'}
            onClick={() => setView('grid')}
          >
            <span className="view-icon view-icon--grid" aria-hidden="true"><i /><i /><i /><i /></span>
            <span className="sr-only">{shelfText(locale, 'grid')}</span>
          </button>
          <button
            type="button"
            className={view === 'list' ? 'is-active' : ''}
            aria-pressed={view === 'list'}
            onClick={() => setView('list')}
          >
            <span className="view-icon view-icon--list" aria-hidden="true"><i /><i /><i /></span>
            <span className="sr-only">{shelfText(locale, 'list')}</span>
          </button>
        </div>
      </div>

      {status === 'loading' && (
        <div className={`shelf-books shelf-books--${view}`} aria-busy="true" aria-label={shelfText(locale, 'loading')}>
          {Array.from({ length: view === 'grid' ? 6 : 4 }, (_, index) => (
            <article className={`shelf-book-skeleton shelf-book-skeleton--${view}`} key={index}>
              <span className="shelf-book-skeleton__cover" />
              <span className="shelf-book-skeleton__copy"><i /><i /><i /></span>
            </article>
          ))}
        </div>
      )}

      {status === 'error' && (
        <section className="shelf-state shelf-state--error" role="alert">
          <Icon name="refresh" size={30} />
          <h2>{shelfText(locale, 'error')}</h2>
          <p>{error}</p>
          <button className="button button--secondary" type="button" onClick={() => void load()}>
            <Icon name="refresh" size={17} />
            {t('retry')}
          </button>
        </section>
      )}

      {status === 'ready' && readings.length === 0 && (
        <section className="shelf-state shelf-state--empty">
          <div className="book-spines" aria-hidden="true">
            <span /><span /><span /><span /><span />
          </div>
          <div>
            <p className="eyebrow">{t('shelf_eyebrow')}</p>
            <h2>{shelfText(locale, 'empty_title')}</h2>
            <p>{shelfText(locale, 'empty_copy')}</p>
            <Link className="button button--primary" to="/">
              {shelfText(locale, 'register')}
              <Icon name="arrow" size={17} />
            </Link>
          </div>
        </section>
      )}

      {status === 'ready' && readings.length > 0 && visibleReadings.length === 0 && (
        <section className="shelf-state shelf-state--filtered">
          <p>{shelfText(locale, 'empty_filtered')}</p>
          <button className="text-button" type="button" onClick={() => setFilter('all')}>
            {shelfText(locale, 'all')}
          </button>
        </section>
      )}

      {status === 'ready' && visibleReadings.length > 0 && (
        <div className={`shelf-books shelf-books--${view}`}>
          {visibleReadings.map((reading) => (
            <ShelfBookCard
              key={reading.leitura_id}
              reading={reading}
              view={view}
              locale={locale}
              onOpen={setSelected}
            />
          ))}
        </div>
      )}

      <ReadingDetailPanel reading={selected} locale={locale} onClose={() => setSelected(null)} />
    </section>
  )
}

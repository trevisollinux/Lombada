import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { ReadingDetailPanel } from '../features/shelf/ReadingDetailPanel'
import { ShelfBookCard } from '../features/shelf/ShelfBookCard'
import { SpineShelf } from '../features/shelf/SpineShelf'
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
  const stored = localStorage.getItem(VIEW_KEY)
  if (stored === 'list' || stored === 'lista') return 'list'
  if (stored === 'spines' || stored === 'lombadas') return 'spines'
  return 'grid'
}

export function ShelfPage() {
  const { locale, t } = usePreferences()
  const [readings, setReadings] = useState<ShelfReading[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<ShelfFilter>('all')
  const [filterMenuOpen, setFilterMenuOpen] = useState(false)
  const [view, setViewState] = useState<ShelfView>(initialView)
  const [selected, setSelected] = useState<ShelfReading | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

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

  useEffect(() => {
    if (!filterMenuOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setFilterMenuOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [filterMenuOpen])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 3500)
    return () => window.clearTimeout(timer)
  }, [notice])

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
    localStorage.setItem(
      VIEW_KEY,
      nextView === 'list' ? 'lista' : nextView === 'spines' ? 'lombadas' : 'grade',
    )
  }

  function handleUpdated(updated: ShelfReading) {
    setReadings((current) => current.map((reading) => (
      reading.leitura_id === updated.leitura_id ? updated : reading
    )))
    setSelected(updated)
    setNotice(shelfText(locale, 'saved_success'))
  }

  function handleDeleted(readingId: number) {
    setReadings((current) => current.filter((reading) => reading.leitura_id !== readingId))
    setSelected(null)
    setNotice(shelfText(locale, 'deleted_success'))
  }

  return (
    <section className="page page--shelf">
      <PageHeader
        title={t('shelf_title')}
        description={
          status === 'ready'
            ? `${readings.length} ${shelfText(locale, 'books_count')}`
            : t('shelf_copy')
        }
      />

      {/* como no v1, estante e diário são irmãos no mesmo segmento */}
      <div className="shelf-diary-segment" role="tablist" aria-label={t('shelf_title')}>
        <span className="shelf-diary-segment__btn is-active" role="tab" aria-selected="true">
          {t('shelf_title')}
        </span>
        <Link className="shelf-diary-segment__btn" role="tab" aria-selected="false" to="/diario">
          {t('diary_title')}
        </Link>
      </div>

      {status === 'ready' && readings.length > 0 && (
        <p className="shelf-summary">
          {readings.length} {shelfText(locale, 'books_count')}
          {' · '}{counts.read} {shelfText(locale, 'read').toLocaleLowerCase(locale)}
          {' · '}{counts.reading} {shelfText(locale, 'reading').toLocaleLowerCase(locale)}
          {' · '}{counts.want} {shelfText(locale, 'want').toLocaleLowerCase(locale)}
        </p>
      )}

      {notice && (
        <div className="shelf-notice" role="status" aria-live="polite">
          {notice}
        </div>
      )}

      <div className="shelf-toolbar">
        <div className="shelf-filter-menu">
          <button
            type="button"
            className="shelf-filter-menu__trigger"
            aria-haspopup="listbox"
            aria-expanded={filterMenuOpen}
            onClick={() => setFilterMenuOpen((current) => !current)}
          >
            <span>{shelfText(locale, (filters.find((option) => option.id === filter) ?? filters[0]).label)}</span>
            <small>{counts[filter]}</small>
            <Icon name="chevron-down" size={14} />
          </button>
          {filterMenuOpen && (
            <>
              <button
                className="shelf-filter-menu__backdrop"
                type="button"
                aria-label={t('close')}
                onClick={() => setFilterMenuOpen(false)}
              />
              <div className="shelf-filter-menu__list" role="listbox" aria-label={t('shelf_title')}>
                {filters.map((option) => {
                  const count = counts[option.id]
                  if (option.id === 'other' && count === 0) return null
                  return (
                    <button
                      key={option.id}
                      type="button"
                      role="option"
                      aria-selected={filter === option.id}
                      className={filter === option.id ? 'is-active' : ''}
                      onClick={() => {
                        setFilter(option.id)
                        setFilterMenuOpen(false)
                      }}
                    >
                      <span>{shelfText(locale, option.label)}</span>
                      <small>{count}</small>
                    </button>
                  )
                })}
              </div>
            </>
          )}
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
          <button
            type="button"
            className={view === 'spines' ? 'is-active' : ''}
            aria-pressed={view === 'spines'}
            onClick={() => setView('spines')}
          >
            <span className="view-icon view-icon--spines" aria-hidden="true"><i /><i /><i /><i /></span>
            <span className="sr-only">{shelfText(locale, 'spines')}</span>
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
        view === 'spines' ? (
          <SpineShelf readings={visibleReadings} locale={locale} onOpen={setSelected} />
        ) : (
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
        )
      )}

      <ReadingDetailPanel
        reading={selected}
        locale={locale}
        onClose={() => setSelected(null)}
        onUpdated={handleUpdated}
        onDeleted={handleDeleted}
      />
    </section>
  )
}

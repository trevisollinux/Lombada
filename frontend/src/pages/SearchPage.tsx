import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { SearchResultCard } from '../features/catalog/SearchResultCard'
import {
  SearchFilterSheet,
  countActiveFilters,
  type SearchFilters,
} from '../features/catalog/SearchFilterSheet'
import { ManualBookForm } from '../features/catalog/ManualBookForm'
import { catalogText } from '../features/catalog/catalogI18n'
import { manualText } from '../features/catalog/manualI18n'
import { exploreText } from '../features/explore/exploreI18n'
import {
  ONBOARDING_DISMISSED,
  ONBOARDING_MARKER,
  OnboardingValueCard,
} from '../features/progress/OnboardingValueCard'
import { ReadingRitualCard } from '../features/progress/ReadingRitualCard'
import { useFeatureFlags } from '../providers/FeatureFlagsProvider'
import { usePreferences } from '../providers/PreferencesProvider'
import { trackProductEvent } from '../services/analytics'
import {
  exploreCatalog,
  getCatalogPublishers,
  getPopularSearches,
  getPopularWorks,
  getShelf,
} from '../services/api'
import type { CatalogPublisher, CatalogSort, CatalogWork, PopularSearch } from '../types/catalog'
import type { ShelfReading } from '../types/reading'

const filterParamKeys = ['editora', 'ordem', 'criticas', 'lendo', 'capa', 'isbn', 'pt'] as const

function validSort(value: string): CatalogSort {
  return value === 'popular' || value === 'avaliacao' || value === 'recentes' ? value : ''
}

function readFilters(params: URLSearchParams): SearchFilters {
  return {
    publisher: params.get('editora') || '',
    sort: validSort(params.get('ordem') || ''),
    withReviews: params.get('criticas') === '1',
    readingNow: params.get('lendo') === '1',
    withCover: params.get('capa') === '1',
    withIsbn: params.get('isbn') === '1',
    portuguese: params.get('pt') === '1',
  }
}

const fallbackSuggestions = [
  'Virginia Woolf',
  'Crime e Castigo',
  'Machado de Assis',
  'Clarice Lispector',
]

function onboardingSource(): boolean {
  try {
    return sessionStorage.getItem(ONBOARDING_MARKER) === 'active'
  } catch {
    return false
  }
}

function initiallyDismissed(): boolean {
  try {
    return sessionStorage.getItem(ONBOARDING_DISMISSED) === '1'
  } catch {
    return false
  }
}

export function SearchPage() {
  const { locale, t } = usePreferences()
  const { enabled, status: featureStatus } = useFeatureFlags()
  const [searchParams, setSearchParams] = useSearchParams()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const activeQuery = searchParams.get('q')?.trim() || ''
  const [query, setQuery] = useState(activeQuery)
  const [results, setResults] = useState<CatalogWork[]>([])
  const [popularSearches, setPopularSearches] = useState<PopularSearch[]>([])
  const [popularWorks, setPopularWorks] = useState<CatalogWork[]>([])
  const [shelf, setShelf] = useState<ShelfReading[]>([])
  const [shelfReady, setShelfReady] = useState(false)
  const [onboardingDismissed, setOnboardingDismissed] = useState(initiallyDismissed)
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [publishers, setPublishers] = useState<CatalogPublisher[]>([])
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)

  // filtros derivam da URL (mesmas chaves do Explorar); a string dos params
  // vira a chave estável do efeito de busca
  const filterKey = filterParamKeys.map((key) => `${key}=${searchParams.get(key) || ''}`).join('&')
  const filters = useMemo(() => readFilters(searchParams), [filterKey])
  const activeFilters = countActiveFilters(filters)

  const onboardingEnabled = featureStatus === 'ready' && enabled('onboarding_value')
  const homeRitualEnabled = featureStatus === 'ready' && enabled('home_ritual')
  const progressEnabled = featureStatus === 'ready' && enabled('progress_sessions')

  useEffect(() => {
    setQuery(activeQuery)
  }, [activeQuery])

  useEffect(() => {
    if (!onboardingEnabled && !homeRitualEnabled) {
      setShelf([])
      setShelfReady(false)
      return
    }
    const controller = new AbortController()
    setShelfReady(false)
    void getShelf(controller.signal)
      .then((payload) => {
        setShelf(Array.isArray(payload) ? payload : [])
        setShelfReady(true)
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setShelf([])
        setShelfReady(true)
      })
    return () => controller.abort()
  }, [homeRitualEnabled, onboardingEnabled])

  useEffect(() => {
    const controller = new AbortController()

    if (!activeQuery) {
      setResults([])
      setStatus('idle')
      setError(null)
      void Promise.allSettled([
        getPopularSearches(controller.signal),
        getPopularWorks(controller.signal),
      ]).then(([searchesResult, worksResult]) => {
        if (controller.signal.aborted) return
        if (searchesResult.status === 'fulfilled') setPopularSearches(searchesResult.value)
        if (worksResult.status === 'fulfilled') setPopularWorks(worksResult.value.slice(0, 8))
      })
      return () => controller.abort()
    }

    if (activeQuery.length < 2) {
      setResults([])
      setStatus('ready')
      return () => controller.abort()
    }

    setStatus('loading')
    setError(null)
    // exploreCatalog cobre a busca simples (só q) e a busca com filtros —
    // ambos batem em /api/buscar; sem filtro é equivalente ao searchCatalog
    void exploreCatalog(
      {
        query: activeQuery,
        publisher: filters.publisher,
        sort: filters.sort,
        withReviews: filters.withReviews,
        readingNow: filters.readingNow,
        withCover: filters.withCover,
        withIsbn: filters.withIsbn,
        portuguese: filters.portuguese,
      },
      controller.signal,
    )
      .then((payload) => {
        setResults(Array.isArray(payload) ? payload : [])
        setStatus('ready')
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : catalogText(locale, 'error'))
        setStatus('error')
      })

    return () => controller.abort()
  }, [activeQuery, filterKey, filters, locale])

  // editoras pro select da sheet (carrega uma vez)
  useEffect(() => {
    const controller = new AbortController()
    void getCatalogPublishers(controller.signal)
      .then((payload) => setPublishers(Array.isArray(payload) ? payload : []))
      .catch(() => {})
    return () => controller.abort()
  }, [])

  function setFilterParam(patch: Partial<SearchFilters>) {
    const next = new URLSearchParams(searchParams)
    const map: Record<keyof SearchFilters, string> = {
      publisher: 'editora',
      sort: 'ordem',
      withReviews: 'criticas',
      readingNow: 'lendo',
      withCover: 'capa',
      withIsbn: 'isbn',
      portuguese: 'pt',
    }
    for (const [field, value] of Object.entries(patch)) {
      const key = map[field as keyof SearchFilters]
      if (typeof value === 'boolean') {
        if (value) next.set(key, '1')
        else next.delete(key)
      } else if (value) {
        next.set(key, value)
      } else {
        next.delete(key)
      }
    }
    setSearchParams(next)
  }

  function clearFilters() {
    const next = new URLSearchParams(searchParams)
    filterParamKeys.forEach((key) => next.delete(key))
    setSearchParams(next)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = query.trim()
    if (normalized) {
      trackProductEvent('search_submitted', {
        source: onboardingSource() ? 'onboarding' : 'home',
        has_filters: activeFilters > 0,
        result_state: 'submitted',
      })
      const next = new URLSearchParams(searchParams)
      next.set('q', normalized)
      setSearchParams(next)
    } else {
      setSearchParams({})
    }
  }

  function runSearch(value: string) {
    setQuery(value)
    trackProductEvent('search_submitted', {
      source: onboardingSource() ? 'onboarding' : 'home',
      has_filters: activeFilters > 0,
      result_state: 'submitted',
    })
    const next = new URLSearchParams(searchParams)
    next.set('q', value)
    setSearchParams(next)
  }

  function startOnboarding() {
    try {
      sessionStorage.setItem(ONBOARDING_MARKER, 'active')
    } catch {
      // O fluxo continua mesmo quando o armazenamento está indisponível.
    }
    inputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.setTimeout(() => inputRef.current?.focus(), 250)
  }

  function dismissOnboarding() {
    setOnboardingDismissed(true)
    try {
      sessionStorage.setItem(ONBOARDING_DISMISSED, '1')
    } catch {
      // Estado efêmero; falhar ao persistir não bloqueia a navegação.
    }
  }

  const suggestions = popularSearches.length > 0
    ? popularSearches.slice(0, 6).map((item) => item.termo)
    : fallbackSuggestions
  const readingNow = shelf.find((reading) => reading.status === 'Lendo') ?? null
  const showOnboarding = onboardingEnabled && shelfReady && shelf.length === 0 && !onboardingDismissed
  const showRitual = homeRitualEnabled && progressEnabled && shelfReady && Boolean(readingNow)
  const resultSource = onboardingSource() ? 'onboarding' : 'search'

  return (
    <section className="page page--search">
      <PageHeader
        title={t('search_title')}
        description={
          status === 'ready' && activeQuery
            ? `${results.length} ${catalogText(locale, 'results')}`
            : t('search_copy')
        }
      />

      {showOnboarding && (
        <OnboardingValueCard locale={locale} onStart={startOnboarding} onDismiss={dismissOnboarding} />
      )}

      {showRitual && readingNow && <ReadingRitualCard reading={readingNow} locale={locale} />}

      <div className="catalog-search-row">
        <form className="search-form catalog-search-form" onSubmit={submit} role="search">
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('search_placeholder')}
            aria-label={t('search_placeholder')}
            autoComplete="off"
          />
          <button type="submit" aria-label={t('search_button')}>
            <Icon name="search" size={21} />
          </button>
        </form>
        <button
          type="button"
          className={`search-filter-trigger${activeFilters > 0 ? ' has-filters' : ''}`}
          onClick={() => setFiltersOpen(true)}
          aria-haspopup="dialog"
        >
          <Icon name="explore" size={16} />
          <span>{exploreText(locale, 'open_filters')}</span>
          {activeFilters > 0 && <strong>{activeFilters}</strong>}
        </button>
      </div>

      {filtersOpen && (
        <SearchFilterSheet
          locale={locale}
          filters={filters}
          publishers={publishers}
          onChange={setFilterParam}
          onClear={clearFilters}
          onClose={() => setFiltersOpen(false)}
        />
      )}

      {!activeQuery && (
        <section className="catalog-discovery">
          <div className="catalog-discovery__heading">
            <p className="eyebrow">{catalogText(locale, 'popular_searches')}</p>
          </div>
          <div className="suggestion-row catalog-suggestions" aria-label={catalogText(locale, 'popular_searches')}>
            {suggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => runSearch(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>

          {popularWorks.length > 0 && (
            <>
              <div className="catalog-discovery__heading catalog-discovery__heading--works">
                <p className="eyebrow">{catalogText(locale, 'popular_books')}</p>
              </div>
              <div className="catalog-results catalog-results--featured">
                {popularWorks.map((work) => (
                  <SearchResultCard key={`${work.work_key}-${work.titulo}`} work={work} locale={locale} source={resultSource} />
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {status === 'loading' && (
        <div className="catalog-results catalog-results--loading" aria-busy="true" aria-label={catalogText(locale, 'loading')}>
          {Array.from({ length: 6 }, (_, index) => (
            <article key={index}><span /><div><i /><i /><i /></div></article>
          ))}
        </div>
      )}

      {status === 'error' && (
        <section className="catalog-state" role="alert">
          <Icon name="refresh" size={30} />
          <h2>{catalogText(locale, 'error')}</h2>
          <p>{error}</p>
          <button className="button button--secondary" type="button" onClick={() => runSearch(activeQuery)}>
            <Icon name="refresh" size={17} />
            {t('retry')}
          </button>
        </section>
      )}

      {status === 'ready' && activeQuery && results.length === 0 && (
        <section className="catalog-state">
          <Icon name="search" size={32} />
          <h2>{catalogText(locale, 'no_results')}</h2>
          <p>{catalogText(locale, 'no_results_copy')}</p>
          <div className="catalog-state__actions">
            {activeFilters > 0 && (
              <button className="button button--secondary" type="button" onClick={clearFilters}>
                {exploreText(locale, 'clear')}
              </button>
            )}
            <button className="button button--primary" type="button" onClick={() => setManualOpen(true)}>
              {manualText(locale, 'cta_button')}
            </button>
          </div>
        </section>
      )}

      {status === 'ready' && results.length > 0 && (
        <>
          <div className="catalog-results">
            {results.map((work) => (
              <SearchResultCard key={`${work.work_key}-${work.titulo}`} work={work} locale={locale} source={resultSource} />
            ))}
          </div>
          <p className="manual-cta">
            <span>{manualText(locale, 'cta_text')}</span>
            <button type="button" className="text-button" onClick={() => setManualOpen(true)}>
              {manualText(locale, 'cta_button')}
            </button>
          </p>
        </>
      )}

      {manualOpen && (
        <ManualBookForm
          locale={locale}
          initialTitle={activeQuery}
          onClose={() => setManualOpen(false)}
        />
      )}
    </section>
  )
}

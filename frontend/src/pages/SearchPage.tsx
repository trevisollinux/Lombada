import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { SearchResultCard } from '../features/catalog/SearchResultCard'
import { catalogText } from '../features/catalog/catalogI18n'
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
  getPopularSearches,
  getPopularWorks,
  getShelf,
  searchCatalog,
} from '../services/api'
import type { CatalogWork, PopularSearch } from '../types/catalog'
import type { ShelfReading } from '../types/reading'

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
    void searchCatalog(activeQuery, controller.signal)
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
  }, [activeQuery, locale])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = query.trim()
    if (normalized) {
      trackProductEvent('search_submitted', {
        source: onboardingSource() ? 'onboarding' : 'home',
        has_filters: false,
        result_state: 'submitted',
      })
      setSearchParams({ q: normalized })
    } else {
      setSearchParams({})
    }
  }

  function runSearch(value: string) {
    setQuery(value)
    trackProductEvent('search_submitted', {
      source: onboardingSource() ? 'onboarding' : 'home',
      has_filters: false,
      result_state: 'submitted',
    })
    setSearchParams({ q: value })
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
        eyebrow={t('search_eyebrow')}
        title={t('search_title')}
        description={
          status === 'ready' && activeQuery
            ? `${results.length} ${catalogText(locale, 'results')}`
            : t('search_copy')
        }
        aside={<span className="stage-stamp">06 · catálogo</span>}
      />

      {showOnboarding && (
        <OnboardingValueCard locale={locale} onStart={startOnboarding} onDismiss={dismissOnboarding} />
      )}

      {showRitual && readingNow && <ReadingRitualCard reading={readingNow} locale={locale} />}

      <form className="search-form catalog-search-form" onSubmit={submit} role="search">
        <Icon name="search" size={24} />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('search_placeholder')}
          aria-label={t('search_placeholder')}
          autoComplete="off"
        />
        <button type="submit">{t('search_button')}</button>
      </form>

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
        </section>
      )}

      {status === 'ready' && results.length > 0 && (
        <div className="catalog-results">
          {results.map((work) => (
            <SearchResultCard key={`${work.work_key}-${work.titulo}`} work={work} locale={locale} source={resultSource} />
          ))}
        </div>
      )}
    </section>
  )
}

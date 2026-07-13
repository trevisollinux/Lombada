import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { SearchResultCard } from '../features/catalog/SearchResultCard'
import { catalogText } from '../features/catalog/catalogI18n'
import { usePreferences } from '../providers/PreferencesProvider'
import {
  getPopularSearches,
  getPopularWorks,
  searchCatalog,
} from '../services/api'
import type { CatalogWork, PopularSearch } from '../types/catalog'

const fallbackSuggestions = [
  'Virginia Woolf',
  'Crime e Castigo',
  'Machado de Assis',
  'Clarice Lispector',
]

export function SearchPage() {
  const { locale, t } = usePreferences()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeQuery = searchParams.get('q')?.trim() || ''
  const [query, setQuery] = useState(activeQuery)
  const [results, setResults] = useState<CatalogWork[]>([])
  const [popularSearches, setPopularSearches] = useState<PopularSearch[]>([])
  const [popularWorks, setPopularWorks] = useState<CatalogWork[]>([])
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setQuery(activeQuery)
  }, [activeQuery])

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
    if (normalized) setSearchParams({ q: normalized })
    else setSearchParams({})
  }

  function runSearch(value: string) {
    setQuery(value)
    setSearchParams({ q: value })
  }

  const suggestions = popularSearches.length > 0
    ? popularSearches.slice(0, 6).map((item) => item.termo)
    : fallbackSuggestions

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

      <form className="search-form catalog-search-form" onSubmit={submit} role="search">
        <Icon name="search" size={24} />
        <input
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
                  <SearchResultCard key={`${work.work_key}-${work.titulo}`} work={work} locale={locale} />
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
            <SearchResultCard key={`${work.work_key}-${work.titulo}`} work={work} locale={locale} />
          ))}
        </div>
      )}
    </section>
  )
}

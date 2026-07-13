import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { SearchResultCard } from '../features/catalog/SearchResultCard'
import { exploreText } from '../features/explore/exploreI18n'
import { usePreferences } from '../providers/PreferencesProvider'
import {
  exploreCatalog,
  getCatalogLiteratures,
  getCatalogPublishers,
  getPopularWorks,
} from '../services/api'
import type {
  CatalogLiterature,
  CatalogPublisher,
  CatalogSort,
  CatalogWork,
  ExploreCatalogOptions,
} from '../types/catalog'

const genres = [
  'romance',
  'conto',
  'poesia',
  'teatro',
  'ensaio',
  'biografia',
  'história',
  'filosofia',
  'fantasia',
  'ficção científica',
  'terror',
  'policial',
  'infantil',
  'juvenil',
  'crônica',
  'quadrinhos',
]

const booleanParams = ['criticas', 'lendo', 'capa', 'isbn', 'pt'] as const

type BooleanParam = (typeof booleanParams)[number]

function enabled(params: URLSearchParams, key: BooleanParam): boolean {
  return params.get(key) === '1'
}

export function ExplorePage() {
  const { locale, t } = usePreferences()
  const [searchParams, setSearchParams] = useSearchParams()
  const [popularWorks, setPopularWorks] = useState<CatalogWork[]>([])
  const [publishers, setPublishers] = useState<CatalogPublisher[]>([])
  const [literatures, setLiteratures] = useState<CatalogLiterature[]>([])
  const [results, setResults] = useState<CatalogWork[]>([])
  const [discoveryStatus, setDiscoveryStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [resultsStatus, setResultsStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  const genre = searchParams.get('genero') || ''
  const literature = searchParams.get('literatura') || ''
  const publisher = searchParams.get('editora') || ''
  const sort = (searchParams.get('ordem') || '') as CatalogSort
  const withReviews = enabled(searchParams, 'criticas')
  const readingNow = enabled(searchParams, 'lendo')
  const withCover = enabled(searchParams, 'capa')
  const withIsbn = enabled(searchParams, 'isbn')
  const portuguese = enabled(searchParams, 'pt')

  const hasFilters = Boolean(
    genre || literature || publisher || sort || withReviews || readingNow || withCover || withIsbn || portuguese,
  )

  const options = useMemo<ExploreCatalogOptions>(() => ({
    genre,
    literature,
    publisher,
    sort,
    withReviews,
    readingNow,
    withCover,
    withIsbn,
    portuguese,
  }), [genre, literature, publisher, sort, withReviews, readingNow, withCover, withIsbn, portuguese])

  useEffect(() => {
    const controller = new AbortController()
    setDiscoveryStatus('loading')
    void Promise.allSettled([
      getPopularWorks(controller.signal),
      getCatalogPublishers(controller.signal),
      getCatalogLiteratures(controller.signal),
    ]).then(([worksResult, publishersResult, literaturesResult]) => {
      if (controller.signal.aborted) return
      if (worksResult.status === 'fulfilled') setPopularWorks(worksResult.value.slice(0, 12))
      if (publishersResult.status === 'fulfilled') setPublishers(publishersResult.value)
      if (literaturesResult.status === 'fulfilled') setLiteratures(literaturesResult.value)
      const allFailed = [worksResult, publishersResult, literaturesResult].every((item) => item.status === 'rejected')
      setDiscoveryStatus(allFailed ? 'error' : 'ready')
    })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!hasFilters) {
      setResults([])
      setResultsStatus('idle')
      setError(null)
      return
    }

    const controller = new AbortController()
    setResultsStatus('loading')
    setError(null)
    void exploreCatalog(options, controller.signal)
      .then((payload) => {
        setResults(Array.isArray(payload) ? payload : [])
        setResultsStatus('ready')
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : exploreText(locale, 'error'))
        setResultsStatus('error')
      })
    return () => controller.abort()
  }, [hasFilters, locale, options])

  function setParam(key: string, value: string | boolean) {
    const next = new URLSearchParams(searchParams)
    if (typeof value === 'boolean') {
      if (value) next.set(key, '1')
      else next.delete(key)
    } else if (value) {
      next.set(key, value)
    } else {
      next.delete(key)
    }
    setSearchParams(next)
  }

  function clearFilters() {
    setSearchParams({})
  }

  const activeLabels = [
    genre,
    literature ? literatures.find((item) => item.slug === literature)?.label || literature : '',
    publisher,
    sort === 'popular' ? exploreText(locale, 'most_read') : '',
    sort === 'avaliacao' ? exploreText(locale, 'best_rated') : '',
    sort === 'recentes' ? exploreText(locale, 'recent') : '',
    withReviews ? exploreText(locale, 'with_reviews') : '',
    readingNow ? exploreText(locale, 'reading_now') : '',
    withCover ? exploreText(locale, 'with_cover') : '',
    withIsbn ? exploreText(locale, 'with_isbn') : '',
    portuguese ? exploreText(locale, 'portuguese') : '',
  ].filter(Boolean)

  return (
    <section className="page page--explore">
      <PageHeader
        eyebrow={exploreText(locale, 'eyebrow')}
        title={exploreText(locale, 'title')}
        description={
          hasFilters && resultsStatus === 'ready'
            ? `${results.length} ${exploreText(locale, 'results')}`
            : exploreText(locale, 'copy')
        }
        aside={<span className="stage-stamp">07 · descoberta</span>}
      />

      <section className="explore-filter-panel" aria-labelledby="explore-filter-title">
        <div className="explore-filter-panel__heading">
          <div>
            <p className="eyebrow">{exploreText(locale, 'filters')}</p>
            <h2 id="explore-filter-title">{exploreText(locale, 'filter_copy')}</h2>
          </div>
          {hasFilters && (
            <button className="text-button" type="button" onClick={clearFilters}>
              {exploreText(locale, 'clear')}
            </button>
          )}
        </div>

        <div className="explore-filter-grid">
          <label>
            <span>{exploreText(locale, 'publisher')}</span>
            <select value={publisher} onChange={(event) => setParam('editora', event.target.value)}>
              <option value="">{exploreText(locale, 'all_publishers')}</option>
              {publishers.map((item) => (
                <option key={item.slug} value={item.editora}>
                  {item.editora} · {item.obras_count}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>{exploreText(locale, 'literature')}</span>
            <select value={literature} onChange={(event) => setParam('literatura', event.target.value)}>
              <option value="">{exploreText(locale, 'all_literatures')}</option>
              {literatures.map((item) => (
                <option key={item.slug} value={item.slug}>{item.label}</option>
              ))}
            </select>
          </label>

          <label>
            <span>{exploreText(locale, 'sort')}</span>
            <select value={sort} onChange={(event) => setParam('ordem', event.target.value)}>
              <option value="">{exploreText(locale, 'relevance')}</option>
              <option value="popular">{exploreText(locale, 'most_read')}</option>
              <option value="avaliacao">{exploreText(locale, 'best_rated')}</option>
              <option value="recentes">{exploreText(locale, 'recent')}</option>
            </select>
          </label>
        </div>

        <div className="explore-genre-row" aria-label={exploreText(locale, 'genres')}>
          {genres.map((item) => (
            <button
              key={item}
              type="button"
              className={genre === item ? 'is-active' : ''}
              aria-pressed={genre === item}
              onClick={() => setParam('genero', genre === item ? '' : item)}
            >
              {item}
            </button>
          ))}
        </div>

        <div className="explore-toggle-row">
          <Toggle active={withReviews} label={exploreText(locale, 'with_reviews')} onClick={() => setParam('criticas', !withReviews)} />
          <Toggle active={readingNow} label={exploreText(locale, 'reading_now')} onClick={() => setParam('lendo', !readingNow)} />
          <Toggle active={withCover} label={exploreText(locale, 'with_cover')} onClick={() => setParam('capa', !withCover)} />
          <Toggle active={withIsbn} label={exploreText(locale, 'with_isbn')} onClick={() => setParam('isbn', !withIsbn)} />
          <Toggle active={portuguese} label={exploreText(locale, 'portuguese')} onClick={() => setParam('pt', !portuguese)} />
        </div>

        {activeLabels.length > 0 && (
          <div className="explore-active-filters" aria-label={exploreText(locale, 'active_filters')}>
            <span>{exploreText(locale, 'active_filters')}</span>
            {activeLabels.map((label) => <strong key={label}>{label}</strong>)}
          </div>
        )}
      </section>

      {hasFilters ? (
        <FilteredResults
          locale={locale}
          status={resultsStatus}
          results={results}
          error={error}
          retry={() => setSearchParams(new URLSearchParams(searchParams))}
        />
      ) : (
        <DiscoveryHome
          locale={locale}
          status={discoveryStatus}
          popularWorks={popularWorks}
          publishers={publishers}
          literatures={literatures}
          chooseGenre={(value) => setParam('genero', value)}
          chooseLiterature={(value) => setParam('literatura', value)}
          choosePublisher={(value) => setParam('editora', value)}
        />
      )}
    </section>
  )
}

interface FilteredResultsProps {
  locale: 'pt-BR' | 'en'
  status: 'idle' | 'loading' | 'ready' | 'error'
  results: CatalogWork[]
  error: string | null
  retry: () => void
}

function FilteredResults({ locale, status, results, error, retry }: FilteredResultsProps) {
  if (status === 'loading') return <ExploreLoading label={exploreText(locale, 'loading')} />
  if (status === 'error') {
    return (
      <section className="catalog-state" role="alert">
        <Icon name="refresh" size={30} />
        <h2>{exploreText(locale, 'error')}</h2>
        <p>{error}</p>
        <button className="button button--secondary" type="button" onClick={retry}>
          <Icon name="refresh" size={17} />
          {locale === 'pt-BR' ? 'Tentar novamente' : 'Try again'}
        </button>
      </section>
    )
  }
  if (status === 'ready' && results.length === 0) {
    return (
      <section className="catalog-state">
        <Icon name="explore" size={32} />
        <h2>{exploreText(locale, 'empty')}</h2>
        <p>{exploreText(locale, 'empty_copy')}</p>
      </section>
    )
  }
  return (
    <div className="catalog-results explore-results">
      {results.map((work) => (
        <SearchResultCard key={`${work.work_key}-${work.titulo}`} work={work} locale={locale} />
      ))}
    </div>
  )
}

interface DiscoveryHomeProps {
  locale: 'pt-BR' | 'en'
  status: 'loading' | 'ready' | 'error'
  popularWorks: CatalogWork[]
  publishers: CatalogPublisher[]
  literatures: CatalogLiterature[]
  chooseGenre: (value: string) => void
  chooseLiterature: (value: string) => void
  choosePublisher: (value: string) => void
}

function DiscoveryHome({
  locale,
  status,
  popularWorks,
  publishers,
  literatures,
  chooseGenre,
  chooseLiterature,
  choosePublisher,
}: DiscoveryHomeProps) {
  if (status === 'loading') return <ExploreLoading label={exploreText(locale, 'loading')} />
  if (status === 'error') {
    return (
      <section className="catalog-state" role="alert">
        <Icon name="refresh" size={30} />
        <h2>{exploreText(locale, 'error')}</h2>
      </section>
    )
  }

  return (
    <div className="explore-discovery">
      {popularWorks.length > 0 && (
        <section className="explore-section">
          <div className="explore-section__heading">
            <div><p className="eyebrow">{exploreText(locale, 'popular')}</p><h2>{exploreText(locale, 'popular')}</h2></div>
            <span>{popularWorks.length}</span>
          </div>
          <div className="catalog-results explore-results">
            {popularWorks.map((work) => (
              <SearchResultCard key={`${work.work_key}-${work.titulo}`} work={work} locale={locale} />
            ))}
          </div>
        </section>
      )}

      <section className="explore-section">
        <div className="explore-section__heading">
          <div><p className="eyebrow">{exploreText(locale, 'paths')}</p><h2>{exploreText(locale, 'literatures')}</h2></div>
        </div>
        <div className="explore-path-grid">
          {literatures.slice(0, 10).map((item, index) => (
            <button key={item.slug} type="button" onClick={() => chooseLiterature(item.slug)}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{item.label}</strong>
              <small>{item.pais || item.regiao}</small>
              <Icon name="arrow" size={17} />
            </button>
          ))}
        </div>
      </section>

      <section className="explore-section">
        <div className="explore-section__heading">
          <div><p className="eyebrow">{exploreText(locale, 'paths')}</p><h2>{exploreText(locale, 'genres')}</h2></div>
        </div>
        <div className="explore-genre-wall">
          {genres.map((item, index) => (
            <button key={item} type="button" onClick={() => chooseGenre(item)}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <strong>{item}</strong>
            </button>
          ))}
        </div>
      </section>

      {publishers.length > 0 && (
        <section className="explore-section">
          <div className="explore-section__heading">
            <div><p className="eyebrow">{exploreText(locale, 'publishers')}</p><h2>{exploreText(locale, 'publishers')}</h2></div>
            <span>{publishers.length}</span>
          </div>
          <div className="explore-publisher-grid">
            {publishers.slice(0, 12).map((item) => (
              <button key={item.slug} type="button" onClick={() => choosePublisher(item.editora)}>
                <strong>{item.editora}</strong>
                <span>{item.obras_count} {exploreText(locale, 'works')}</span>
                <small>{item.edicoes_count} {exploreText(locale, 'editions')} · {item.com_capa_count} {exploreText(locale, 'coverage')}</small>
                <Icon name="arrow" size={17} />
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function ExploreLoading({ label }: { label: string }) {
  return (
    <div className="catalog-results catalog-results--loading explore-loading" aria-busy="true" aria-label={label}>
      {Array.from({ length: 6 }, (_, index) => (
        <article key={index}><span /><div><i /><i /><i /></div></article>
      ))}
    </div>
  )
}

function Toggle({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button type="button" className={active ? 'is-active' : ''} aria-pressed={active} onClick={onClick}>
      <span aria-hidden="true">{active ? '✓' : '+'}</span>
      {label}
    </button>
  )
}

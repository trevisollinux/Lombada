import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { exploreText } from '../features/explore/exploreI18n'
import { usePreferences } from '../providers/PreferencesProvider'
import { getCatalogPublishers } from '../services/api'
import type { CatalogPublisher } from '../types/catalog'

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

/* Página dedicada de editoras, como no app legado (/editoras): a lista
   completa do catálogo, com busca. Cada editora abre suas obras no Explorar
   filtrado (/explorar?editora=…). */
export function PublishersPage() {
  const { locale } = usePreferences()
  const [publishers, setPublishers] = useState<CatalogPublisher[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [query, setQuery] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    getCatalogPublishers(controller.signal)
      .then((list) => {
        setPublishers(list)
        setStatus('ready')
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setStatus('error')
      })
    return () => controller.abort()
  }, [retryVersion])

  const filtered = useMemo(() => {
    const q = normalize(query.trim())
    if (!q) return publishers
    return publishers.filter((item) => normalize(item.editora).includes(q))
  }, [publishers, query])

  return (
    <section className="page page--publishers">
      <PageHeader title={exploreText(locale, 'publishers')} />
      <p className="publishers-copy">{exploreText(locale, 'publishers_copy')}</p>

      {status === 'loading' && (
        <div className="publishers-list publishers-list--loading" aria-busy="true">
          {Array.from({ length: 8 }, (_, index) => (
            <span key={index} />
          ))}
        </div>
      )}

      {status === 'error' && (
        <section className="catalog-state" role="alert">
          <Icon name="refresh" size={30} />
          <h2>{exploreText(locale, 'error')}</h2>
          <button
            className="button button--secondary"
            type="button"
            onClick={() => setRetryVersion((current) => current + 1)}
          >
            <Icon name="refresh" size={17} />
            {locale === 'pt-BR' ? 'Tentar novamente' : locale === 'es' ? 'Reintentar' : 'Try again'}
          </button>
        </section>
      )}

      {status === 'ready' && (
        <>
          <div className="publishers-search">
            <Icon name="search" size={16} />
            <input
              type="search"
              value={query}
              placeholder={exploreText(locale, 'search_publisher')}
              aria-label={exploreText(locale, 'search_publisher')}
              onChange={(event) => setQuery(event.target.value)}
            />
            <span className="publishers-search__count">{filtered.length}</span>
          </div>

          {filtered.length === 0 ? (
            <p className="publishers-empty">{exploreText(locale, 'no_publisher_match')}</p>
          ) : (
            <ul className="publishers-list">
              {filtered.map((item) => (
                <li key={item.slug || item.editora}>
                  <Link
                    className="publisher-row"
                    to={`/explorar?editora=${encodeURIComponent(item.editora)}`}
                  >
                    <span className="publisher-row__main">
                      <strong>{item.editora}</strong>
                      <small>
                        {item.obras_count} {exploreText(locale, 'works')} · {item.edicoes_count}{' '}
                        {exploreText(locale, 'editions')}
                      </small>
                    </span>
                    <Icon name="arrow" size={17} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}

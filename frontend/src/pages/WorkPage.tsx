import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'

import { BookCover } from '../components/BookCover'
import { Icon } from '../components/Icon'
import { PostReadCelebration } from '../features/catalog/PostReadCelebration'
import { ReadingRegistrationForm } from '../features/catalog/ReadingRegistrationForm'
import { catalogText } from '../features/catalog/catalogI18n'
import { usePreferences } from '../providers/PreferencesProvider'
import {
  getShelf,
  getWorkEditions,
  getWorkSocial,
  searchCatalog,
} from '../services/api'
import type {
  CatalogEdition,
  CatalogWork,
  ReadingCreateResponse,
  WorkSocialResponse,
} from '../types/catalog'

interface WorkLocationState {
  work?: CatalogWork
}

function cleanEdition(raw: Partial<CatalogEdition>): CatalogEdition {
  return {
    edicao_id: raw.edicao_id ?? null,
    ol_edition_key: raw.ol_edition_key || null,
    titulo_edicao: raw.titulo_edicao || '',
    editora: raw.editora || '',
    tradutor: raw.tradutor || '',
    isbn: raw.isbn || '',
    idioma: raw.idioma || '',
    ano: raw.ano ?? null,
    capa_url: raw.capa_url || '',
    paginas: raw.paginas ?? null,
    leituras_count: raw.leituras_count,
    leituras: raw.leituras,
    tem: raw.tem,
    querem: raw.querem,
    media: raw.media,
    estado: raw.estado,
  }
}

function localEditions(payload: WorkSocialResponse | null): CatalogEdition[] {
  if (!payload) return []
  return payload.edicoes.map((item) => cleanEdition({
    edicao_id: item.edicao_id,
    ol_edition_key: item.ol_edition_key,
    titulo_edicao: payload.obra.titulo,
    ...item.edicao,
    leituras: item.leituras,
    tem: item.tem,
    querem: item.querem,
    media: item.media,
    estado: item.estado,
  }))
}

function editionKey(edition: CatalogEdition): string {
  if (edition.ol_edition_key) return `key:${edition.ol_edition_key}`
  if (edition.isbn) return `isbn:${edition.isbn.replace(/\D/g, '')}`
  return `meta:${edition.editora.trim().toLowerCase()}|${edition.ano ?? ''}|${edition.tradutor.trim().toLowerCase()}`
}

function mergeEditions(groups: CatalogEdition[][]): CatalogEdition[] {
  const merged = new Map<string, CatalogEdition>()
  groups.flat().forEach((raw) => {
    const edition = cleanEdition(raw)
    const key = editionKey(edition)
    const previous = merged.get(key)
    if (!previous) {
      merged.set(key, edition)
      return
    }
    merged.set(key, {
      ...edition,
      ...previous,
      edicao_id: previous.edicao_id ?? edition.edicao_id,
      capa_url: previous.capa_url || edition.capa_url,
      paginas: previous.paginas ?? edition.paginas,
      estado: previous.estado ?? edition.estado,
      leituras: previous.leituras ?? edition.leituras,
      tem: previous.tem ?? edition.tem,
      querem: previous.querem ?? edition.querem,
      media: previous.media ?? edition.media,
    })
  })

  return Array.from(merged.values()).sort((a, b) => {
    const aPt = a.idioma.toLowerCase().includes('portugu') ? 1 : 0
    const bPt = b.idioma.toLowerCase().includes('portugu') ? 1 : 0
    if (aPt !== bPt) return bPt - aPt
    if (Boolean(a.capa_url) !== Boolean(b.capa_url)) return Number(Boolean(b.capa_url)) - Number(Boolean(a.capa_url))
    return (b.ano ?? 0) - (a.ano ?? 0)
  })
}

export function WorkPage() {
  const { locale } = usePreferences()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const stateWork = (location.state as WorkLocationState | null)?.work
  const initialWork: CatalogWork = stateWork ?? {
    work_key: searchParams.get('work_key') || '',
    titulo: searchParams.get('titulo') || '',
    autor: searchParams.get('autor') || '',
    ano: null,
    idioma_original: '',
    capa_url: '',
  }

  const [work, setWork] = useState<CatalogWork>(initialWork)
  const [social, setSocial] = useState<WorkSocialResponse | null>(null)
  const [editions, setEditions] = useState<CatalogEdition[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [selectedEdition, setSelectedEdition] = useState<CatalogEdition | null>(null)
  const [registered, setRegistered] = useState<ReadingCreateResponse | null>(null)
  const [celebration, setCelebration] = useState<{ title: string; milestone: number } | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setStatus('loading')
      setError(null)
      try {
        let resolvedWork = initialWork
        if (!stateWork && initialWork.titulo) {
          const results = await searchCatalog(initialWork.titulo, controller.signal)
          resolvedWork = results.find((item) => item.work_key === initialWork.work_key)
            ?? results.find((item) => item.titulo.toLowerCase() === initialWork.titulo.toLowerCase())
            ?? initialWork
          setWork(resolvedWork)
        }

        const embedded = [
          ...(resolvedWork.edicao_isbn ? [resolvedWork.edicao_isbn] : []),
          ...(resolvedWork.edicoes || []),
        ].map(cleanEdition)

        const [socialResult, externalResult] = await Promise.allSettled([
          getWorkSocial(resolvedWork, controller.signal),
          resolvedWork.work_key.startsWith('/works/')
            ? getWorkEditions(resolvedWork.work_key, controller.signal)
            : Promise.resolve([]),
        ])

        if (controller.signal.aborted) return

        const socialPayload = socialResult.status === 'fulfilled' ? socialResult.value : null
        const external = externalResult.status === 'fulfilled' ? externalResult.value : []
        setSocial(socialPayload)

        if (socialPayload?.obra?.titulo) {
          setWork((current) => ({
            ...current,
            work_key: socialPayload.obra.work_key || current.work_key,
            titulo: socialPayload.obra.titulo || current.titulo,
            autor: socialPayload.obra.autor || current.autor,
            ano: socialPayload.obra.ano ?? current.ano,
            idioma_original: socialPayload.obra.idioma_original || current.idioma_original,
          }))
        }

        const combined = mergeEditions([localEditions(socialPayload), embedded, external])
        setEditions(combined)
        setStatus('ready')
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : catalogText(locale, 'error'))
        setStatus('error')
      }
    }

    void load()
    return () => controller.abort()
  }, [initialWork.autor, initialWork.titulo, initialWork.work_key, locale, stateWork])

  const heroCover = useMemo(
    () => selectedEdition?.capa_url || work.capa_url || editions.find((edition) => edition.capa_url)?.capa_url || '',
    [editions, selectedEdition, work.capa_url],
  )

  function handleRegistered(result: ReadingCreateResponse, meta: { status: string; title: string }) {
    setRegistered(result)
    setSelectedEdition(null)
    // livro concluído: celebração com confete + marco (Nº livro lido)
    if (meta.status === 'Lido') {
      setCelebration({ title: meta.title, milestone: 0 })
      void getShelf()
        .then((rows) => {
          const lidos = Array.isArray(rows) ? rows.filter((row) => row.status === 'Lido').length : 0
          setCelebration((current) => (current ? { ...current, milestone: lidos } : current))
        })
        .catch(() => {})
    }
  }

  return (
    <section className="page page--work">
      <Link className="catalog-back" to={`/?q=${encodeURIComponent(work.titulo)}`}>
        <Icon name="arrow" size={16} />
        {catalogText(locale, 'back_search')}
      </Link>

      <header className="work-hero">
        <BookCover title={work.titulo} author={work.autor} url={heroCover} className="work-hero__cover" />
        <div className="work-hero__copy">
          <p className="eyebrow">{[work.ano, work.idioma_original].filter(Boolean).join(' · ') || catalogText(locale, 'edition')}</p>
          <h1>{work.titulo || 'Lombada'}</h1>
          <p className="work-hero__author">{work.autor || '—'}</p>
          {social && (
            <div className="work-hero__stats">
              <span><strong>{social.estatisticas.leituras}</strong>{catalogText(locale, 'readings')}</span>
              <span><strong>{social.estatisticas.criticas}</strong>{catalogText(locale, 'reviews')}</span>
              <span><strong>{social.estatisticas.lendo}</strong>{catalogText(locale, 'reading_now')}</span>
              {social.estatisticas.media !== null && (
                <span><strong>{social.estatisticas.media.toFixed(1)}</strong>{catalogText(locale, 'average')}</span>
              )}
            </div>
          )}
        </div>
      </header>

      {registered && (
        <section className="catalog-success" role="status">
          <Icon name="shelf" size={30} />
          <div>
            <h2>{catalogText(locale, 'registered')}</h2>
            <p>{catalogText(locale, 'registered_copy')}</p>
          </div>
          <Link className="button button--primary" to="/estante">
            {catalogText(locale, 'go_shelf')}
            <Icon name="arrow" size={16} />
          </Link>
        </section>
      )}

      {selectedEdition && !registered && (
        <section className="catalog-registration-shell">
          <ReadingRegistrationForm
            work={work}
            edition={selectedEdition}
            locale={locale}
            onCancel={() => setSelectedEdition(null)}
            onRegistered={handleRegistered}
          />
        </section>
      )}

      <div className="work-section-heading">
        <div>
          <p className="eyebrow">{catalogText(locale, 'edition')}</p>
          <h2>{catalogText(locale, 'editions')}</h2>
        </div>
        {status === 'ready' && <span>{editions.length}</span>}
      </div>

      {status === 'loading' && (
        <div className="catalog-editions catalog-editions--loading" aria-busy="true">
          {Array.from({ length: 6 }, (_, index) => <article key={index}><span /><div><i /><i /><i /></div></article>)}
        </div>
      )}

      {status === 'error' && (
        <section className="catalog-state" role="alert">
          <Icon name="refresh" size={30} />
          <h2>{catalogText(locale, 'error')}</h2>
          <p>{error}</p>
        </section>
      )}

      {status === 'ready' && editions.length === 0 && (
        <section className="catalog-state">
          <Icon name="shelf" size={32} />
          <h2>{catalogText(locale, 'no_editions')}</h2>
          <p>{catalogText(locale, 'no_editions_copy')}</p>
        </section>
      )}

      {status === 'ready' && editions.length > 0 && (
        <div className="catalog-editions">
          {editions.map((edition) => {
            const key = editionKey(edition)
            const meta = [edition.editora, edition.ano, edition.idioma].filter(Boolean)
            const badges = [
              edition.estado?.li ? catalogText(locale, 'already_read') : '',
              edition.estado?.tenho ? catalogText(locale, 'owned') : '',
              edition.estado?.quero ? catalogText(locale, 'wanted') : '',
            ].filter(Boolean)
            return (
              <article className={`catalog-edition${selectedEdition && editionKey(selectedEdition) === key ? ' is-selected' : ''}`} key={key}>
                <BookCover
                  title={edition.titulo_edicao || work.titulo}
                  author={work.autor}
                  url={edition.capa_url || work.capa_url}
                  className="catalog-edition__cover"
                />
                <div className="catalog-edition__body">
                  <p className="eyebrow">{meta.join(' · ') || catalogText(locale, 'unknown_edition')}</p>
                  <h3>{edition.titulo_edicao || work.titulo}</h3>
                  <dl>
                    {edition.tradutor && <div><dt>{catalogText(locale, 'translator')}</dt><dd>{edition.tradutor}</dd></div>}
                    {edition.isbn && <div><dt>{catalogText(locale, 'isbn')}</dt><dd>{edition.isbn}</dd></div>}
                    {edition.paginas && <div><dt>{catalogText(locale, 'pages')}</dt><dd>{edition.paginas}</dd></div>}
                  </dl>
                  {badges.length > 0 && <div className="catalog-edition__badges">{badges.map((badge) => <span key={badge}>{badge}</span>)}</div>}
                  {(edition.leituras || edition.media !== null && edition.media !== undefined) && (
                    <p className="catalog-edition__social">
                      {edition.leituras ? `${edition.leituras} ${catalogText(locale, 'edition_readings')}` : ''}
                      {edition.media !== null && edition.media !== undefined ? ` · ${catalogText(locale, 'average')} ${edition.media.toFixed(1)}` : ''}
                    </p>
                  )}
                  <button
                    className="button button--primary"
                    type="button"
                    onClick={() => {
                      setRegistered(null)
                      setSelectedEdition(edition)
                      window.scrollTo({ top: 0, behavior: 'smooth' })
                    }}
                  >
                    {catalogText(locale, 'register')}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      )}

      {celebration && (
        <PostReadCelebration
          locale={locale}
          title={celebration.title}
          milestone={celebration.milestone}
          onClose={() => setCelebration(null)}
        />
      )}
    </section>
  )
}

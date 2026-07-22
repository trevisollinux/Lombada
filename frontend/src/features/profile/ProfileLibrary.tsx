import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import type { ProfileReading } from '../../types/profile'
import { profileText } from './profileI18n'
import { formatAuthor } from '../../utils/text'

interface ProfileShelfProps {
  readings: ProfileReading[]
  locale: Locale
}

function workLink(reading: ProfileReading) {
  const params = new URLSearchParams({
    work_key: reading.work_key,
    titulo: reading.titulo,
    autor: reading.autor,
  })
  return {
    to: { pathname: '/obra', search: `?${params.toString()}` },
    state: {
      work: {
        work_key: reading.work_key,
        titulo: reading.titulo,
        autor: reading.autor,
        ano: null,
        idioma_original: '',
        capa_url: reading.capa_url,
      },
    },
  }
}

function statusClass(status: string): string {
  const normalized = status.toLocaleLowerCase()
  if (normalized === 'lendo') return 'reading'
  if (normalized === 'lido') return 'read'
  if (normalized === 'quero ler') return 'wanted'
  return 'custom'
}

export function ProfileShelf({ readings, locale }: ProfileShelfProps) {
  const allLabel = profileText(locale, 'all_statuses')
  const statuses = useMemo(() => [
    allLabel,
    ...Array.from(new Set(readings.map((reading) => reading.status).filter(Boolean))),
  ], [allLabel, readings])
  const [filter, setFilter] = useState(allLabel)

  useEffect(() => setFilter(allLabel), [allLabel])

  const visible = filter === allLabel ? readings : readings.filter((reading) => reading.status === filter)

  return (
    <section className="profile-section" aria-labelledby="profile-shelf-title">
      <header className="profile-section__heading">
        <div>
          <p className="eyebrow">{readings.length} {profileText(locale, 'books')}</p>
          <h2 id="profile-shelf-title">{profileText(locale, 'shelf')}</h2>
        </div>
      </header>
      <div className="profile-filter-chips" aria-label={profileText(locale, 'shelf')}>
        {statuses.map((status) => (
          <button
            key={status}
            type="button"
            className={filter === status ? 'is-active' : ''}
            aria-pressed={filter === status}
            onClick={() => setFilter(status)}
          >
            {status}
          </button>
        ))}
      </div>
      {visible.length === 0 ? (
        <p className="profile-section__empty">{profileText(locale, 'empty_shelf')}</p>
      ) : (
        <div className="profile-shelf-grid">
          {visible.map((reading) => {
            const link = workLink(reading)
            const edition = [reading.editora, reading.ano].filter(Boolean).join(' · ')
            return (
              <article key={reading.leitura_id} className="profile-book-card">
                <Link to={link.to} state={link.state}>
                  <BookCover title={reading.titulo} author={reading.autor} url={reading.capa_url} />
                </Link>
                <div>
                  <span className={`profile-status profile-status--${statusClass(reading.status)}`}>{reading.status}</span>
                  <Link to={link.to} state={link.state}><h3>{reading.titulo}</h3></Link>
                  <p>{formatAuthor(reading.autor)}</p>
                  {edition && <small>{edition}</small>}
                  {reading.nota !== null && <strong className="profile-book-card__rating">{reading.nota.toFixed(1)}/5</strong>}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

interface ProfileHighlightsProps {
  readingNow: ProfileReading[]
  favorites: ProfileReading[]
  locale: Locale
}

export function ProfileHighlights({ readingNow, favorites, locale }: ProfileHighlightsProps) {
  if (readingNow.length === 0 && favorites.length === 0) return null

  return (
    <section className="profile-highlights">
      {readingNow.length > 0 && (
        <div className="profile-highlight-block">
          <div className="profile-highlight-block__heading">
            <p className="eyebrow">{profileText(locale, 'reading_now')}</p>
            <span>{readingNow.length}</span>
          </div>
          <div className="profile-highlight-rail">
            {readingNow.map((reading) => {
              const link = workLink(reading)
              return (
                <article key={reading.leitura_id}>
                  <Link to={link.to} state={link.state}>
                    <BookCover title={reading.titulo} author={reading.autor} url={reading.capa_url} />
                    <strong>{reading.titulo}</strong>
                    <small>{formatAuthor(reading.autor)}</small>
                  </Link>
                </article>
              )
            })}
          </div>
        </div>
      )}

      {favorites.length > 0 && (
        <div className="profile-highlight-block">
          <div className="profile-highlight-block__heading">
            <p className="eyebrow">{profileText(locale, 'favorites')}</p>
            <span>{favorites.length}</span>
          </div>
          <div className="profile-favorite-list">
            {favorites.map((reading, index) => {
              const link = workLink(reading)
              return (
                <Link key={reading.leitura_id} to={link.to} state={link.state}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <div>
                    <strong>{reading.titulo}</strong>
                    <small>{formatAuthor(reading.autor)}</small>
                  </div>
                  {reading.nota !== null && <b>{reading.nota.toFixed(1)}</b>}
                  <Icon name="arrow" size={15} />
                </Link>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}

interface ProfileReviewsProps {
  readings: ProfileReading[]
  locale: Locale
}

export function ProfileReviews({ readings, locale }: ProfileReviewsProps) {
  const [visibleSpoilers, setVisibleSpoilers] = useState<Set<number>>(new Set())

  function toggleSpoiler(readingId: number) {
    setVisibleSpoilers((current) => {
      const next = new Set(current)
      if (next.has(readingId)) next.delete(readingId)
      else next.add(readingId)
      return next
    })
  }

  return (
    <section className="profile-section" aria-labelledby="profile-reviews-title">
      <header className="profile-section__heading">
        <div>
          <p className="eyebrow">{readings.length}</p>
          <h2 id="profile-reviews-title">{profileText(locale, 'reviews')}</h2>
        </div>
      </header>
      {readings.length === 0 ? (
        <p className="profile-section__empty">{profileText(locale, 'empty_reviews')}</p>
      ) : (
        <div className="profile-review-list">
          {readings.map((reading) => {
            const link = workLink(reading)
            const show = !reading.spoiler || visibleSpoilers.has(reading.leitura_id)
            return (
              <article key={reading.leitura_id} className="profile-review-card">
                <Link className="profile-review-card__book" to={link.to} state={link.state}>
                  <BookCover title={reading.titulo} author={reading.autor} url={reading.capa_url} />
                  <div>
                    <h3>{reading.titulo}</h3>
                    <p>{formatAuthor(reading.autor)}</p>
                    {reading.nota !== null && <strong>{reading.nota.toFixed(1)}/5</strong>}
                  </div>
                </Link>
                {reading.spoiler && (
                  <div className="profile-review-card__spoiler">
                    <span>{profileText(locale, 'spoiler')}</span>
                    <button className="text-button" type="button" onClick={() => toggleSpoiler(reading.leitura_id)}>
                      {show ? profileText(locale, 'hide_spoiler') : profileText(locale, 'show_spoiler')}
                    </button>
                  </div>
                )}
                {show ? <p className="profile-review-card__text">{reading.relato}</p> : <div className="profile-review-card__hidden" />}
                <Link className="profile-review-card__link" to={link.to} state={link.state}>
                  {profileText(locale, 'open_work')} <Icon name="arrow" size={14} />
                </Link>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

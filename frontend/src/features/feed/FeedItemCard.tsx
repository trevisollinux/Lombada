import { useCallback, useState } from 'react'
import { Link } from 'react-router'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import {
  likeReview,
  saveReview,
  unlikeReview,
  unsaveReview,
} from '../../services/api'
import type { FeedItem, FeedReviewItem, FeedTextItem } from '../../types/feed'
import { FeedAvatar } from './FeedAvatar'
import { feedText } from './feedI18n'
import { FollowButton } from './FollowButton'
import { ReviewComments } from './ReviewComments'

interface FeedItemCardProps {
  item: FeedItem
  locale: Locale
  loggedIn: boolean
  onFollowChange: (handle: string, following: boolean) => void
}

function formatDate(value: string, locale: Locale): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
}

function activityLabel(item: FeedReviewItem, locale: Locale): string {
  const key = item.tipo === 'wrote_review'
    ? 'wrote_review'
    : item.tipo === 'started_reading'
      ? 'started_reading'
      : item.tipo === 'finished_reading'
        ? 'finished_reading'
        : item.tipo === 'wants_to_read'
          ? 'wants_to_read'
          : 'created_reading'
  return feedText(locale, key)
}

export function FeedItemCard({ item, locale, loggedIn, onFollowChange }: FeedItemCardProps) {
  if (item.tipo === 'wrote_text') {
    return <FeedTextCard item={item} locale={locale} loggedIn={loggedIn} onFollowChange={onFollowChange} />
  }
  return <FeedReviewCard item={item} locale={locale} loggedIn={loggedIn} onFollowChange={onFollowChange} />
}

function FeedReviewCard({ item, locale, loggedIn, onFollowChange }: FeedItemCardProps & { item: FeedReviewItem }) {
  const [reading, setReading] = useState(item.leitura)
  const [spoilerVisible, setSpoilerVisible] = useState(!item.leitura.spoiler)
  const [commentsOpen, setCommentsOpen] = useState(false)
  const [busyAction, setBusyAction] = useState<'like' | 'save' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const workParams = new URLSearchParams({
    work_key: item.livro.work_key,
    titulo: item.livro.titulo,
    autor: item.livro.autor,
  })
  const workState = {
    work: {
      work_key: item.livro.work_key,
      titulo: item.livro.titulo,
      autor: item.livro.autor,
      ano: null,
      idioma_original: '',
      capa_url: item.livro.capa_url,
    },
  }

  const updateCommentsCount = useCallback((count: number) => {
    setReading((current) => ({ ...current, comments_count: count }))
  }, [])

  function requireInteraction(): boolean {
    if (item.usuario.is_me) {
      setActionError(feedText(locale, 'own_review'))
      return false
    }
    if (!loggedIn) {
      setActionError(feedText(locale, 'login_required'))
      return false
    }
    return true
  }

  async function toggleLike() {
    if (busyAction || !requireInteraction()) return
    setBusyAction('like')
    setActionError(null)
    try {
      const result = reading.liked_by_me
        ? await unlikeReview(reading.leitura_id)
        : await likeReview(reading.leitura_id)
      setReading((current) => ({
        ...current,
        liked_by_me: result.liked,
        likes_count: result.likes_count,
      }))
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : feedText(locale, 'error'))
    } finally {
      setBusyAction(null)
    }
  }

  async function toggleSave() {
    if (busyAction || !requireInteraction()) return
    setBusyAction('save')
    setActionError(null)
    try {
      const result = reading.saved_by_me
        ? await unsaveReview(reading.leitura_id)
        : await saveReview(reading.leitura_id)
      setReading((current) => ({ ...current, saved_by_me: result.saved }))
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : feedText(locale, 'error'))
    } finally {
      setBusyAction(null)
    }
  }

  const hasReview = reading.publico && Boolean(reading.relato.trim())
  const editionMeta = [item.edicao.editora, item.edicao.ano].filter(Boolean).join(' · ')

  return (
    <article className={`feed-card feed-card--${item.tipo}`}>
      <header className="feed-card__header">
        <a className="feed-card__identity" href={`/u/${encodeURIComponent(item.usuario.handle)}`}>
          <FeedAvatar
            name={item.usuario.nome}
            handle={item.usuario.handle}
            url={item.usuario.avatar_url}
          />
          <span>
            <strong>{item.usuario.nome || `@${item.usuario.handle}`}</strong>
            <small>@{item.usuario.handle}</small>
          </span>
        </a>
        <div className="feed-card__header-actions">
          <FollowButton
            handle={item.usuario.handle}
            following={item.usuario.is_following}
            isMe={item.usuario.is_me}
            isDemo={item.usuario.is_demo}
            loggedIn={loggedIn}
            locale={locale}
            compact
            onChange={onFollowChange}
          />
          <time dateTime={item.created_at}>{formatDate(item.created_at, locale)}</time>
        </div>
      </header>

      <div className="feed-card__activity">
        <span>{activityLabel(item, locale)}</span>
        {item.usuario.is_demo && <small>demo</small>}
      </div>

      <div className="feed-card__book">
        <Link to={{ pathname: '/obra', search: `?${workParams.toString()}` }} state={workState}>
          <BookCover
            title={item.livro.titulo}
            author={item.livro.autor}
            url={item.livro.capa_url}
            className="feed-card__cover"
          />
        </Link>
        <div className="feed-card__book-copy">
          <Link to={{ pathname: '/obra', search: `?${workParams.toString()}` }} state={workState}>
            <h2>{item.livro.titulo}</h2>
          </Link>
          <p>{item.livro.autor}</p>
          {editionMeta && <small>{feedText(locale, 'edition')} · {editionMeta}</small>}
          {reading.nota !== null && (
            <span className="feed-card__rating">
              {feedText(locale, 'rating')} <strong>{reading.nota.toFixed(1)}</strong>/5
            </span>
          )}
          <Link className="feed-card__book-link" to={{ pathname: '/obra', search: `?${workParams.toString()}` }} state={workState}>
            {feedText(locale, 'open_book')} <Icon name="arrow" size={15} />
          </Link>
        </div>
      </div>

      {hasReview && (
        <section className={`feed-review${reading.spoiler ? ' has-spoiler' : ''}`}>
          {reading.spoiler && (
            <div className="feed-review__spoiler-label">
              <span>{feedText(locale, 'spoiler')}</span>
              <button className="text-button" type="button" onClick={() => setSpoilerVisible((current) => !current)}>
                {spoilerVisible ? feedText(locale, 'hide_spoiler') : feedText(locale, 'reveal_spoiler')}
              </button>
            </div>
          )}
          {spoilerVisible ? <p>{reading.relato}</p> : <div className="feed-review__hidden" aria-hidden="true" />}
        </section>
      )}

      {hasReview && (
        <footer className="feed-card__footer">
          <div className="feed-card__actions">
            <button
              type="button"
              className={reading.liked_by_me ? 'is-active' : ''}
              aria-pressed={reading.liked_by_me}
              disabled={busyAction === 'like'}
              onClick={() => void toggleLike()}
              title={item.usuario.is_me ? feedText(locale, 'own_review') : feedText(locale, 'like')}
            >
              <Icon name="heart" size={18} />
              <span>{reading.likes_count || feedText(locale, 'like')}</span>
            </button>
            <button
              type="button"
              className={commentsOpen ? 'is-active' : ''}
              aria-expanded={commentsOpen}
              onClick={() => setCommentsOpen((current) => !current)}
            >
              <Icon name="comment" size={18} />
              <span>{reading.comments_count || feedText(locale, 'comments')}</span>
            </button>
            <button
              type="button"
              className={reading.saved_by_me ? 'is-active' : ''}
              aria-pressed={reading.saved_by_me}
              disabled={busyAction === 'save'}
              onClick={() => void toggleSave()}
              title={item.usuario.is_me ? feedText(locale, 'own_review') : feedText(locale, 'save')}
            >
              <Icon name="bookmark" size={18} />
              <span>{reading.saved_by_me ? feedText(locale, 'saved') : feedText(locale, 'save')}</span>
            </button>
          </div>
          {actionError && (
            <p className="feed-card__action-error" role="status">
              {actionError}{' '}
              {!loggedIn && <a href="/api/auth/google/login">{feedText(locale, 'sign_in')}</a>}
            </p>
          )}
        </footer>
      )}

      {hasReview && commentsOpen && (
        <ReviewComments
          readingId={reading.leitura_id}
          loggedIn={loggedIn}
          locale={locale}
          onCountChange={updateCommentsCount}
        />
      )}
    </article>
  )
}

function FeedTextCard({ item, locale, loggedIn, onFollowChange }: FeedItemCardProps & { item: FeedTextItem }) {
  const workParams = item.texto.obra
    ? new URLSearchParams({
        work_key: item.texto.obra.work_key,
        titulo: item.texto.obra.titulo,
        autor: item.texto.obra.autor,
      })
    : null

  return (
    <article className="feed-card feed-card--text">
      <header className="feed-card__header">
        <a className="feed-card__identity" href={`/u/${encodeURIComponent(item.usuario.handle)}`}>
          <FeedAvatar
            name={item.usuario.nome}
            handle={item.usuario.handle}
            url={item.usuario.avatar_url}
          />
          <span>
            <strong>{item.usuario.nome || `@${item.usuario.handle}`}</strong>
            <small>@{item.usuario.handle}</small>
          </span>
        </a>
        <div className="feed-card__header-actions">
          <FollowButton
            handle={item.usuario.handle}
            following={item.usuario.is_following}
            isMe={item.usuario.is_me}
            isDemo={item.usuario.is_demo}
            loggedIn={loggedIn}
            locale={locale}
            compact
            onChange={onFollowChange}
          />
          <time dateTime={item.created_at}>{formatDate(item.created_at, locale)}</time>
        </div>
      </header>

      <div className="feed-card__activity">
        <span>{feedText(locale, 'wrote_text')}</span>
        {item.usuario.is_demo && <small>demo</small>}
      </div>

      <section className="feed-text-entry">
        <p className="eyebrow">{feedText(locale, 'wrote_text')}</p>
        <h2>{item.texto.titulo}</h2>
        <p>{item.texto.conteudo}</p>
        {item.texto.obra && workParams && (
          <Link to={{ pathname: '/obra', search: `?${workParams.toString()}` }}>
            {item.texto.obra.titulo} · {item.texto.obra.autor}
            <Icon name="arrow" size={15} />
          </Link>
        )}
      </section>
    </article>
  )
}

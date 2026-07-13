import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import type { Locale } from '../../i18n'
import {
  createReviewComment,
  deleteReviewComment,
  getReviewComments,
} from '../../services/api'
import type { ReviewComment } from '../../types/feed'
import { FeedAvatar } from './FeedAvatar'
import { feedText } from './feedI18n'

interface ReviewCommentsProps {
  readingId: number
  loggedIn: boolean
  locale: Locale
  onCountChange: (count: number) => void
}

function formatDate(value: string, locale: Locale): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
}

export function ReviewComments({ readingId, loggedIn, locale, onCountChange }: ReviewCommentsProps) {
  const [comments, setComments] = useState<ReviewComment[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    setError(null)
    void getReviewComments(readingId, controller.signal)
      .then((payload) => {
        setComments(payload)
        setStatus('ready')
        onCountChange(payload.length)
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : feedText(locale, 'error'))
        setStatus('error')
      })
    return () => controller.abort()
  }, [locale, onCountChange, readingId])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = text.trim()
    if (!normalized || saving) return
    if (!loggedIn) {
      setError(feedText(locale, 'login_required'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await createReviewComment(readingId, normalized)
      setComments((current) => {
        const next = [...current, created]
        onCountChange(next.length)
        return next
      })
      setText('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : feedText(locale, 'error'))
    } finally {
      setSaving(false)
    }
  }

  async function remove(commentId: number) {
    if (deletingId !== null) return
    setDeletingId(commentId)
    setError(null)
    try {
      await deleteReviewComment(commentId)
      setComments((current) => {
        const next = current.filter((comment) => comment.id !== commentId)
        onCountChange(next.length)
        return next
      })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : feedText(locale, 'error'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="review-comments" aria-label={feedText(locale, 'comments')}>
      {status === 'loading' && <p className="review-comments__state">{feedText(locale, 'comment_loading')}</p>}
      {status === 'error' && <p className="review-comments__state" role="alert">{error}</p>}

      {status === 'ready' && comments.length === 0 && (
        <p className="review-comments__state">{feedText(locale, 'comment_empty')}</p>
      )}

      {status === 'ready' && comments.length > 0 && (
        <div className="review-comments__list">
          {comments.map((comment) => {
            const profilePath = `/perfil/${encodeURIComponent(comment.usuario.handle)}`
            return (
              <article key={comment.id} className="review-comment">
                <Link to={profilePath} aria-label={`@${comment.usuario.handle}`}>
                  <FeedAvatar
                    name={comment.usuario.nome}
                    handle={comment.usuario.handle}
                    url={comment.usuario.avatar_url}
                    size="small"
                  />
                </Link>
                <div>
                  <header>
                    <Link to={profilePath}>
                      {comment.usuario.nome || `@${comment.usuario.handle}`}
                    </Link>
                    <time dateTime={comment.criado_em}>{formatDate(comment.criado_em, locale)}</time>
                  </header>
                  <p>{comment.texto}</p>
                  {comment.is_me && (
                    <button
                      className="text-button review-comment__delete"
                      type="button"
                      disabled={deletingId === comment.id}
                      onClick={() => void remove(comment.id)}
                    >
                      {deletingId === comment.id ? '…' : feedText(locale, 'comment_delete')}
                    </button>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}

      <form className="review-comments__form" onSubmit={submit}>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={feedText(locale, 'comment_placeholder')}
          maxLength={500}
          rows={3}
          disabled={saving}
        />
        <div>
          <small>{text.length}/500</small>
          <button className="button button--secondary" type="submit" disabled={saving || !text.trim()}>
            {saving ? '…' : feedText(locale, 'comment_send')}
          </button>
        </div>
      </form>

      {error && status !== 'error' && (
        <p className="review-comments__error" role="status">
          {error}{' '}
          {!loggedIn && <a href="/api/auth/google/login">{feedText(locale, 'sign_in')}</a>}
        </p>
      )}
    </section>
  )
}

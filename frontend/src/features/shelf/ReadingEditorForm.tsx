import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { StarRating } from '../../components/StarRating'
import type { Locale } from '../../i18n'
import { trackProductEvent } from '../../services/analytics'
import { deleteReading, getReadingStatuses, updateReading } from '../../services/api'
import type { ReadingMutation, ShelfReading } from '../../types/reading'
import { shelfText } from './shelfI18n'

interface ReadingEditorFormProps {
  reading: ShelfReading
  locale: Locale
  onCancel: () => void
  onSaved: (reading: ShelfReading) => void
  onDeleted: (readingId: number) => void
}

const DEFAULT_STATUSES = ['Lido', 'Lendo', 'Quero ler']

function uniqueStatuses(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

function statusForAnalytics(value: string): string {
  return DEFAULT_STATUSES.includes(value) ? value : 'custom'
}

export function ReadingEditorForm({
  reading,
  locale,
  onCancel,
  onSaved,
  onDeleted,
}: ReadingEditorFormProps) {
  const [statusValue, setStatusValue] = useState(reading.status)
  const [rating, setRating] = useState<number | null>(reading.nota)
  const [date, setDate] = useState(reading.data || '')
  const [review, setReview] = useState(reading.relato || '')
  const [isPublic, setIsPublic] = useState(reading.publico)
  const [hasSpoiler, setHasSpoiler] = useState(reading.spoiler)
  const [statuses, setStatuses] = useState<string[]>(() => uniqueStatuses([...DEFAULT_STATUSES, reading.status]))
  const [phase, setPhase] = useState<'idle' | 'saving' | 'deleting'>('idle')
  const [deleteArmed, setDeleteArmed] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setStatusValue(reading.status)
    setRating(reading.nota)
    setDate(reading.data || '')
    setReview(reading.relato || '')
    setIsPublic(reading.publico)
    setHasSpoiler(reading.spoiler)
    setDeleteArmed(false)
    setError(null)
  }, [reading])

  useEffect(() => {
    const controller = new AbortController()
    void getReadingStatuses(controller.signal)
      .then((payload) => {
        const custom = payload.custom.map((item) => item.nome)
        setStatuses(uniqueStatuses([...payload.padrao, ...custom, reading.status]))
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setStatuses(uniqueStatuses([...DEFAULT_STATUSES, reading.status]))
      })
    return () => controller.abort()
  }, [reading.status])

  const dirty = useMemo(() => {
    return (
      statusValue !== reading.status ||
      rating !== reading.nota ||
      date.trim() !== (reading.data || '') ||
      review.trim() !== (reading.relato || '') ||
      isPublic !== reading.publico ||
      hasSpoiler !== reading.spoiler
    )
  }, [date, hasSpoiler, isPublic, rating, reading, review, statusValue])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!statusValue.trim() || phase !== 'idle') return

    setPhase('saving')
    setError(null)
    setDeleteArmed(false)

    const payload: ReadingMutation = {
      status: statusValue.trim(),
      nota: rating,
      data: date.trim(),
      relato: review.trim(),
      publico: isPublic,
      spoiler: hasSpoiler,
    }

    try {
      const saved = await updateReading(reading.leitura_id, payload)
      trackProductEvent('reading_updated', {
        source: 'detail',
        status: statusForAnalytics(payload.status),
        has_rating: payload.nota !== null,
        public: payload.publico,
      })
      onSaved({ ...reading, ...saved })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : shelfText(locale, 'save_error'))
    } finally {
      setPhase('idle')
    }
  }

  async function handleDelete() {
    if (phase !== 'idle') return
    if (!deleteArmed) {
      setDeleteArmed(true)
      setError(null)
      return
    }

    setPhase('deleting')
    setError(null)
    try {
      await deleteReading(reading.leitura_id)
      onDeleted(reading.leitura_id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : shelfText(locale, 'delete_error'))
      setDeleteArmed(false)
      setPhase('idle')
    }
  }

  const busy = phase !== 'idle'

  return (
    <form className="reading-editor" onSubmit={handleSubmit}>
      <div className="reading-editor__grid">
        <label className="reading-editor__field">
          <span>{shelfText(locale, 'status')}</span>
          <select
            value={statusValue}
            onChange={(event) => setStatusValue(event.target.value)}
            disabled={busy}
          >
            {statuses.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        </label>

        <div className="reading-editor__field">
          <span>{shelfText(locale, 'rating')}</span>
          <StarRating
            value={rating}
            onChange={setRating}
            disabled={busy}
            clearLabel={shelfText(locale, 'no_rating')}
            ariaLabel={shelfText(locale, 'rating')}
          />
        </div>
      </div>

      <label className="reading-editor__field">
        <span>{shelfText(locale, 'reading_date')}</span>
        <input
          value={date}
          onChange={(event) => setDate(event.target.value)}
          placeholder={shelfText(locale, 'reading_date_placeholder')}
          maxLength={80}
          disabled={busy}
        />
      </label>

      <label className="reading-editor__field">
        <span>{shelfText(locale, 'review')}</span>
        <textarea
          value={review}
          onChange={(event) => setReview(event.target.value)}
          rows={7}
          maxLength={2000}
          placeholder={shelfText(locale, 'review_placeholder')}
          disabled={busy}
        />
        <small>{review.length}/2000</small>
      </label>

      <div className="reading-editor__toggles">
        <label>
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(event) => setIsPublic(event.target.checked)}
            disabled={busy}
          />
          <span>
            <strong>{shelfText(locale, 'make_public')}</strong>
            <small>{shelfText(locale, 'make_public_hint')}</small>
          </span>
        </label>

        <label>
          <input
            type="checkbox"
            checked={hasSpoiler}
            onChange={(event) => setHasSpoiler(event.target.checked)}
            disabled={busy}
          />
          <span>
            <strong>{shelfText(locale, 'mark_spoiler')}</strong>
            <small>{shelfText(locale, 'mark_spoiler_hint')}</small>
          </span>
        </label>
      </div>

      {error && <p className="reading-editor__error" role="alert">{error}</p>}

      <div className="reading-editor__actions">
        <button className="button button--primary" type="submit" disabled={busy || !dirty}>
          {phase === 'saving' ? shelfText(locale, 'saving') : shelfText(locale, 'save_changes')}
        </button>
        <button className="button button--secondary" type="button" onClick={onCancel} disabled={busy}>
          {shelfText(locale, 'cancel')}
        </button>
      </div>

      <section className={`reading-editor__danger${deleteArmed ? ' is-armed' : ''}`}>
        <div>
          <strong>{shelfText(locale, 'remove_reading')}</strong>
          <p>
            {deleteArmed
              ? shelfText(locale, 'remove_confirmation')
              : shelfText(locale, 'remove_hint')}
          </p>
        </div>
        <div className="reading-editor__danger-actions">
          {deleteArmed && (
            <button type="button" className="text-button" onClick={() => setDeleteArmed(false)} disabled={busy}>
              {shelfText(locale, 'keep_reading')}
            </button>
          )}
          <button
            type="button"
            className="reading-editor__delete"
            onClick={() => void handleDelete()}
            disabled={busy}
          >
            {phase === 'deleting'
              ? shelfText(locale, 'deleting')
              : deleteArmed
                ? shelfText(locale, 'confirm_remove')
                : shelfText(locale, 'remove')}
          </button>
        </div>
      </section>
    </form>
  )
}

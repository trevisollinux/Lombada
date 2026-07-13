import { useEffect, useMemo, useState, type FormEvent } from 'react'

import type { Locale } from '../../i18n'
import { ApiError, createReading, getReadingStatuses } from '../../services/api'
import type {
  CatalogEdition,
  CatalogWork,
  ReadingCreateResponse,
} from '../../types/catalog'
import { catalogText } from './catalogI18n'

interface ReadingRegistrationFormProps {
  work: CatalogWork
  edition: CatalogEdition
  locale: Locale
  onCancel: () => void
  onRegistered: (result: ReadingCreateResponse) => void
}

const DEFAULT_STATUSES = ['Lido', 'Lendo', 'Quero ler']
const RATING_OPTIONS = Array.from({ length: 10 }, (_, index) => (index + 1) / 2)

function unique(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

export function ReadingRegistrationForm({
  work,
  edition,
  locale,
  onCancel,
  onRegistered,
}: ReadingRegistrationFormProps) {
  const [statuses, setStatuses] = useState(DEFAULT_STATUSES)
  const [status, setStatus] = useState('Lendo')
  const [rating, setRating] = useState<number | null>(null)
  const [date, setDate] = useState('')
  const [review, setReview] = useState('')
  const [isPublic, setIsPublic] = useState(false)
  const [hasSpoiler, setHasSpoiler] = useState(false)
  const [ownsEdition, setOwnsEdition] = useState(false)
  const [wantsEdition, setWantsEdition] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void getReadingStatuses(controller.signal)
      .then((payload) => {
        setStatuses(unique([...payload.padrao, ...payload.custom.map((item) => item.nome)]))
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setStatuses(DEFAULT_STATUSES)
      })
    return () => controller.abort()
  }, [])

  const editionLabel = useMemo(() => {
    return [edition.editora, edition.ano, edition.idioma].filter(Boolean).join(' · ')
  }, [edition])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return

    setSaving(true)
    setError(null)
    try {
      const result = await createReading({
        work_key: work.work_key,
        titulo: work.titulo,
        autor: work.autor,
        idioma_original: work.idioma_original || '',
        ano_obra: work.ano ?? null,
        ol_edition_key: edition.ol_edition_key || null,
        editora: edition.editora || '',
        tradutor: edition.tradutor || '',
        isbn: edition.isbn || '',
        idioma: edition.idioma || '',
        ano_edicao: edition.ano ?? null,
        capa_url: edition.capa_url || work.capa_url || '',
        paginas: edition.paginas ?? null,
        status,
        nota: rating,
        relato: review.trim(),
        publico: isPublic,
        spoiler: hasSpoiler,
        data: date.trim(),
        tenho_edicao: ownsEdition,
        quero_edicao: wantsEdition,
      })
      onRegistered(result)
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setError(catalogText(locale, 'duplicate'))
      } else {
        setError(cause instanceof Error ? cause.message : catalogText(locale, 'save_error'))
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="catalog-registration" onSubmit={handleSubmit}>
      <div className="catalog-registration__heading">
        <div>
          <p className="eyebrow">{catalogText(locale, 'register_title')}</p>
          <h2>{work.titulo}</h2>
          <p>{editionLabel || catalogText(locale, 'unknown_edition')}</p>
        </div>
        <button className="text-button" type="button" onClick={onCancel} disabled={saving}>
          {catalogText(locale, 'cancel')}
        </button>
      </div>

      <div className="catalog-registration__grid">
        <label className="catalog-registration__field">
          <span>{catalogText(locale, 'status')}</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)} disabled={saving}>
            {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>

        <label className="catalog-registration__field">
          <span>{catalogText(locale, 'rating')}</span>
          <select
            value={rating === null ? '' : String(rating)}
            onChange={(event) => setRating(event.target.value ? Number(event.target.value) : null)}
            disabled={saving}
          >
            <option value="">{catalogText(locale, 'no_rating')}</option>
            {RATING_OPTIONS.map((value) => (
              <option key={value} value={value}>{value.toFixed(1)}</option>
            ))}
          </select>
        </label>
      </div>

      <label className="catalog-registration__field">
        <span>{catalogText(locale, 'reading_date')}</span>
        <input
          value={date}
          onChange={(event) => setDate(event.target.value)}
          placeholder={catalogText(locale, 'reading_date_placeholder')}
          maxLength={80}
          disabled={saving}
        />
      </label>

      <label className="catalog-registration__field">
        <span>{catalogText(locale, 'review')}</span>
        <textarea
          value={review}
          onChange={(event) => setReview(event.target.value)}
          placeholder={catalogText(locale, 'review_placeholder')}
          rows={6}
          maxLength={2000}
          disabled={saving}
        />
        <small>{review.length}/2000</small>
      </label>

      <div className="catalog-registration__toggles">
        <label>
          <input
            type="checkbox"
            checked={ownsEdition}
            onChange={(event) => {
              setOwnsEdition(event.target.checked)
              if (event.target.checked) setWantsEdition(false)
            }}
            disabled={saving}
          />
          <span>{catalogText(locale, 'own_edition')}</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={wantsEdition}
            onChange={(event) => {
              setWantsEdition(event.target.checked)
              if (event.target.checked) setOwnsEdition(false)
            }}
            disabled={saving}
          />
          <span>{catalogText(locale, 'want_edition')}</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(event) => setIsPublic(event.target.checked)}
            disabled={saving}
          />
          <span>{catalogText(locale, 'make_public')}</span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={hasSpoiler}
            onChange={(event) => setHasSpoiler(event.target.checked)}
            disabled={saving}
          />
          <span>{catalogText(locale, 'mark_spoiler')}</span>
        </label>
      </div>

      {error && <p className="catalog-registration__error" role="alert">{error}</p>}

      <div className="catalog-registration__actions">
        <button className="button button--primary" type="submit" disabled={saving}>
          {saving ? catalogText(locale, 'saving') : catalogText(locale, 'save')}
        </button>
        <button className="button button--secondary" type="button" onClick={onCancel} disabled={saving}>
          {catalogText(locale, 'cancel')}
        </button>
      </div>
    </form>
  )
}

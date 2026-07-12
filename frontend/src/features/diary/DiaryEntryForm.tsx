import { useEffect, useMemo, useState, type FormEvent } from 'react'

import type { Locale } from '../../i18n'
import {
  createDiaryEntry,
  getEditionChapters,
  getEditionPages,
  updateDiaryEntry,
} from '../../services/api'
import type { ChapterSuggestion, DiaryEntry, DiaryMutation, DiaryProgressType } from '../../types/diary'
import type { ShelfReading } from '../../types/reading'
import { diaryText } from './diaryI18n'

interface DiaryEntryFormProps {
  readings: ShelfReading[]
  locale: Locale
  entry?: DiaryEntry | null
  initialReadingId?: number | null
  onCancel: () => void
  onSaved: (entry: DiaryEntry, reading: ShelfReading) => void
}

const progressTypes: DiaryProgressType[] = ['pagina', 'porcentagem', 'capitulo', 'livre']

function progressLabel(locale: Locale, type: DiaryProgressType): string {
  const keys: Record<DiaryProgressType, 'page' | 'percent' | 'chapter' | 'free'> = {
    pagina: 'page',
    porcentagem: 'percent',
    capitulo: 'chapter',
    livre: 'free',
  }
  return diaryText(locale, keys[type])
}

function numberOrNull(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function DiaryEntryForm({
  readings,
  locale,
  entry = null,
  initialReadingId = null,
  onCancel,
  onSaved,
}: DiaryEntryFormProps) {
  const editing = Boolean(entry)
  const fallbackReadingId = entry?.leitura_id ?? initialReadingId ?? readings[0]?.leitura_id ?? null
  const [readingId, setReadingId] = useState<number | null>(fallbackReadingId)
  const [progressType, setProgressType] = useState<DiaryProgressType>(entry?.progresso_tipo ?? 'livre')
  const [page, setPage] = useState(entry?.pagina ? String(entry.pagina) : '')
  const [percentage, setPercentage] = useState(entry?.porcentagem !== null && entry?.porcentagem !== undefined ? String(entry.porcentagem) : '')
  const [chapter, setChapter] = useState(entry?.capitulo ?? '')
  const [chapterOrder, setChapterOrder] = useState<number | null>(entry?.capitulo_ordem ?? null)
  const [note, setNote] = useState(entry?.nota ?? '')
  const [isPublic, setIsPublic] = useState(entry?.publico ?? false)
  const [hasSpoiler, setHasSpoiler] = useState(entry?.spoiler ?? false)
  const [totalPages, setTotalPages] = useState('')
  const [knownPages, setKnownPages] = useState<number | null>(null)
  const [chapters, setChapters] = useState<ChapterSuggestion[]>([])
  const [contextLoading, setContextLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedReading = useMemo(
    () => readings.find((reading) => reading.leitura_id === readingId) ?? null,
    [readingId, readings],
  )

  useEffect(() => {
    if (readingId !== null && readings.some((reading) => reading.leitura_id === readingId)) return
    setReadingId(readings[0]?.leitura_id ?? null)
  }, [readingId, readings])

  useEffect(() => {
    setKnownPages(selectedReading?.paginas ?? null)
    setTotalPages('')
    setChapters([])
    setContextLoading(false)

    if (!selectedReading || !['pagina', 'capitulo'].includes(progressType)) return

    const controller = new AbortController()
    setContextLoading(true)
    const request = progressType === 'pagina'
      ? getEditionPages(selectedReading.edicao_id, controller.signal).then((payload) => {
          setKnownPages(payload.paginas)
        })
      : getEditionChapters(selectedReading.edicao_id, controller.signal).then(setChapters)

    void request
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
      })
      .finally(() => {
        if (!controller.signal.aborted) setContextLoading(false)
      })

    return () => controller.abort()
  }, [progressType, selectedReading])

  function chooseProgressType(type: DiaryProgressType) {
    setProgressType(type)
    setError(null)
  }

  function changeChapter(value: string) {
    setChapter(value)
    const match = chapters.find((item) => item.titulo === value)
    setChapterOrder(match?.ordem ?? null)
  }

  function validationMessage(): string | null {
    if (!selectedReading) return diaryText(locale, 'select_book')
    if (progressType === 'pagina' && (!numberOrNull(page) || Number(page) <= 0)) {
      return diaryText(locale, 'validation_page')
    }
    if (progressType === 'porcentagem') {
      const value = numberOrNull(percentage)
      if (value === null || value < 0 || value > 100) return diaryText(locale, 'validation_percent')
    }
    if (progressType === 'capitulo' && !chapter.trim()) return diaryText(locale, 'validation_chapter')
    if (progressType === 'livre' && !note.trim()) return diaryText(locale, 'validation_note')
    return null
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving || !selectedReading) return

    const validation = validationMessage()
    if (validation) {
      setError(validation)
      return
    }

    const payload: DiaryMutation = {
      progresso_tipo: progressType,
      pagina: progressType === 'pagina' || progressType === 'capitulo' ? numberOrNull(page) : null,
      porcentagem: progressType === 'porcentagem' ? numberOrNull(percentage) : null,
      capitulo: progressType === 'capitulo' ? chapter.trim() : '',
      capitulo_ordem: progressType === 'capitulo' ? chapterOrder : null,
      nota: note.trim(),
      publico: isPublic,
      spoiler: hasSpoiler,
    }

    const informedTotal = numberOrNull(totalPages)
    if (!editing && !knownPages && informedTotal && informedTotal > 0) {
      payload.paginas_total = informedTotal
    }
    if (!editing) payload.origem = 'diario'

    setSaving(true)
    setError(null)
    try {
      const saved = entry
        ? await updateDiaryEntry(entry.id, payload)
        : await createDiaryEntry(selectedReading.leitura_id, payload)
      onSaved(saved, selectedReading)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : diaryText(locale, 'save_error'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="diary-form" onSubmit={handleSubmit}>
      <div className="diary-form__heading">
        <div>
          <p className="eyebrow">{editing ? diaryText(locale, 'edit_title') : diaryText(locale, 'create_title')}</p>
          <h2>{selectedReading?.titulo ?? diaryText(locale, 'select_book')}</h2>
        </div>
        <button type="button" className="text-button" onClick={onCancel} disabled={saving}>
          {diaryText(locale, 'close_editor')}
        </button>
      </div>

      <label className="diary-form__field">
        <span>{diaryText(locale, 'select_book')}</span>
        <select
          value={readingId ?? ''}
          onChange={(event) => setReadingId(event.target.value ? Number(event.target.value) : null)}
          disabled={saving || editing}
          required
        >
          <option value="" disabled>{diaryText(locale, 'select_book')}</option>
          {readings.map((reading) => (
            <option key={reading.leitura_id} value={reading.leitura_id}>
              {reading.titulo}{reading.autor ? ` — ${reading.autor}` : ''}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="diary-form__types">
        <legend>{diaryText(locale, 'progress_type')}</legend>
        <div>
          {progressTypes.map((type) => (
            <button
              key={type}
              type="button"
              className={progressType === type ? 'is-active' : ''}
              aria-pressed={progressType === type}
              onClick={() => chooseProgressType(type)}
              disabled={saving}
            >
              {progressLabel(locale, type)}
            </button>
          ))}
        </div>
      </fieldset>

      {progressType === 'pagina' && (
        <div className="diary-form__progress-grid">
          <label className="diary-form__field">
            <span>{diaryText(locale, 'page_label')}</span>
            <input
              type="number"
              min="1"
              max={knownPages ?? undefined}
              value={page}
              onChange={(event) => setPage(event.target.value)}
              disabled={saving}
              required
            />
          </label>
          {knownPages ? (
            <div className="diary-form__known-total">
              <span>{diaryText(locale, 'page_of')}</span>
              <strong>{knownPages}</strong>
            </div>
          ) : (
            <label className="diary-form__field">
              <span>{diaryText(locale, 'total_pages')}</span>
              <input
                type="number"
                min="1"
                max="20000"
                value={totalPages}
                onChange={(event) => setTotalPages(event.target.value)}
                disabled={saving || contextLoading || editing}
              />
              <small>{diaryText(locale, 'total_pages_hint')}</small>
            </label>
          )}
        </div>
      )}

      {progressType === 'porcentagem' && (
        <label className="diary-form__field">
          <span>{diaryText(locale, 'percent_label')}</span>
          <div className="diary-form__percentage">
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={percentage}
              onChange={(event) => setPercentage(event.target.value)}
              disabled={saving}
              required
            />
            <strong>%</strong>
          </div>
        </label>
      )}

      {progressType === 'capitulo' && (
        <div className="diary-form__progress-grid">
          <label className="diary-form__field">
            <span>{diaryText(locale, 'chapter_label')}</span>
            <input
              list="diary-chapters"
              value={chapter}
              onChange={(event) => changeChapter(event.target.value)}
              placeholder={diaryText(locale, 'chapter_placeholder')}
              maxLength={120}
              disabled={saving || contextLoading}
              required
            />
            <datalist id="diary-chapters">
              {chapters.map((item) => (
                <option key={`${item.ordem ?? 'x'}-${item.titulo}`} value={item.titulo} />
              ))}
            </datalist>
          </label>
          <label className="diary-form__field">
            <span>{diaryText(locale, 'chapter_page')}</span>
            <input
              type="number"
              min="1"
              value={page}
              onChange={(event) => setPage(event.target.value)}
              disabled={saving}
            />
          </label>
        </div>
      )}

      <label className="diary-form__field">
        <span>{diaryText(locale, 'note')}</span>
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder={diaryText(locale, 'note_placeholder')}
          rows={6}
          maxLength={2000}
          disabled={saving}
          required={progressType === 'livre'}
        />
        <small>{note.length}/2000</small>
      </label>

      <div className="diary-form__toggles">
        <label>
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(event) => setIsPublic(event.target.checked)}
            disabled={saving}
          />
          <span><strong>{diaryText(locale, 'make_public')}</strong><small>{diaryText(locale, 'make_public_hint')}</small></span>
        </label>
        <label>
          <input
            type="checkbox"
            checked={hasSpoiler}
            onChange={(event) => setHasSpoiler(event.target.checked)}
            disabled={saving}
          />
          <span><strong>{diaryText(locale, 'mark_spoiler')}</strong><small>{diaryText(locale, 'mark_spoiler_hint')}</small></span>
        </label>
      </div>

      {error && <p className="diary-form__error" role="alert">{error}</p>}

      <div className="diary-form__actions">
        <button className="button button--primary" type="submit" disabled={saving || !selectedReading}>
          {saving ? diaryText(locale, 'saving') : diaryText(locale, 'save')}
        </button>
        <button className="button button--secondary" type="button" onClick={onCancel} disabled={saving}>
          {diaryText(locale, 'cancel')}
        </button>
      </div>
    </form>
  )
}

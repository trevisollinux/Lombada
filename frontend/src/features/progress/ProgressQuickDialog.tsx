import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import { trackProductEvent } from '../../services/analytics'
import { createDiaryEntry } from '../../services/api'
import type { DiaryEntry } from '../../types/diary'
import type { ReadingProgressSummary } from '../../types/features'
import type { ShelfReading } from '../../types/reading'
import { getReadingProgress } from './progressApi'
import { progressText } from './progressI18n'

interface ProgressQuickDialogProps {
  reading: ShelfReading | null
  locale: Locale
  onClose: () => void
  onLogged?: (entry: DiaryEntry) => void
}

type ProgressMode = 'pagina' | 'porcentagem'

function initialMode(summary: ReadingProgressSummary | null, reading: ShelfReading): ProgressMode {
  if (summary?.pagina_atual !== null && summary?.pagina_atual !== undefined) return 'pagina'
  if (summary?.paginas_total || reading.paginas) return 'pagina'
  return 'porcentagem'
}

function feedbackInsight(entry: DiaryEntry, mode: ProgressMode): 'page_delta' | 'page_reached' | 'percent_reached' {
  if (entry.paginas_delta && entry.paginas_delta > 0) return 'page_delta'
  return mode === 'pagina' ? 'page_reached' : 'percent_reached'
}

export function ProgressQuickDialog({ reading, locale, onClose, onLogged }: ProgressQuickDialogProps) {
  const [summary, setSummary] = useState<ReadingProgressSummary | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [mode, setMode] = useState<ProgressMode>('pagina')
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<DiaryEntry | null>(null)
  const [error, setError] = useState<string | null>(null)

  function close() {
    if (saved) {
      trackProductEvent('progress_feedback', {
        source: 'quick_action',
        insight_type: feedbackInsight(saved, mode),
        action: 'closed',
      })
    }
    onClose()
  }

  useEffect(() => {
    if (!reading) return
    const activeReading = reading
    const controller = new AbortController()
    setSummary(null)
    setStatus('loading')
    setValue('')
    setSaved(null)
    setError(null)
    void getReadingProgress(activeReading.leitura_id, controller.signal)
      .then((payload) => {
        setSummary(payload)
        setMode(initialMode(payload, activeReading))
        setStatus('ready')
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setMode(activeReading.paginas ? 'pagina' : 'porcentagem')
        setError(cause instanceof Error ? cause.message : progressText(locale, 'load_error'))
        setStatus('error')
      })
    return () => controller.abort()
  }, [locale, reading])

  useEffect(() => {
    if (!reading) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) close()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previous
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [mode, onClose, reading, saved, saving])

  if (!reading) return null
  const activeReading = reading

  function validationMessage(): string | null {
    const numeric = Number(value)
    if (mode === 'pagina') {
      const total = summary?.paginas_total ?? activeReading.paginas
      if (!Number.isInteger(numeric) || numeric <= 0 || (total !== null && total !== undefined && numeric > total)) {
        return progressText(locale, 'validation_page')
      }
      return null
    }
    if (!Number.isFinite(numeric) || numeric < 0 || numeric > 100) {
      return progressText(locale, 'validation_percent')
    }
    return null
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return
    const validation = validationMessage()
    if (validation) {
      setError(validation)
      return
    }

    const numeric = Number(value)
    setSaving(true)
    setError(null)
    try {
      const entry = await createDiaryEntry(activeReading.leitura_id, {
        progresso_tipo: mode,
        pagina: mode === 'pagina' ? numeric : null,
        porcentagem: mode === 'porcentagem' ? numeric : null,
        nota: '',
        publico: false,
        spoiler: false,
        paginas_total: summary?.paginas_total ?? activeReading.paginas,
        origem: 'li_mais',
      })
      setSaved(entry)
      setSummary((current) => current ? {
        ...current,
        pagina_atual: mode === 'pagina' ? numeric : current.pagina_atual,
        porcentagem: mode === 'porcentagem' ? numeric : current.porcentagem,
        sessoes: current.sessoes + 1,
        delta_ultima: entry.paginas_delta,
        paginas_7d: (current.paginas_7d ?? 0) + Math.max(0, entry.paginas_delta ?? 0),
      } : current)
      trackProductEvent('progress_logged', {
        source: 'quick_action',
        progress_type: mode === 'pagina' ? 'page' : 'percentage',
        public: false,
      })
      trackProductEvent('progress_feedback', {
        source: 'quick_action',
        insight_type: feedbackInsight(entry, mode),
        action: 'viewed',
      })
      onLogged?.(entry)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : progressText(locale, 'save_error'))
    } finally {
      setSaving(false)
    }
  }

  const totalPages = summary?.paginas_total ?? activeReading.paginas
  const currentValue = mode === 'pagina' ? summary?.pagina_atual : summary?.porcentagem
  const successMessage = saved?.paginas_delta && saved.paginas_delta > 0
    ? progressText(locale, 'success_delta', { value: saved.paginas_delta })
    : mode === 'pagina'
      ? progressText(locale, 'success_page', { value })
      : progressText(locale, 'success_percent', { value })

  return (
    <div className="progress-dialog-layer">
      <button className="progress-dialog-backdrop" type="button" aria-label={progressText(locale, 'cancel')} onClick={saving ? undefined : close} />
      <section className="progress-dialog" role="dialog" aria-modal="true" aria-labelledby="progress-dialog-title">
        <header>
          <div>
            <p className="eyebrow">{progressText(locale, 'log_more')}</p>
            <h2 id="progress-dialog-title">{progressText(locale, 'quick_title')}</h2>
            <p>{activeReading.titulo}</p>
          </div>
          <button className="icon-button" type="button" onClick={close} disabled={saving}>
            <Icon name="close" />
            <span className="sr-only">{progressText(locale, 'cancel')}</span>
          </button>
        </header>

        {saved ? (
          <div className="progress-dialog__success" role="status">
            <Icon name="diary" size={34} />
            <h3>{successMessage}</h3>
            <p>{progressText(locale, 'continue_copy')}</p>
            <div>
              <button className="button button--primary" type="button" onClick={close}>
                {locale === 'pt-BR' ? 'Concluir' : 'Done'}
              </button>
              <Link
                className="button button--secondary"
                to="/diario"
                onClick={() => {
                  trackProductEvent('progress_feedback', {
                    source: 'quick_action',
                    insight_type: feedbackInsight(saved, mode),
                    action: 'open_diary',
                  })
                  onClose()
                }}
              >
                {progressText(locale, 'open_diary')}
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={submit}>
            <p className="progress-dialog__copy">{progressText(locale, 'quick_copy')}</p>

            <div className="progress-dialog__modes" role="group" aria-label={progressText(locale, 'quick_title')}>
              <button type="button" className={mode === 'pagina' ? 'is-active' : ''} onClick={() => { setMode('pagina'); setValue(''); setError(null) }} disabled={saving}>
                {progressText(locale, 'page')}
              </button>
              <button type="button" className={mode === 'porcentagem' ? 'is-active' : ''} onClick={() => { setMode('porcentagem'); setValue(''); setError(null) }} disabled={saving}>
                {progressText(locale, 'percentage')}
              </button>
            </div>

            <label className="progress-dialog__field">
              <span>{progressText(locale, mode === 'pagina' ? 'current_page' : 'current_percentage')}</span>
              <div>
                <input
                  type="number"
                  inputMode="numeric"
                  min={mode === 'pagina' ? 1 : 0}
                  max={mode === 'pagina' ? totalPages ?? undefined : 100}
                  step={mode === 'pagina' ? 1 : 0.1}
                  value={value}
                  placeholder={currentValue !== null && currentValue !== undefined ? String(currentValue) : ''}
                  onChange={(event) => setValue(event.target.value)}
                  autoFocus
                  disabled={saving}
                  required
                />
                <span>{mode === 'pagina' && totalPages ? `/ ${totalPages}` : mode === 'porcentagem' ? '%' : ''}</span>
              </div>
            </label>

            {status === 'loading' && <p className="progress-dialog__context">{locale === 'pt-BR' ? 'Carregando progresso atual…' : 'Loading current progress…'}</p>}
            {status === 'ready' && summary && (
              <p className="progress-dialog__context">
                {summary.sessoes} {progressText(locale, 'sessions')}
                {summary.paginas_7d !== null ? ` · ${summary.paginas_7d} ${progressText(locale, 'pages_last_week')}` : ''}
              </p>
            )}
            {error && <p className="progress-dialog__error" role="alert">{error}</p>}

            <div className="progress-dialog__actions">
              <button className="button button--primary" type="submit" disabled={saving || !value}>
                {saving ? progressText(locale, 'saving') : progressText(locale, 'save')}
              </button>
              <button className="button button--secondary" type="button" onClick={close} disabled={saving}>
                {progressText(locale, 'cancel')}
              </button>
              <Link className="button button--ghost" to="/diario" onClick={onClose}>
                {progressText(locale, 'open_diary')}
              </Link>
            </div>
          </form>
        )}
      </section>
    </div>
  )
}

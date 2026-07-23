import { useEffect, useState, type FormEvent, type ReactNode } from 'react'

import { Icon } from '../../components/Icon'
import { Portal } from '../../components/Portal'
import type { Locale } from '../../i18n'
import { submitManualBook, type ManualBookPayload } from '../../services/api'
import { manualText } from './manualI18n'

interface ManualBookFormProps {
  locale: Locale
  initialTitle?: string
  onClose: () => void
}

type Fields = {
  titulo: string
  autor: string
  ano_obra: string
  idioma_original: string
  titulo_edicao: string
  editora: string
  tradutor: string
  isbn: string
  idioma: string
  ano_edicao: string
  capa_url: string
  paginas: string
}

function emptyFields(title: string): Fields {
  return {
    titulo: title,
    autor: '',
    ano_obra: '',
    idioma_original: '',
    titulo_edicao: '',
    editora: '',
    tradutor: '',
    isbn: '',
    idioma: '',
    ano_edicao: '',
    capa_url: '',
    paginas: '',
  }
}

function toNumber(value: string): number | null {
  const parsed = Number.parseInt(value.trim(), 10)
  return Number.isFinite(parsed) ? parsed : null
}

export function ManualBookForm({ locale, initialTitle = '', onClose }: ManualBookFormProps) {
  const [fields, setFields] = useState<Fields>(() => emptyFields(initialTitle))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !submitting) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose, submitting])

  function update(key: keyof Fields, value: string) {
    setFields((current) => ({ ...current, [key]: value }))
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    if (!fields.titulo.trim() || !fields.autor.trim()) {
      setError(manualText(locale, 'required_error'))
      return
    }
    setSubmitting(true)
    setError(null)
    const payload: ManualBookPayload = {
      titulo: fields.titulo.trim(),
      autor: fields.autor.trim(),
      ano_obra: toNumber(fields.ano_obra),
      idioma_original: fields.idioma_original.trim(),
      titulo_edicao: fields.titulo_edicao.trim(),
      editora: fields.editora.trim(),
      tradutor: fields.tradutor.trim(),
      isbn: fields.isbn.trim(),
      idioma: fields.idioma.trim(),
      ano_edicao: toNumber(fields.ano_edicao),
      capa_url: fields.capa_url.trim(),
      paginas: toNumber(fields.paginas),
    }
    try {
      await submitManualBook(payload)
      setDone(true)
    } catch {
      setError(manualText(locale, 'error'))
      setSubmitting(false)
    }
  }

  return (
    <Portal>
    <div className="panel-layer" role="presentation">
      <button
        className="panel-backdrop"
        type="button"
        aria-label={manualText(locale, 'close')}
        onClick={submitting ? undefined : onClose}
      />
      <section className="manual-form" role="dialog" aria-modal="true" aria-labelledby="manual-form-title">
        <header className="manual-form__header">
          <div>
            <p className="eyebrow">{manualText(locale, 'cta_button')}</p>
            <h2 id="manual-form-title">{manualText(locale, 'title')}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={submitting && !done}>
            <Icon name="close" />
            <span className="sr-only">{manualText(locale, 'close')}</span>
          </button>
        </header>

        {done ? (
          <div className="manual-form__done">
            <span className="manual-form__done-glyph" aria-hidden="true">✓</span>
            <h3>{manualText(locale, 'success_title')}</h3>
            <p>{manualText(locale, 'success')}</p>
            <button className="button button--primary" type="button" onClick={onClose}>
              {manualText(locale, 'close')}
            </button>
          </div>
        ) : (
          <form className="manual-form__body" onSubmit={submit}>
            <fieldset className="manual-form__group">
              <legend>{manualText(locale, 'book_group')}</legend>
              <Field label={`${manualText(locale, 'work_title')} *`}>
                <input value={fields.titulo} onChange={(e) => update('titulo', e.target.value)} required />
              </Field>
              <Field label={`${manualText(locale, 'author')} *`}>
                <input value={fields.autor} onChange={(e) => update('autor', e.target.value)} required />
              </Field>
              <div className="manual-form__row">
                <Field label={manualText(locale, 'work_year')}>
                  <input inputMode="numeric" value={fields.ano_obra} onChange={(e) => update('ano_obra', e.target.value)} />
                </Field>
                <Field label={manualText(locale, 'original_language')}>
                  <input value={fields.idioma_original} onChange={(e) => update('idioma_original', e.target.value)} />
                </Field>
              </div>
            </fieldset>

            <fieldset className="manual-form__group">
              <legend>{manualText(locale, 'edition_group')}</legend>
              <Field label={manualText(locale, 'edition_title')}>
                <input value={fields.titulo_edicao} onChange={(e) => update('titulo_edicao', e.target.value)} />
              </Field>
              <div className="manual-form__row">
                <Field label={manualText(locale, 'publisher')}>
                  <input value={fields.editora} onChange={(e) => update('editora', e.target.value)} />
                </Field>
                <Field label={manualText(locale, 'translator')}>
                  <input value={fields.tradutor} onChange={(e) => update('tradutor', e.target.value)} />
                </Field>
              </div>
              <div className="manual-form__row">
                <Field label={manualText(locale, 'isbn')}>
                  <input value={fields.isbn} onChange={(e) => update('isbn', e.target.value)} />
                </Field>
                <Field label={manualText(locale, 'language')}>
                  <input value={fields.idioma} onChange={(e) => update('idioma', e.target.value)} />
                </Field>
              </div>
              <div className="manual-form__row">
                <Field label={manualText(locale, 'edition_year')}>
                  <input inputMode="numeric" value={fields.ano_edicao} onChange={(e) => update('ano_edicao', e.target.value)} />
                </Field>
                <Field label={manualText(locale, 'pages')}>
                  <input inputMode="numeric" value={fields.paginas} onChange={(e) => update('paginas', e.target.value)} />
                </Field>
              </div>
              <Field label={manualText(locale, 'cover_url')}>
                <input value={fields.capa_url} onChange={(e) => update('capa_url', e.target.value)} />
              </Field>
            </fieldset>

            {error && <p className="manual-form__error" role="alert">{error}</p>}

            <footer className="manual-form__actions">
              <button type="button" className="text-button" onClick={onClose} disabled={submitting}>
                {manualText(locale, 'cancel')}
              </button>
              <button type="submit" className="button button--primary" disabled={submitting}>
                {submitting ? manualText(locale, 'submitting') : manualText(locale, 'submit')}
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
    </Portal>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="manual-form__field">
      <span>{label}</span>
      {children}
    </label>
  )
}

import { useCallback, useEffect, useState } from 'react'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import {
  getMyEssentials,
  getPublicEssentials,
  getShelf,
  putEssentials,
} from '../../services/api'
import type { EssentialBook } from '../../types/essentials'
import type { ShelfReading } from '../../types/reading'
import { essentialsText } from './essentialsI18n'

interface EssentialBooksProps {
  handle: string
  owner: boolean
  canEdit: boolean
  locale: Locale
}

const SLOTS = [1, 2, 3, 4]

export function EssentialBooks({ handle, owner, canEdit, locale }: EssentialBooksProps) {
  const [books, setBooks] = useState<EssentialBook[]>([])
  const [ready, setReady] = useState(false)
  const [editing, setEditing] = useState(false)

  const load = useCallback((signal?: AbortSignal) => {
    const request = owner ? getMyEssentials(signal) : getPublicEssentials(handle, signal)
    request
      .then((data) => {
        setBooks(data.books)
        setReady(true)
      })
      .catch(() => {
        /* 404 (flag off / perfil sem essenciais): a seção não aparece */
        setReady(true)
      })
  }, [handle, owner])

  useEffect(() => {
    const controller = new AbortController()
    setReady(false)
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  if (!ready) return null
  // público sem essenciais: nada a mostrar. dono vê o convite pra escolher.
  if (books.length === 0 && !canEdit) return null

  const byPosition = new Map(books.map((book) => [book.position, book]))

  return (
    <section className="essentials" aria-labelledby="essentials-title">
      <header className="essentials__head">
        <div>
          <p className="eyebrow">{essentialsText(locale, 'label')}</p>
          <h3 id="essentials-title">{essentialsText(locale, 'title')}</h3>
        </div>
        {canEdit && books.length > 0 && (
          <button className="text-button" type="button" onClick={() => setEditing(true)}>
            <Icon name="settings" size={15} />
            {essentialsText(locale, 'edit')}
          </button>
        )}
      </header>

      {books.length === 0 ? (
        <div className="essentials__empty">
          <p>{essentialsText(locale, 'empty')}</p>
          <button className="button button--secondary" type="button" onClick={() => setEditing(true)}>
            {essentialsText(locale, 'choose')}
          </button>
        </div>
      ) : (
        <ol className="essentials__grid">
          {SLOTS.map((position) => {
            const book = byPosition.get(position)
            return (
              <li key={position} className={`essentials__slot${book ? '' : ' is-empty'}`}>
                {book ? (
                  <>
                    <BookCover title={book.title} author={book.author} url={book.cover_url} />
                    <span className="essentials__rank" aria-hidden="true">{position}</span>
                    <div className="essentials__meta">
                      <strong>{book.title}</strong>
                      {book.author && <span>{book.author}</span>}
                    </div>
                  </>
                ) : (
                  <span className="essentials__rank essentials__rank--empty" aria-hidden="true">{position}</span>
                )}
              </li>
            )
          })}
        </ol>
      )}

      {editing && (
        <EssentialsEditor
          locale={locale}
          initial={books}
          onClose={() => setEditing(false)}
          onSaved={(next) => {
            setBooks(next)
            setEditing(false)
          }}
        />
      )}
    </section>
  )
}

interface EssentialsEditorProps {
  locale: Locale
  initial: EssentialBook[]
  onClose: () => void
  onSaved: (books: EssentialBook[]) => void
}

function EssentialsEditor({ locale, initial, onClose, onSaved }: EssentialsEditorProps) {
  const [shelf, setShelf] = useState<ShelfReading[]>([])
  const [shelfReady, setShelfReady] = useState(false)
  const [selected, setSelected] = useState<string[]>(initial.map((book) => book.work_key))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getShelf(controller.signal)
      .then((rows) => {
        setShelf(Array.isArray(rows) ? rows : [])
        setShelfReady(true)
      })
      .catch(() => setShelfReady(true))
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !saving) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose, saving])

  // dedup por obra — a estante pode ter várias leituras da mesma obra
  const uniqueWorks = Array.from(
    new Map(shelf.filter((row) => row.work_key).map((row) => [row.work_key, row])).values(),
  )
  const labelByKey = new Map(uniqueWorks.map((row) => [row.work_key, row]))

  function toggle(workKey: string) {
    setSelected((current) => {
      if (current.includes(workKey)) return current.filter((key) => key !== workKey)
      if (current.length >= 4) return current
      return [...current, workKey]
    })
  }

  async function save() {
    if (saving) return
    setSaving(true)
    setError(false)
    try {
      const result = await putEssentials(selected)
      onSaved(result.books)
    } catch {
      setError(true)
      setSaving(false)
    }
  }

  return (
    <div className="panel-layer" role="presentation">
      <button className="panel-backdrop" type="button" aria-label={essentialsText(locale, 'close')} onClick={saving ? undefined : onClose} />
      <section className="essentials-editor" role="dialog" aria-modal="true" aria-labelledby="essentials-editor-title">
        <header className="essentials-editor__header">
          <div>
            <p className="eyebrow">{essentialsText(locale, 'label')}</p>
            <h2 id="essentials-editor-title">{essentialsText(locale, 'editor_title')}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={saving}>
            <Icon name="close" />
            <span className="sr-only">{essentialsText(locale, 'close')}</span>
          </button>
        </header>

        <p className="essentials-editor__hint">{essentialsText(locale, 'editor_hint')}</p>

        <div className="essentials-editor__selected" aria-label={essentialsText(locale, 'selected')}>
          {SLOTS.map((position) => {
            const workKey = selected[position - 1]
            const row = workKey ? labelByKey.get(workKey) : undefined
            return (
              <div key={position} className={`essentials-editor__slot${row ? '' : ' is-empty'}`}>
                {row ? (
                  <>
                    <BookCover title={row.titulo} author={row.autor} url={row.capa_url} />
                    <button
                      type="button"
                      className="essentials-editor__remove"
                      aria-label={`${essentialsText(locale, 'position')}`.replace('{n}', String(position))}
                      onClick={() => toggle(workKey)}
                    >
                      <Icon name="close" size={14} />
                    </button>
                  </>
                ) : (
                  <span aria-hidden="true">{position}</span>
                )}
              </div>
            )
          })}
        </div>

        <p className="eyebrow essentials-editor__shelf-label">{essentialsText(locale, 'shelf')}</p>
        {!shelfReady ? (
          <p className="essentials-editor__loading">…</p>
        ) : uniqueWorks.length === 0 ? (
          <p className="essentials-editor__empty">{essentialsText(locale, 'no_shelf')}</p>
        ) : (
          <div className="essentials-editor__shelf">
            {uniqueWorks.map((row) => {
              const active = selected.includes(row.work_key)
              const full = selected.length >= 4 && !active
              return (
                <button
                  key={row.work_key}
                  type="button"
                  className={`essentials-editor__pick${active ? ' is-active' : ''}`}
                  aria-pressed={active}
                  disabled={full}
                  onClick={() => toggle(row.work_key)}
                  title={row.titulo}
                >
                  <BookCover title={row.titulo} author={row.autor} url={row.capa_url} />
                  {active && (
                    <span className="essentials-editor__check" aria-hidden="true">
                      {selected.indexOf(row.work_key) + 1}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        )}

        {error && <p className="essentials-editor__error" role="alert">{essentialsText(locale, 'save_error')}</p>}

        <footer className="essentials-editor__actions">
          <button type="button" className="text-button" onClick={onClose} disabled={saving}>
            {essentialsText(locale, 'cancel')}
          </button>
          <button type="button" className="button button--primary" onClick={() => void save()} disabled={saving}>
            {saving ? essentialsText(locale, 'saving') : essentialsText(locale, 'save')}
          </button>
        </footer>
      </section>
    </div>
  )
}

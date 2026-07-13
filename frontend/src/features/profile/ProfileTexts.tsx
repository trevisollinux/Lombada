import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import {
  createProfileText,
  deleteProfileText,
  updateProfileText,
} from '../../services/api'
import type { ProfileReading, ProfileText, ProfileTextMutation } from '../../types/profile'
import { profileText } from './profileI18n'

interface ProfileTextsProps {
  texts: ProfileText[]
  readings: ProfileReading[]
  owner: boolean
  loggedIn: boolean
  locale: Locale
  onItemsChange?: (texts: ProfileText[]) => void
}

type EditorMode = { kind: 'new' } | { kind: 'edit'; textId: number } | null

function formatDate(value: string, locale: Locale): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(parsed)
}

export function ProfileTexts({
  texts,
  readings,
  owner,
  loggedIn,
  locale,
  onItemsChange,
}: ProfileTextsProps) {
  const [items, setItems] = useState(texts)
  const [editor, setEditor] = useState<EditorMode>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [workKey, setWorkKey] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => setItems(texts), [texts])

  const works = useMemo(() => {
    const byKey = new Map<string, { workKey: string; title: string; author: string }>()
    for (const reading of readings) {
      if (!reading.work_key || byKey.has(reading.work_key)) continue
      byKey.set(reading.work_key, {
        workKey: reading.work_key,
        title: reading.titulo,
        author: reading.autor,
      })
    }
    return [...byKey.values()].sort((a, b) => a.title.localeCompare(b.title, locale))
  }, [locale, readings])

  function setSyncedItems(updater: (current: ProfileText[]) => ProfileText[]) {
    setItems((current) => {
      const next = updater(current)
      onItemsChange?.(next)
      return next
    })
  }

  function closeEditor() {
    setEditor(null)
    setTitle('')
    setContent('')
    setWorkKey('')
    setIsPublic(true)
    setError(null)
  }

  function openNew() {
    setEditor({ kind: 'new' })
    setTitle('')
    setContent('')
    setWorkKey('')
    setIsPublic(true)
    setNotice(null)
    setError(null)
  }

  function openEdit(text: ProfileText) {
    setEditor({ kind: 'edit', textId: text.texto_id })
    setTitle(text.titulo)
    setContent(text.conteudo)
    setWorkKey(text.obra?.work_key || '')
    setIsPublic(text.publico)
    setNotice(null)
    setError(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editor || saving) return
    const normalizedTitle = title.trim()
    const normalizedContent = content.trim()
    if (!normalizedTitle || !normalizedContent) {
      setError('Título e texto são obrigatórios.')
      return
    }

    const payload: ProfileTextMutation = {
      titulo: normalizedTitle,
      conteudo: normalizedContent,
      work_key: workKey || null,
      publico: isPublic,
    }

    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const saved = editor.kind === 'new'
        ? await createProfileText(payload)
        : await updateProfileText(editor.textId, payload)
      setSyncedItems((current) => editor.kind === 'new'
        ? [saved, ...current]
        : current.map((item) => item.texto_id === saved.texto_id ? saved : item))
      closeEditor()
      setNotice(profileText(locale, 'text_saved'))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : profileText(locale, 'profile_error'))
    } finally {
      setSaving(false)
    }
  }

  async function remove(textId: number) {
    if (deleteConfirmId !== textId) {
      setDeleteConfirmId(textId)
      return
    }
    if (deletingId !== null) return
    setDeletingId(textId)
    setError(null)
    try {
      await deleteProfileText(textId)
      setSyncedItems((current) => current.filter((item) => item.texto_id !== textId))
      setDeleteConfirmId(null)
      if (editor?.kind === 'edit' && editor.textId === textId) closeEditor()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : profileText(locale, 'profile_error'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="profile-section profile-texts" aria-labelledby="profile-texts-title">
      <header className="profile-section__heading">
        <div>
          <p className="eyebrow">{owner ? profileText(locale, 'manage_texts') : profileText(locale, 'public_profile')}</p>
          <h2 id="profile-texts-title">{profileText(locale, 'texts')}</h2>
        </div>
        {owner && loggedIn && !editor && (
          <button className="button button--primary" type="button" onClick={openNew}>
            <Icon name="plus" size={17} />
            {profileText(locale, 'new_text')}
          </button>
        )}
      </header>

      {owner && !loggedIn && <p className="profile-section__empty">{profileText(locale, 'login_to_edit')}</p>}

      {owner && loggedIn && editor && (
        <form className="profile-text-editor" onSubmit={submit}>
          <div className="profile-text-editor__heading">
            <h3>{editor.kind === 'new' ? profileText(locale, 'new_text') : profileText(locale, 'edit_text')}</h3>
            <button className="icon-button" type="button" onClick={closeEditor} aria-label={profileText(locale, 'close')}>
              <Icon name="close" size={18} />
            </button>
          </div>
          <label>
            <span>{profileText(locale, 'text_title')}</span>
            <input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            <span>{profileText(locale, 'text_content')}</span>
            <textarea value={content} maxLength={20000} rows={10} onChange={(event) => setContent(event.target.value)} />
            <small>{content.length}/20000</small>
          </label>
          <label>
            <span>{profileText(locale, 'text_work')}</span>
            <select value={workKey} onChange={(event) => setWorkKey(event.target.value)}>
              <option value="">{profileText(locale, 'text_no_work')}</option>
              {works.map((work) => (
                <option key={work.workKey} value={work.workKey}>{work.title} · {work.author}</option>
              ))}
            </select>
          </label>
          <label className="profile-text-editor__visibility">
            <input type="checkbox" checked={isPublic} onChange={(event) => setIsPublic(event.target.checked)} />
            <span>{isPublic ? profileText(locale, 'text_public') : profileText(locale, 'text_private')}</span>
          </label>
          <div className="profile-text-editor__actions">
            <button className="button button--primary" type="submit" disabled={saving}>
              {saving ? '…' : profileText(locale, 'save_text')}
            </button>
            <button className="button button--ghost" type="button" disabled={saving} onClick={closeEditor}>
              {profileText(locale, 'cancel')}
            </button>
          </div>
        </form>
      )}

      {notice && <p className="profile-editor__notice" role="status">{notice}</p>}
      {error && <p className="profile-editor__error" role="alert">{error}</p>}

      {items.length === 0 ? (
        <p className="profile-section__empty">{profileText(locale, 'empty_texts')}</p>
      ) : (
        <div className="profile-text-list">
          {items.map((text) => {
            const params = text.obra ? new URLSearchParams({
              work_key: text.obra.work_key,
              titulo: text.obra.titulo,
              autor: text.obra.autor,
            }) : null
            return (
              <article key={text.texto_id} className="profile-text-card">
                <header>
                  <div>
                    <span className={`profile-visibility profile-visibility--${text.publico ? 'public' : 'private'}`}>
                      {text.publico ? profileText(locale, 'public') : profileText(locale, 'private')}
                    </span>
                    <time dateTime={text.criado_em}>{formatDate(text.criado_em, locale)}</time>
                  </div>
                  {owner && loggedIn && (
                    <div className="profile-text-card__actions">
                      <button className="text-button" type="button" onClick={() => openEdit(text)}>
                        {profileText(locale, 'edit_text')}
                      </button>
                      <button
                        className={`text-button profile-text-card__delete${deleteConfirmId === text.texto_id ? ' is-confirming' : ''}`}
                        type="button"
                        disabled={deletingId === text.texto_id}
                        onClick={() => void remove(text.texto_id)}
                      >
                        {deletingId === text.texto_id
                          ? '…'
                          : deleteConfirmId === text.texto_id
                            ? profileText(locale, 'confirm_delete_text')
                            : profileText(locale, 'delete_text')}
                      </button>
                    </div>
                  )}
                </header>
                <h3>{text.titulo}</h3>
                <p>{text.conteudo}</p>
                {text.obra && params && (
                  <Link to={{ pathname: '/obra', search: `?${params.toString()}` }}>
                    {text.obra.titulo} · {text.obra.autor}
                    <Icon name="arrow" size={14} />
                  </Link>
                )}
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { DiaryEntryCard } from '../features/diary/DiaryEntryCard'
import { DiaryEntryForm } from '../features/diary/DiaryEntryForm'
import { diaryText } from '../features/diary/diaryI18n'
import { ShareCardDialog } from '../features/memories/ShareCardDialog'
import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'
import { getDiary, getShelf } from '../services/api'
import type { DiaryEntry } from '../types/diary'
import type { ShareCardPayload } from '../types/memories'
import type { ShelfReading } from '../types/reading'

type LoadStatus = 'loading' | 'ready' | 'error'

function enrichEntry(entry: DiaryEntry, reading: ShelfReading, previous?: DiaryEntry): DiaryEntry {
  return {
    ...previous,
    ...entry,
    status: reading.status,
    titulo: reading.titulo,
    autor: reading.autor,
    capa_url: reading.capa_url,
  }
}

function sortEntries(entries: DiaryEntry[]): DiaryEntry[] {
  return [...entries].sort((a, b) => b.created_at.localeCompare(a.created_at))
}

export function DiaryPage() {
  const { locale, t } = usePreferences()
  const { account } = useSession()
  const [entries, setEntries] = useState<DiaryEntry[]>([])
  const [readings, setReadings] = useState<ShelfReading[]>([])
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const [filterReadingId, setFilterReadingId] = useState<number | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingEntry, setEditingEntry] = useState<DiaryEntry | null>(null)
  const [shareEntry, setShareEntry] = useState<DiaryEntry | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading')
    setError(null)
    try {
      const [diaryPayload, shelfPayload] = await Promise.all([
        getDiary(signal),
        getShelf(signal),
      ])
      setEntries(Array.isArray(diaryPayload) ? diaryPayload : [])
      setReadings(Array.isArray(shelfPayload) ? shelfPayload : [])
      setStatus('ready')
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      setError(cause instanceof Error ? cause.message : diaryText(locale, 'error'))
      setStatus('error')
    }
  }, [locale])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 3500)
    return () => window.clearTimeout(timer)
  }, [notice])

  const visibleEntries = useMemo(() => {
    if (filterReadingId === null) return entries
    return entries.filter((entry) => entry.leitura_id === filterReadingId)
  }, [entries, filterReadingId])

  const shareReading = shareEntry
    ? readings.find((reading) => reading.leitura_id === shareEntry.leitura_id) || null
    : null
  const sharePayload: ShareCardPayload | null = shareEntry && shareReading
    ? {
        kind: 'diary',
        reading: shareReading,
        entry: shareEntry,
        handle: account?.handle || '',
      }
    : null

  function openCreate() {
    setEditingEntry(null)
    setEditorOpen(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function openEdit(entry: DiaryEntry) {
    setEditingEntry(entry)
    setEditorOpen(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function closeEditor() {
    setEditorOpen(false)
    setEditingEntry(null)
  }

  function handleSaved(saved: DiaryEntry, reading: ShelfReading) {
    if (editingEntry) {
      setEntries((current) => sortEntries(current.map((entry) => (
        entry.id === saved.id ? enrichEntry(saved, reading, entry) : entry
      ))))
      setNotice(diaryText(locale, 'saved'))
    } else {
      setEntries((current) => sortEntries([enrichEntry(saved, reading), ...current]))
      setNotice(diaryText(locale, 'created'))
    }
    closeEditor()
  }

  function handleDeleted(entryId: number) {
    setEntries((current) => current.filter((entry) => entry.id !== entryId))
    if (editingEntry?.id === entryId) closeEditor()
    if (shareEntry?.id === entryId) setShareEntry(null)
    setNotice(diaryText(locale, 'deleted'))
  }

  const initialReadingId = editingEntry?.leitura_id ?? filterReadingId ?? readings[0]?.leitura_id ?? null

  return (
    <section className="page page--diary">
      <PageHeader
        eyebrow={t('diary_eyebrow')}
        title={t('diary_title')}
        description={
          status === 'ready'
            ? `${entries.length} ${diaryText(locale, 'entries')}`
            : t('diary_copy')
        }
        aside={<span className="stage-stamp">05 · memória real</span>}
      />

      {notice && (
        <div className="diary-notice" role="status" aria-live="polite">
          {notice}
        </div>
      )}

      {status === 'ready' && (
        <div className="diary-toolbar">
          <label>
            <span>{diaryText(locale, 'filter_book')}</span>
            <select
              value={filterReadingId ?? ''}
              onChange={(event) => setFilterReadingId(event.target.value ? Number(event.target.value) : null)}
            >
              <option value="">{diaryText(locale, 'all_books')}</option>
              {readings.map((reading) => (
                <option key={reading.leitura_id} value={reading.leitura_id}>
                  {reading.titulo}{reading.autor ? ` — ${reading.autor}` : ''}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button button--primary"
            type="button"
            onClick={openCreate}
            disabled={readings.length === 0}
          >
            <Icon name="plus" size={17} />
            {diaryText(locale, 'new_entry')}
          </button>
        </div>
      )}

      {editorOpen && readings.length > 0 && (
        <section className="diary-editor-shell" aria-label={editingEntry ? diaryText(locale, 'edit_title') : diaryText(locale, 'create_title')}>
          <DiaryEntryForm
            key={editingEntry?.id ?? `new-${initialReadingId ?? 'none'}`}
            readings={readings}
            locale={locale}
            entry={editingEntry}
            initialReadingId={initialReadingId}
            onCancel={closeEditor}
            onSaved={handleSaved}
          />
        </section>
      )}

      {status === 'loading' && (
        <div className="diary-loading" aria-busy="true" aria-label={diaryText(locale, 'loading')}>
          {Array.from({ length: 4 }, (_, index) => (
            <article key={index}><span /><div><i /><i /><i /></div></article>
          ))}
        </div>
      )}

      {status === 'error' && (
        <section className="diary-state diary-state--error" role="alert">
          <Icon name="refresh" size={30} />
          <h2>{diaryText(locale, 'error')}</h2>
          <p>{error}</p>
          <button className="button button--secondary" type="button" onClick={() => void load()}>
            <Icon name="refresh" size={17} />
            {t('retry')}
          </button>
        </section>
      )}

      {status === 'ready' && readings.length === 0 && (
        <section className="diary-state diary-state--empty">
          <div className="diary-empty-mark" aria-hidden="true"><span /><span /><span /></div>
          <div>
            <p className="eyebrow">{t('diary_eyebrow')}</p>
            <h2>{diaryText(locale, 'empty_title')}</h2>
            <p>{diaryText(locale, 'no_readings')}</p>
            <Link className="button button--primary" to="/">
              {diaryText(locale, 'find_book')}
              <Icon name="arrow" size={17} />
            </Link>
          </div>
        </section>
      )}

      {status === 'ready' && readings.length > 0 && entries.length === 0 && !editorOpen && (
        <section className="diary-state diary-state--empty">
          <div className="diary-empty-mark" aria-hidden="true"><span /><span /><span /></div>
          <div>
            <p className="eyebrow">{t('diary_eyebrow')}</p>
            <h2>{diaryText(locale, 'empty_title')}</h2>
            <p>{diaryText(locale, 'empty_copy')}</p>
            <button className="button button--primary" type="button" onClick={openCreate}>
              <Icon name="plus" size={17} />
              {diaryText(locale, 'new_entry')}
            </button>
          </div>
        </section>
      )}

      {status === 'ready' && entries.length > 0 && visibleEntries.length === 0 && (
        <section className="diary-state diary-state--filtered">
          <p>{diaryText(locale, 'empty_copy')}</p>
          <button className="text-button" type="button" onClick={() => setFilterReadingId(null)}>
            {diaryText(locale, 'all_books')}
          </button>
        </section>
      )}

      {status === 'ready' && visibleEntries.length > 0 && (
        <div className="diary-timeline">
          {visibleEntries.map((entry) => (
            <DiaryEntryCard
              key={entry.id}
              entry={entry}
              locale={locale}
              onEdit={openEdit}
              onShare={setShareEntry}
              onDeleted={handleDeleted}
            />
          ))}
        </div>
      )}

      <ShareCardDialog payload={sharePayload} locale={locale} onClose={() => setShareEntry(null)} />
    </section>
  )
}

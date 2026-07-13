import { useEffect, useRef, useState } from 'react'

import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import type {
  ShareCardCoverMode,
  ShareCardPayload,
  ShareCardTheme,
} from '../../types/memories'
import {
  defaultIncludeExcerpt,
  downloadShareCard,
  renderShareCard,
  shareCardFilename,
  shareCardHasExcerpt,
  shareCardHasSpoiler,
  shareCardSupportsCover,
  shareOrDownloadCard,
} from './shareCards'
import { memoriesText } from './memoriesI18n'

const CARD_THEME_KEY = 'lombada_card_theme'

interface ShareCardDialogProps {
  payload: ShareCardPayload | null
  locale: Locale
  onClose: () => void
}

function initialTheme(): ShareCardTheme {
  const saved = localStorage.getItem(CARD_THEME_KEY)
  return saved === 'light' || saved === 'dark' ? saved : 'auto'
}

async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('Copy unavailable')
}

export function ShareCardDialog({ payload, locale, onClose }: ShareCardDialogProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const renderVersion = useRef(0)
  const [theme, setThemeState] = useState<ShareCardTheme>(initialTheme)
  const [coverMode, setCoverMode] = useState<ShareCardCoverMode>('original')
  const [includeExcerpt, setIncludeExcerpt] = useState(false)
  const [rendering, setRendering] = useState(false)
  const [busy, setBusy] = useState<'share' | 'download' | 'copy' | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!payload) return
    setCoverMode('original')
    setIncludeExcerpt(defaultIncludeExcerpt(payload))
    setNotice(null)
    setError(null)
  }, [payload])

  useEffect(() => {
    if (!payload) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [busy, onClose, payload])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!payload || !canvas) return
    const version = ++renderVersion.current
    setRendering(true)
    setError(null)
    void renderShareCard(canvas, payload, { theme, coverMode, includeExcerpt }, locale)
      .catch((cause) => {
        if (version !== renderVersion.current) return
        setError(cause instanceof Error ? cause.message : memoriesText(locale, 'card_error'))
      })
      .finally(() => {
        if (version === renderVersion.current) setRendering(false)
      })
  }, [coverMode, includeExcerpt, locale, payload, theme])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(null), 3200)
    return () => window.clearTimeout(timer)
  }, [notice])

  if (!payload) return null
  const activePayload = payload

  function setTheme(value: ShareCardTheme) {
    setThemeState(value)
    localStorage.setItem(CARD_THEME_KEY, value)
  }

  async function ensureCanvas(): Promise<HTMLCanvasElement> {
    const canvas = canvasRef.current
    if (!canvas) throw new Error(memoriesText(locale, 'card_error'))
    await renderShareCard(canvas, activePayload, { theme, coverMode, includeExcerpt }, locale)
    return canvas
  }

  async function share() {
    if (busy) return
    setBusy('share')
    setError(null)
    setNotice(null)
    try {
      const canvas = await ensureCanvas()
      const result = await shareOrDownloadCard(canvas, activePayload, locale)
      if (result === 'shared') setNotice(memoriesText(locale, 'card_shared'))
      if (result === 'downloaded') setNotice(memoriesText(locale, 'card_downloaded'))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : memoriesText(locale, 'card_error'))
    } finally {
      setBusy(null)
    }
  }

  async function download() {
    if (busy) return
    setBusy('download')
    setError(null)
    setNotice(null)
    try {
      const canvas = await ensureCanvas()
      await downloadShareCard(canvas, shareCardFilename(activePayload))
      setNotice(memoriesText(locale, 'card_downloaded'))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : memoriesText(locale, 'card_error'))
    } finally {
      setBusy(null)
    }
  }

  async function copyProfile() {
    if (busy || !activePayload.handle) return
    setBusy('copy')
    setError(null)
    try {
      await copyText(`${window.location.origin}/u/${encodeURIComponent(activePayload.handle)}`)
      setNotice(memoriesText(locale, 'link_copied'))
    } catch {
      setError(memoriesText(locale, 'card_error'))
    } finally {
      setBusy(null)
    }
  }

  const supportsCover = shareCardSupportsCover(activePayload)
  const hasExcerpt = shareCardHasExcerpt(activePayload)
  const hasSpoiler = shareCardHasSpoiler(activePayload)

  return (
    <div className="share-card-layer" role="presentation">
      <button
        className="share-card-backdrop"
        type="button"
        aria-label={memoriesText(locale, 'close')}
        onClick={busy ? undefined : onClose}
      />
      <section className="share-card-dialog" role="dialog" aria-modal="true" aria-labelledby="share-card-title">
        <header className="share-card-dialog__header">
          <div>
            <p className="eyebrow">{memoriesText(locale, 'reading_memory')}</p>
            <h2 id="share-card-title">{memoriesText(locale, 'card_preview')}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={Boolean(busy)}>
            <Icon name="close" />
            <span className="sr-only">{memoriesText(locale, 'close')}</span>
          </button>
        </header>

        <div className="share-card-dialog__body">
          <div className="share-card-preview-shell">
            <canvas ref={canvasRef} className="share-card-canvas" aria-label={memoriesText(locale, 'card_preview')} />
            {rendering && <span className="share-card-rendering">{memoriesText(locale, 'generating')}</span>}
          </div>

          <aside className="share-card-controls">
            <fieldset>
              <legend>{memoriesText(locale, 'card_theme')}</legend>
              <div className="share-card-choice-grid share-card-choice-grid--three">
                {(['auto', 'light', 'dark'] as ShareCardTheme[]).map((value) => (
                  <label key={value} className={theme === value ? 'is-selected' : ''}>
                    <input
                      type="radio"
                      name="share-card-theme"
                      value={value}
                      checked={theme === value}
                      onChange={() => setTheme(value)}
                    />
                    <span>{memoriesText(locale, value === 'auto' ? 'theme_auto' : value === 'light' ? 'theme_light' : 'theme_dark')}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            {supportsCover && (
              <fieldset>
                <legend>{memoriesText(locale, 'cover_style')}</legend>
                <div className="share-card-choice-grid">
                  {(['original', 'editorial', 'editorial-dark'] as ShareCardCoverMode[]).map((value) => (
                    <label key={value} className={coverMode === value ? 'is-selected' : ''}>
                      <input
                        type="radio"
                        name="share-card-cover"
                        value={value}
                        checked={coverMode === value}
                        onChange={() => setCoverMode(value)}
                      />
                      <span>
                        {memoriesText(
                          locale,
                          value === 'original'
                            ? 'cover_original'
                            : value === 'editorial'
                              ? 'cover_editorial'
                              : 'cover_editorial_dark',
                        )}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}

            {hasExcerpt && (
              <div className="share-card-excerpt-control">
                <label>
                  <input
                    type="checkbox"
                    checked={includeExcerpt}
                    onChange={(event) => setIncludeExcerpt(event.target.checked)}
                  />
                  <span>{memoriesText(locale, 'include_excerpt')}</span>
                </label>
                {hasSpoiler && <p>{memoriesText(locale, 'excerpt_spoiler_warning')}</p>}
              </div>
            )}

            <div className="share-card-actions">
              <button className="button button--primary" type="button" disabled={Boolean(busy) || rendering} onClick={() => void share()}>
                <Icon name="external" size={17} />
                {busy === 'share' ? memoriesText(locale, 'generating') : memoriesText(locale, 'share_card')}
              </button>
              <button className="button button--secondary" type="button" disabled={Boolean(busy) || rendering} onClick={() => void download()}>
                {busy === 'download' ? memoriesText(locale, 'generating') : memoriesText(locale, 'download_card')}
              </button>
              {activePayload.handle && (
                <button className="button button--ghost" type="button" disabled={Boolean(busy)} onClick={() => void copyProfile()}>
                  {memoriesText(locale, 'copy_profile_link')}
                </button>
              )}
            </div>

            {notice && <p className="share-card-notice" role="status">{notice}</p>}
            {error && <p className="share-card-error" role="alert">{error}</p>}
          </aside>
        </div>
      </section>
    </div>
  )
}

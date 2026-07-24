import { useEffect, useState } from 'react'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import { Portal } from '../../components/Portal'
import type { Locale } from '../../i18n'
import { useFeatureFlags } from '../../providers/FeatureFlagsProvider'
import { useSession } from '../../providers/SessionProvider'
import type { ShelfReading } from '../../types/reading'
import { memoriesText } from '../memories/memoriesI18n'
import { ShareCardDialog } from '../memories/ShareCardDialog'
import { ProgressQuickDialog } from '../progress/ProgressQuickDialog'
import { progressText } from '../progress/progressI18n'
import { ReadingEditorForm } from './ReadingEditorForm'
import { shelfText } from './shelfI18n'
import { formatAuthor } from '../../utils/text'

interface ReadingDetailPanelProps {
  reading: ShelfReading | null
  locale: Locale
  onClose: () => void
  onUpdated: (reading: ShelfReading) => void
  onDeleted: (readingId: number) => void
}

function ratingLabel(value: number | null): string {
  if (value === null) return '—'
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function ReadingDetailPanel({
  reading,
  locale,
  onClose,
  onUpdated,
  onDeleted,
}: ReadingDetailPanelProps) {
  const { account } = useSession()
  const { enabled, status: featureStatus } = useFeatureFlags()
  const [editing, setEditing] = useState(false)
  const [sharing, setSharing] = useState(false)
  const [progressOpen, setProgressOpen] = useState(false)
  const progressEnabled = featureStatus === 'ready' && enabled('progress_sessions')

  useEffect(() => {
    setEditing(false)
    setSharing(false)
    setProgressOpen(false)
  }, [reading?.leitura_id])

  const isOpen = Boolean(reading)

  // Trava a rolagem do fundo só quando o painel abre/fecha. Não pode depender de
  // editing/sharing/progressOpen: reexecutar aqui a cada troca de estado faz o
  // overflow do body oscilar e, com os diálogos aninhados (progresso/share) que
  // também travam o body, sobra um `overflow: hidden` preso — o app inteiro fica
  // sem rolar.
  useEffect(() => {
    if (!isOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [isOpen])

  useEffect(() => {
    if (!reading) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || sharing || progressOpen) return
      if (editing) setEditing(false)
      else onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [editing, onClose, progressOpen, reading, sharing])

  if (!reading) return null

  const editionMeta = [
    reading.editora,
    reading.ano,
    reading.paginas ? `${reading.paginas} ${shelfText(locale, 'pages')}` : '',
  ].filter(Boolean)

  return (
    <Portal>
      <div className="reading-detail-layer">
        <button
          className="reading-detail-backdrop"
          type="button"
          aria-label={shelfText(locale, 'close_detail')}
          onClick={onClose}
        />
        <aside
          className={`reading-detail${editing ? ' reading-detail--editing' : ''}`}
          role="dialog"
          aria-modal="true"
          aria-labelledby="reading-detail-title"
        >
          <div className="reading-detail__topbar">
            <span className="reading-detail__status">{reading.status}</span>
            <div className="reading-detail__topbar-actions">
              {!editing && (
                <button className="reading-detail__edit-trigger" type="button" onClick={() => setEditing(true)}>
                  {shelfText(locale, 'edit_reading')}
                </button>
              )}
              <button className="icon-button" type="button" onClick={onClose}>
                <Icon name="close" />
                <span className="sr-only">{shelfText(locale, 'close_detail')}</span>
              </button>
            </div>
          </div>

          <div className="reading-detail__hero">
            <BookCover
              title={reading.titulo}
              author={reading.autor}
              url={reading.capa_url}
              className="reading-detail__cover"
            />
            <div>
              <p className="eyebrow">{shelfText(locale, 'edition')}</p>
              <h2 id="reading-detail-title">{reading.titulo}</h2>
              <p className="reading-detail__author">{formatAuthor(reading.autor) || '—'}</p>
              {editionMeta.length > 0 && (
                <p className="reading-detail__edition-meta">{editionMeta.join(' · ')}</p>
              )}
            </div>
          </div>

          {editing ? (
            <ReadingEditorForm
              reading={reading}
              locale={locale}
              onCancel={() => setEditing(false)}
              onSaved={(updated) => {
                onUpdated(updated)
                setEditing(false)
              }}
              onDeleted={onDeleted}
            />
          ) : (
            <>
              <dl className="reading-detail__facts">
                <div>
                  <dt>{shelfText(locale, 'rating')}</dt>
                  <dd>{ratingLabel(reading.nota)}</dd>
                </div>
                <div>
                  <dt>{shelfText(locale, 'publisher')}</dt>
                  <dd>{reading.editora || '—'}</dd>
                </div>
                <div>
                  <dt>{shelfText(locale, 'translator')}</dt>
                  <dd>{reading.tradutor || '—'}</dd>
                </div>
                <div>
                  <dt>{shelfText(locale, 'isbn')}</dt>
                  <dd>{reading.isbn || '—'}</dd>
                </div>
              </dl>

              <section className="reading-detail__review">
                <div className="reading-detail__section-heading">
                  <h3>{shelfText(locale, 'review')}</h3>
                  <div className="reading-detail__badges">
                    <span>{reading.publico ? shelfText(locale, 'public_review') : shelfText(locale, 'private_review')}</span>
                    {reading.spoiler && <span className="is-warning">{shelfText(locale, 'spoiler')}</span>}
                  </div>
                </div>
                <p>{reading.relato || shelfText(locale, 'no_review')}</p>
              </section>

              {(reading.tenho_edicao || reading.quero_edicao) && (
                <div className="reading-detail__relations">
                  {reading.tenho_edicao && <span>{shelfText(locale, 'owned')}</span>}
                  {reading.quero_edicao && <span>{shelfText(locale, 'wanted')}</span>}
                </div>
              )}

              <div className="reading-detail__actions">
                {progressEnabled && reading.status === 'Lendo' && (
                  <button className="button button--primary" type="button" onClick={() => setProgressOpen(true)}>
                    <Icon name="plus" size={17} />
                    {progressText(locale, 'log_more')}
                  </button>
                )}
                <button className="button button--secondary" type="button" onClick={() => setSharing(true)}>
                  <Icon name="memory" size={17} />
                  {memoriesText(locale, 'share_card')}
                </button>
                <button className="button button--secondary" type="button" onClick={() => setEditing(true)}>
                  {shelfText(locale, 'edit_reading')}
                </button>
              </div>
            </>
          )}
        </aside>
      </div>

      <ProgressQuickDialog
        reading={progressOpen ? reading : null}
        locale={locale}
        onClose={() => setProgressOpen(false)}
      />

      <ShareCardDialog
        payload={sharing ? { kind: 'reading', reading, handle: account?.handle || '' } : null}
        locale={locale}
        onClose={() => setSharing(false)}
      />
    </Portal>
  )
}

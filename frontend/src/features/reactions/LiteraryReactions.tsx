import { useEffect, useState } from 'react'

import type { Locale } from '../../i18n'
import {
  getReviewReactions,
  removeReviewReaction,
  setReviewReaction,
} from '../../services/api'
import type { ReactionSummary, ReactionType } from '../../types/reactions'
import { reactionTypes } from '../../types/reactions'
import { reactionIcons, reactionLabel, reactionsText } from './reactionsI18n'

interface LiteraryReactionsProps {
  readingId: number
  locale: Locale
  loggedIn: boolean
}

/* Barra de reações literárias numa crítica pública. O dono nunca vê quem
   reagiu — só a contagem agregada. Cada leitor mantém no máximo uma reação;
   clicar na ativa remove, clicar em outra troca. Gated pela flag
   literary_reactions no ponto de uso. */
export function LiteraryReactions({ readingId, locale, loggedIn }: LiteraryReactionsProps) {
  const [summary, setSummary] = useState<ReactionSummary | null>(null)
  const [busy, setBusy] = useState<ReactionType | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getReviewReactions(readingId, controller.signal)
      .then((next) => setSummary(next))
      .catch(() => {
        /* 404 (flag off / crítica sumiu) ou rede: a barra simplesmente não aparece */
      })
    return () => controller.abort()
  }, [readingId])

  if (!summary) return null
  // sem reações e sem poder reagir: nada a mostrar
  if (summary.total === 0 && !summary.can_react) return null

  async function toggle(type: ReactionType) {
    if (!summary || !summary.can_react || busy) return
    setBusy(type)
    setError(false)
    const removing = summary.mine === type
    try {
      const next = removing
        ? await removeReviewReaction(readingId)
        : await setReviewReaction(readingId, type)
      setSummary(next)
    } catch {
      setError(true)
    } finally {
      setBusy(null)
    }
  }

  const readOnly = !summary.can_react

  return (
    <div className="literary-reactions" aria-busy={busy ? true : undefined}>
      <p className="literary-reactions__label">{reactionsText(locale, 'heading')}</p>
      <div className="literary-reactions__chips">
        {reactionTypes.map((type) => {
          const count = summary.counts[type] || 0
          const active = summary.mine === type
          return (
            <button
              key={type}
              type="button"
              className={`literary-reaction-chip${active ? ' is-active' : ''}${readOnly ? ' is-readonly' : ''}`}
              aria-pressed={active}
              disabled={readOnly || busy !== null}
              onClick={() => void toggle(type)}
              title={reactionLabel(locale, type)}
            >
              <span className="literary-reaction-chip__icon" aria-hidden="true">
                {reactionIcons[type]}
              </span>
              <span>{reactionLabel(locale, type)}</span>
              {count > 0 && <b>{count}</b>}
            </button>
          )
        })}
      </div>
      {error && <p className="literary-reactions__error" role="status">{reactionsText(locale, 'error')}</p>}
      {!summary.connected && !loggedIn && (
        <p className="literary-reactions__connect">
          <a href="/api/auth/google/login">{reactionsText(locale, 'connect')}</a>
        </p>
      )}
    </div>
  )
}

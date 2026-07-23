import { useEffect, useState } from 'react'

import type { Locale } from '../../i18n'
import { getReactionInbox, markReactionInboxSeen } from '../../services/api'
import type { ReactionInboxResponse } from '../../types/reactions'
import { reactionTypes } from '../../types/reactions'
import { reactionIcons, reactionLabel, reactionsCountLabel, reactionsText } from './reactionsI18n'

interface ReactionInboxProps {
  locale: Locale
}

/* Retorno social pro dono: quem reagiu às críticas dele, agregado por obra
   (nunca por pessoa). Abrir marca como visto, zerando o "nova". Gated pela
   flag literary_reactions e só renderiza pro dono conectado no ponto de uso. */
export function ReactionInbox({ locale }: ReactionInboxProps) {
  const [data, setData] = useState<ReactionInboxResponse | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getReactionInbox(controller.signal)
      .then((next) => {
        setData(next)
        // visualizar o retorno já marca como visto (some o "nova" na próxima)
        if (next.unread_groups > 0) void markReactionInboxSeen().catch(() => {})
      })
      .catch(() => {
        /* 401/404 (não conectado / flag off): a seção não aparece */
      })
    return () => controller.abort()
  }, [])

  if (!data || data.groups.length === 0) return null

  return (
    <section className="reaction-inbox" aria-labelledby="reaction-inbox-title">
      <header className="reaction-inbox__head">
        <div>
          <p className="eyebrow">{reactionsText(locale, 'inbox_label')}</p>
          <h3 id="reaction-inbox-title">{reactionsText(locale, 'inbox_title')}</h3>
        </div>
        {data.unread_groups > 0 && (
          <span className="reaction-inbox__badge">{data.unread_groups}</span>
        )}
      </header>

      <ul className="reaction-inbox__list">
        {data.groups.map((group) => (
          <li
            key={group.reading_id}
            className={`reaction-inbox__item${group.unread ? ' is-unread' : ''}`}
          >
            <span className="reaction-inbox__cover" aria-hidden="true">
              {group.cover_url ? (
                <img src={group.cover_url} alt="" loading="lazy" />
              ) : (
                <span>{(group.title || '?').charAt(0)}</span>
              )}
            </span>
            <div className="reaction-inbox__copy">
              <div className="reaction-inbox__title-row">
                <strong>{group.title || `#${group.reading_id}`}</strong>
                {group.unread && <em>{reactionsText(locale, 'unread')}</em>}
              </div>
              {group.author && <p className="reaction-inbox__author">{group.author}</p>}
              <p className="reaction-inbox__breakdown">
                {reactionTypes
                  .filter((type) => group.counts[type] > 0)
                  .map((type) => (
                    <span key={type} title={reactionLabel(locale, type)}>
                      <b aria-hidden="true">{reactionIcons[type]}</b>
                      {group.counts[type]}
                    </span>
                  ))}
              </p>
              <small>{reactionsCountLabel(locale, group.total)}</small>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

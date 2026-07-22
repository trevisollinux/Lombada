import type { Locale } from '../../i18n'
import type { AppNotification } from '../../types/notifications'
import { interpolate, notificationsText } from './notificationsI18n'

/* "há 3 min" / "há 2 h" / "há 5 d", com fallback pra data curta em datas
   mais antigas. Espelha o dataFeed do app legado. */
export function relativeTime(value: string, locale: Locale): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  const diffMs = Date.now() - parsed.getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return notificationsText(locale, 'now')
  if (minutes < 60) return interpolate(notificationsText(locale, 'minutes'), { n: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return interpolate(notificationsText(locale, 'hours'), { n: hours })
  const days = Math.floor(hours / 24)
  if (days < 7) return interpolate(notificationsText(locale, 'days'), { n: days })
  return new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short' }).format(parsed)
}

export function notificationLabel(notification: AppNotification, locale: Locale): string {
  const actor = notification.ator
  const nome = (actor.nome || '').trim() || `@${actor.handle}`
  const titulo = notification.obra?.titulo || ''
  if (notification.tipo === 'follow') {
    return interpolate(notificationsText(locale, 'follow'), { nome })
  }
  if (notification.tipo === 'like') {
    return titulo
      ? interpolate(notificationsText(locale, 'like_book'), { nome, titulo })
      : interpolate(notificationsText(locale, 'like'), { nome })
  }
  return titulo
    ? interpolate(notificationsText(locale, 'comment_book'), { nome, titulo })
    : interpolate(notificationsText(locale, 'comment'), { nome })
}

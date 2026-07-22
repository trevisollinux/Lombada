import type { Locale } from '../../i18n'

export type NotificationsTextKey =
  | 'title'
  | 'open'
  | 'close'
  | 'loading'
  | 'error'
  | 'retry'
  | 'empty'
  | 'login_required'
  | 'demo_badge'
  | 'follow'
  | 'like'
  | 'like_book'
  | 'comment'
  | 'comment_book'
  | 'now'
  | 'minutes'
  | 'hours'
  | 'days'

const messages: Record<Locale, Record<NotificationsTextKey, string>> = {
  'pt-BR': {
    title: 'Atividade',
    open: 'Abrir atividade',
    close: 'Fechar atividade',
    loading: 'carregando atividade…',
    error: 'não consegui carregar a atividade agora.',
    retry: 'Tentar novamente',
    empty:
      'nenhuma atividade ainda. quando alguém seguir você ou curtir uma crítica, aparece aqui.',
    login_required: 'entre com Google pra ver sua atividade.',
    demo_badge: 'demo',
    follow: '{nome} começou a seguir você',
    like: '{nome} curtiu sua crítica',
    like_book: '{nome} curtiu sua crítica sobre {titulo}',
    comment: '{nome} comentou na sua crítica',
    comment_book: '{nome} comentou na sua crítica sobre {titulo}',
    now: 'agora',
    minutes: 'há {n} min',
    hours: 'há {n} h',
    days: 'há {n} d',
  },
  en: {
    title: 'Activity',
    open: 'Open activity',
    close: 'Close activity',
    loading: 'loading activity…',
    error: "couldn't load your activity right now.",
    retry: 'Try again',
    empty: 'no activity yet. when someone follows you or likes a review, it shows up here.',
    login_required: 'sign in with Google to see your activity.',
    demo_badge: 'demo',
    follow: '{nome} started following you',
    like: '{nome} liked your review',
    like_book: '{nome} liked your review of {titulo}',
    comment: '{nome} commented on your review',
    comment_book: '{nome} commented on your review of {titulo}',
    now: 'now',
    minutes: '{n}m ago',
    hours: '{n}h ago',
    days: '{n}d ago',
  },
}

export function notificationsText(locale: Locale, key: NotificationsTextKey): string {
  return messages[locale][key]
}

export function interpolate(
  template: string,
  values: Record<string, string | number>,
): string {
  return template.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ''))
}

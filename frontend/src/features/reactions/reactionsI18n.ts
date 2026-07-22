import type { Locale } from '../../i18n'
import type { ReactionType } from '../../types/reactions'

export type ReactionsTextKey =
  | 'heading'
  | 'connect'
  | 'error'
  | 'reactions_one'
  | 'reactions_many'
  | 'inbox_label'
  | 'inbox_title'
  | 'inbox_empty'
  | 'unread'

const labels: Record<Locale, Record<ReactionType, string>> = {
  'pt-BR': {
    want_to_read: 'Quero ler também',
    moved_me: 'Esse me marcou',
    good_reading: 'Boa leitura',
  },
  en: {
    want_to_read: 'I want to read it too',
    moved_me: 'This one stayed with me',
    good_reading: 'Good reading',
  },
  es: {
    want_to_read: 'Quiero leerlo también',
    moved_me: 'Este me marcó',
    good_reading: 'Buena lectura',
  },
}

const messages: Record<Locale, Record<ReactionsTextKey, string>> = {
  'pt-BR': {
    heading: 'Reações literárias',
    connect: 'Conecte o Google para reagir',
    error: 'Não consegui atualizar sua reação agora.',
    reactions_one: '1 reação',
    reactions_many: '{count} reações',
    inbox_label: 'retorno social',
    inbox_title: 'Reações às suas críticas',
    inbox_empty: 'Ninguém reagiu às suas críticas ainda.',
    unread: 'nova',
  },
  en: {
    heading: 'Literary reactions',
    connect: 'Connect Google to react',
    error: "I couldn't update your reaction right now.",
    reactions_one: '1 reaction',
    reactions_many: '{count} reactions',
    inbox_label: 'social return',
    inbox_title: 'Reactions to your reviews',
    inbox_empty: 'No one has reacted to your reviews yet.',
    unread: 'new',
  },
  es: {
    heading: 'Reacciones literarias',
    connect: 'Conecta Google para reaccionar',
    error: 'No pude actualizar tu reacción ahora.',
    reactions_one: '1 reacción',
    reactions_many: '{count} reacciones',
    inbox_label: 'retorno social',
    inbox_title: 'Reacciones a tus reseñas',
    inbox_empty: 'Nadie ha reaccionado a tus reseñas todavía.',
    unread: 'nueva',
  },
}

export function reactionsCountLabel(locale: Locale, count: number): string {
  const template = count === 1 ? messages[locale].reactions_one : messages[locale].reactions_many
  return template.replace('{count}', String(count))
}

export const reactionIcons: Record<ReactionType, string> = {
  want_to_read: '＋',
  moved_me: '✦',
  good_reading: '↗',
}

export function reactionLabel(locale: Locale, type: ReactionType): string {
  return labels[locale][type]
}

export function reactionsText(locale: Locale, key: ReactionsTextKey): string {
  return messages[locale][key]
}

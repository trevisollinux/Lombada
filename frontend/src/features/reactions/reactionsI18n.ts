import type { Locale } from '../../i18n'
import type { ReactionType } from '../../types/reactions'

export type ReactionsTextKey =
  | 'heading'
  | 'connect'
  | 'error'
  | 'reactions_one'
  | 'reactions_many'

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
}

const messages: Record<Locale, Record<ReactionsTextKey, string>> = {
  'pt-BR': {
    heading: 'Reações literárias',
    connect: 'Conecte o Google para reagir',
    error: 'Não consegui atualizar sua reação agora.',
    reactions_one: '1 reação',
    reactions_many: '{count} reações',
  },
  en: {
    heading: 'Literary reactions',
    connect: 'Connect Google to react',
    error: "I couldn't update your reaction right now.",
    reactions_one: '1 reaction',
    reactions_many: '{count} reactions',
  },
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

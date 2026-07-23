export type ReactionType = 'want_to_read' | 'moved_me' | 'good_reading'

export const reactionTypes: readonly ReactionType[] = [
  'want_to_read',
  'moved_me',
  'good_reading',
]

export interface ReactionSummary {
  reading_id: number
  counts: Record<ReactionType, number>
  total: number
  mine: ReactionType | null
  is_owner: boolean
  connected: boolean
  can_react: boolean
}

export interface ReactionMutationResponse extends ReactionSummary {
  action: string
  removed?: boolean
}

export interface ReactionInboxGroup {
  reading_id: number
  counts: Record<ReactionType, number>
  total: number
  last_at: string
  unread: boolean
  title: string
  author: string
  cover_url: string
}

export interface ReactionInboxResponse {
  groups: ReactionInboxGroup[]
  unread_groups: number
  grouped: boolean
  individual_notifications: boolean
}

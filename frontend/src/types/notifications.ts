export type NotificationKind = 'follow' | 'like' | 'comment'

export interface NotificationActor {
  handle: string
  nome: string
  avatar_url: string
  is_demo: boolean
}

export interface NotificationWork {
  titulo: string
  autor: string
}

export interface AppNotification {
  id: number
  tipo: NotificationKind
  lida: boolean
  criado_em: string
  ator: NotificationActor
  leitura_id: number | null
  obra: NotificationWork | null
}

export interface UnreadNotificationsResponse {
  count: number
}

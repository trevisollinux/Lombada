export type FeedItemType =
  | 'wrote_review'
  | 'started_reading'
  | 'wants_to_read'
  | 'finished_reading'
  | 'leitura_criada'
  | 'wrote_text'

export interface FeedUser {
  handle: string
  nome: string
  avatar_url: string
  is_demo: boolean
  is_following: boolean
  is_me: boolean
  bio?: string
  reviews_count?: number
  followers_count?: number
}

export interface FeedBook {
  titulo: string
  autor: string
  work_key: string
  capa_url: string
}

export interface FeedEdition {
  editora: string
  tradutor: string
  ano: number | null
}

export interface FeedReading {
  leitura_id: number
  status: string
  nota: number | null
  publico: boolean
  is_demo: boolean
  spoiler: boolean
  relato: string
  likes_count: number
  liked_by_me: boolean
  saved_by_me: boolean
  reported_by_me: boolean
  comments_count: number
}

export interface FeedReviewItem {
  tipo: Exclude<FeedItemType, 'wrote_text'>
  usuario: FeedUser
  livro: FeedBook
  edicao: FeedEdition
  leitura: FeedReading
  created_at: string
}

export interface FeedText {
  texto_id: number
  titulo: string
  conteudo: string
  trecho: boolean
  publico: boolean
  criado_em: string
  obra: {
    titulo: string
    autor: string
    work_key: string
  } | null
}

export interface FeedTextItem {
  tipo: 'wrote_text'
  usuario: FeedUser
  texto: FeedText
  created_at: string
}

export type FeedItem = FeedReviewItem | FeedTextItem

export interface FollowingFeedResponse {
  following_count: number
  items: FeedItem[]
}

export interface DiscoverFeedResponse {
  reviews: FeedItem[]
  readers: FeedUser[]
}

export interface ReadingNowItem {
  handle: string
  nome: string
  avatar_url: string
  is_demo: boolean
  titulo: string
  autor: string
  capa_url: string
  work_key: string
}

export interface ReadingNowResponse {
  items: ReadingNowItem[]
}

export interface ReviewComment {
  id: number
  texto: string
  criado_em: string
  usuario: {
    handle: string
    nome: string
    avatar_url: string
    is_demo: boolean
  }
  is_me: boolean
}

export interface ReviewStateResponse {
  liked: boolean
  likes_count: number
}

export interface ReviewSavedResponse {
  saved: boolean
}

export interface FollowResponse {
  following: boolean
  followers_count: number
  following_count: number
}

export interface ProfileReading {
  leitura_id: number
  status: string
  nota: number | null
  relato: string
  publico: boolean
  spoiler: boolean
  data: string
  titulo: string
  autor: string
  work_key: string
  editora: string
  tradutor: string
  ano: number | null
  isbn: string
  capa_url: string
  likes_count?: number
  liked_by_me?: boolean
  saved_by_me?: boolean
  reported_by_me?: boolean
  comments_count?: number
}

export interface ProfileStats {
  total: number
  lidos: number
  lendo: number
  quero_ler: number
  media_nota: number | null
}

export interface ProfileText {
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

export interface PublicProfileResponse {
  handle: string
  nome: string
  bio: string
  avatar_url: string
  is_demo: boolean
  leituras: ProfileReading[]
  textos: ProfileText[]
  stats: ProfileStats
  lendo_agora: ProfileReading[]
  ultimas_leituras: ProfileReading[]
  criticas_publicas: ProfileReading[]
  favoritos: ProfileReading[]
  followers_count: number
  following_count: number
  edicoes_possui: number
  edicoes_desejadas: number
  is_following: boolean
  is_me: boolean
}

export interface ProfilePerson {
  handle: string
  nome: string
  bio: string
  avatar_url: string
  is_demo: boolean
  is_following: boolean
  is_me: boolean
}

export interface ProfileMutation {
  nome: string
  handle: string
  bio: string
}

export interface ProfileMutationResponse {
  handle: string
  nome: string
  bio: string
  message: string
}

export interface AvatarMutationResponse {
  avatar_url: string
  avatar_custom: boolean
}

export interface ProfileTextMutation {
  titulo: string
  conteudo: string
  work_key: string | null
  publico: boolean
}

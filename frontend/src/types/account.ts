export type AccountProvider = 'google' | 'anonimo'

export interface Account {
  handle: string
  nome: string
  bio: string
  avatar_url: string
  avatar_custom: boolean
  email: string | null
  logado: boolean
  provedor: AccountProvider
  admin: boolean
  followers_count: number
  following_count: number
  edicoes_possui: number
  edicoes_desejadas: number
}

export type SessionStatus = 'loading' | 'ready' | 'error'

/* 'network': o backend não respondeu (cold start, queda, offline);
   'http': respondeu com erro — o servidor está de pé. */
export type SessionErrorKind = 'network' | 'http'

export type DiaryProgressType = 'pagina' | 'porcentagem' | 'capitulo' | 'livre'

export interface DiaryEntry {
  id: number
  leitura_id: number
  progresso_tipo: DiaryProgressType
  pagina: number | null
  porcentagem: number | null
  capitulo: string
  capitulo_ordem: number | null
  pagina_estimada: number | null
  origem: string
  paginas_delta: number | null
  nota: string
  publico: boolean
  spoiler: boolean
  created_at: string
  updated_at: string
  status?: string
  titulo?: string
  autor?: string
  capa_url?: string
}

export interface DiaryMutation {
  progresso_tipo: DiaryProgressType
  pagina?: number | null
  porcentagem?: number | null
  capitulo?: string
  capitulo_ordem?: number | null
  nota: string
  publico: boolean
  spoiler: boolean
  paginas_total?: number | null
  origem?: 'diario' | 'li_mais'
}

export interface EditionPagesResponse {
  paginas: number | null
  fonte: string | null
}

export interface ChapterSuggestion {
  titulo: string
  ordem: number | null
  fonte: string
}

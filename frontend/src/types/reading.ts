export interface ShelfReading {
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
  edicao_id: number
  ol_edition_key: string | null
  editora: string
  tradutor: string
  ano: number | null
  isbn: string
  capa_url: string
  paginas: number | null
  tenho_edicao: boolean
  quero_edicao: boolean
  li_edicao: boolean
}

export type ShelfView = 'grid' | 'list'

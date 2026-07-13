export interface CatalogEdition {
  edicao_id?: number | null
  ol_edition_key: string | null
  titulo_edicao: string
  editora: string
  tradutor: string
  isbn: string
  idioma: string
  ano: number | null
  capa_url: string
  paginas: number | null
  leituras_count?: number
  leituras?: number
  tem?: number
  querem?: number
  media?: number | null
  estado?: {
    tenho: boolean
    quero: boolean
    li: boolean
  }
}

export interface CatalogWork {
  obra_id?: number | null
  edicao_id?: number | null
  work_key: string
  titulo: string
  autor: string
  ano: number | null
  idioma_original: string
  capa_url: string
  editora?: string
  tem_pt?: boolean
  isbn_match?: boolean
  leituras_count?: number
  nota_media?: number | null
  criticas_publicas?: number
  lendo_agora_count?: number
  edicao_isbn?: CatalogEdition | null
  edicoes?: CatalogEdition[]
  _fonte?: string
}

export interface PopularSearch {
  termo: string
  total: number
}

export interface WorkSocialResponse {
  obra: {
    id?: number
    work_key: string
    titulo: string
    autor: string
    ano?: number | null
    idioma_original?: string
    descricao?: string
  }
  estatisticas: {
    leituras: number
    criticas: number
    media: number | null
    lendo: number
    querem: number
  }
  edicoes: Array<{
    edicao_id: number
    ol_edition_key: string | null
    leituras: number
    tem: number
    querem: number
    media: number | null
    estado: {
      tenho: boolean
      quero: boolean
      li: boolean
    }
    edicao: {
      editora: string
      ano: number | null
      tradutor: string
      isbn: string
      idioma: string
      capa_url: string
      paginas: number | null
    }
  }>
  minha_leitura: {
    leitura_id: number
    edicao_id: number
    status: string
  } | null
}

export interface ReadingCreatePayload {
  work_key: string
  titulo: string
  autor: string
  idioma_original: string
  ano_obra: number | null
  ol_edition_key: string | null
  editora: string
  tradutor: string
  isbn: string
  idioma: string
  ano_edicao: number | null
  capa_url: string
  paginas: number | null
  status: string
  nota: number | null
  relato: string
  publico: boolean
  spoiler: boolean
  data: string
  tenho_edicao: boolean
  quero_edicao: boolean
}

export interface ReadingCreateResponse {
  leitura_id: number
  obra_id: number
  edicao_id: number
}

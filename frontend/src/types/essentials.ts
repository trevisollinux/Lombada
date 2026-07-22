export interface EssentialBook {
  position: number
  work_key: string
  title: string
  author: string
  cover_url: string
  edition_id: number | null
}

export interface MyEssentialsResponse {
  books: EssentialBook[]
  can_edit: boolean
}

export interface PublicEssentialsResponse {
  handle: string
  books: EssentialBook[]
}

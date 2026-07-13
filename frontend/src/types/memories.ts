import type { DiaryEntry } from './diary'
import type { ShelfReading } from './reading'

export type RecapPeriod = 'week' | 'month'
export type ShareCardTheme = 'auto' | 'light' | 'dark'
export type ShareCardCoverMode = 'original' | 'editorial' | 'editorial-dark'

export interface PeriodRecapProgress {
  type: 'page' | 'percentage' | 'chapter' | 'session'
  value?: number
  label?: string
}

export interface PeriodRecapHighlight {
  reading_id: number
  work_key: string
  title: string
  author: string
  cover_url: string
  sessions: number
  pages_advanced: number
  last_progress: PeriodRecapProgress
  latest_at: string
}

export interface PeriodRecap {
  version: number
  period: RecapPeriod
  offset: number
  timezone: string
  start_date: string
  end_date: string
  is_current: boolean
  is_complete: boolean
  state: 'active' | 'empty'
  sessions: number
  active_days: number
  books_touched: number
  pages_advanced: number
  page_sessions_calculable: number
  progress_types: {
    page: number
    percentage: number
    chapter: number
    session: number
  }
  highlights: PeriodRecapHighlight[]
  can_go_newer: boolean
  can_go_older: boolean
  generated_at: string
}

export interface LibraryRecap {
  readBooks: ShelfReading[]
  pages: number
  ratedBooks: ShelfReading[]
  averageRating: number | null
  favorite: ShelfReading | null
  topAuthor: {
    name: string
    books: ShelfReading[]
  } | null
}

export type ShareCardPayload =
  | {
      kind: 'reading'
      reading: ShelfReading
      handle: string
    }
  | {
      kind: 'diary'
      reading: ShelfReading
      entry: DiaryEntry
      handle: string
    }
  | {
      kind: 'period'
      recap: PeriodRecap
      handle: string
    }
  | {
      kind: 'library'
      recap: LibraryRecap
      handle: string
    }

export interface ShareCardOptions {
  theme: ShareCardTheme
  coverMode: ShareCardCoverMode
  includeExcerpt: boolean
}

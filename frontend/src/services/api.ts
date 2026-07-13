import type { Account } from '../types/account'
import type {
  CatalogEdition,
  CatalogLiterature,
  CatalogPublisher,
  CatalogWork,
  ExploreCatalogOptions,
  PopularSearch,
  ReadingCreatePayload,
  ReadingCreateResponse,
  WorkSocialResponse,
} from '../types/catalog'
import type {
  ChapterSuggestion,
  DiaryEntry,
  DiaryMutation,
  EditionPagesResponse,
} from '../types/diary'
import type {
  ReadingMutation,
  ReadingMutationResponse,
  ReadingStatusesResponse,
  ShelfReading,
} from '../types/reading'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(message: string, status: number, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function readError(response: Response): Promise<{ message: string; detail?: unknown }> {
  try {
    const payload = (await response.json()) as {
      detail?: string | { detail?: string; [key: string]: unknown }
    }
    if (typeof payload.detail === 'string') {
      return { message: payload.detail, detail: payload.detail }
    }
    if (payload.detail && typeof payload.detail.detail === 'string') {
      return { message: payload.detail.detail, detail: payload.detail }
    }
    return { message: `Erro ${response.status}`, detail: payload.detail }
  } catch {
    return { message: `Erro ${response.status}` }
  }
}

async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
    ...init,
  })

  if (!response.ok) {
    const error = await readError(response)
    throw new ApiError(error.message, response.status, error.detail)
  }

  return (await response.json()) as T
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'GET', signal })
}

export function getCurrentAccount(signal?: AbortSignal): Promise<Account> {
  return apiGet<Account>('/api/eu', signal)
}

export function getShelf(signal?: AbortSignal): Promise<ShelfReading[]> {
  return apiGet<ShelfReading[]>('/api/prateleira', signal)
}

export function getReadingStatuses(signal?: AbortSignal): Promise<ReadingStatusesResponse> {
  return apiGet<ReadingStatusesResponse>('/api/eu/status', signal)
}

export function updateReading(
  readingId: number,
  payload: ReadingMutation,
): Promise<ReadingMutationResponse> {
  return apiRequest<ReadingMutationResponse>(`/api/prateleira/${readingId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteReading(readingId: number): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>(`/api/prateleira/${readingId}`, {
    method: 'DELETE',
  })
}

export function getDiary(signal?: AbortSignal): Promise<DiaryEntry[]> {
  return apiGet<DiaryEntry[]>('/api/diario', signal)
}

export function createDiaryEntry(
  readingId: number,
  payload: DiaryMutation,
): Promise<DiaryEntry> {
  return apiRequest<DiaryEntry>(`/api/leitura/${readingId}/diario`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateDiaryEntry(entryId: number, payload: DiaryMutation): Promise<DiaryEntry> {
  return apiRequest<DiaryEntry>(`/api/diario/${entryId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteDiaryEntry(entryId: number): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>(`/api/diario/${entryId}`, {
    method: 'DELETE',
  })
}

export function getEditionPages(
  editionId: number,
  signal?: AbortSignal,
): Promise<EditionPagesResponse> {
  return apiGet<EditionPagesResponse>(`/api/edicoes/${editionId}/paginas`, signal)
}

export function getEditionChapters(
  editionId: number,
  signal?: AbortSignal,
): Promise<ChapterSuggestion[]> {
  return apiGet<ChapterSuggestion[]>(`/api/edicoes/${editionId}/capitulos`, signal)
}

export function searchCatalog(query: string, signal?: AbortSignal): Promise<CatalogWork[]> {
  const params = new URLSearchParams({ q: query.trim() })
  return apiGet<CatalogWork[]>(`/api/buscar?${params.toString()}`, signal)
}

export function exploreCatalog(
  options: ExploreCatalogOptions,
  signal?: AbortSignal,
): Promise<CatalogWork[]> {
  const params = new URLSearchParams()
  if (options.query?.trim()) params.set('q', options.query.trim())
  if (options.publisher) params.set('editora', options.publisher)
  if (options.genre) params.set('genero', options.genre)
  if (options.literature) params.set('literatura', options.literature)
  if (options.sort) params.set('ordenar', options.sort)
  if (options.withReviews) params.set('com_criticas', 'true')
  if (options.readingNow) params.set('lendo_agora', 'true')
  if (options.withCover) params.set('com_capa', 'true')
  if (options.withIsbn) params.set('com_isbn', 'true')
  if (options.portuguese) params.set('idioma', 'Português')
  return apiGet<CatalogWork[]>(`/api/buscar?${params.toString()}`, signal)
}

export function getPopularSearches(signal?: AbortSignal): Promise<PopularSearch[]> {
  return apiGet<PopularSearch[]>('/api/buscas/populares', signal)
}

export function getPopularWorks(signal?: AbortSignal): Promise<CatalogWork[]> {
  return apiGet<CatalogWork[]>('/api/explore/populares', signal)
}

export function getCatalogPublishers(signal?: AbortSignal): Promise<CatalogPublisher[]> {
  return apiGet<CatalogPublisher[]>('/api/editoras', signal)
}

export function getCatalogLiteratures(signal?: AbortSignal): Promise<CatalogLiterature[]> {
  return apiGet<CatalogLiterature[]>('/api/literaturas', signal)
}

export function getWorkSocial(
  work: Pick<CatalogWork, 'work_key' | 'titulo' | 'autor'>,
  signal?: AbortSignal,
): Promise<WorkSocialResponse> {
  const params = new URLSearchParams({
    work_key: work.work_key,
    titulo: work.titulo,
    autor: work.autor,
  })
  return apiGet<WorkSocialResponse>(`/api/obra/social?${params.toString()}`, signal)
}

export function getWorkEditions(workKey: string, signal?: AbortSignal): Promise<CatalogEdition[]> {
  const params = new URLSearchParams({ work_key: workKey })
  return apiGet<CatalogEdition[]>(`/api/edicoes?${params.toString()}`, signal)
}

export function createReading(payload: ReadingCreatePayload): Promise<ReadingCreateResponse> {
  return apiRequest<ReadingCreateResponse>('/api/prateleira', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

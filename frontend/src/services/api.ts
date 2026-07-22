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
  DiscoverFeedResponse,
  FollowResponse,
  FollowingFeedResponse,
  ReadingNowResponse,
  ReviewComment,
  ReviewSavedResponse,
  ReviewStateResponse,
} from '../types/feed'
import type { PeriodRecap, RecapPeriod } from '../types/memories'
import type { AppNotification, UnreadNotificationsResponse } from '../types/notifications'
import type {
  AvatarMutationResponse,
  ProfileMutation,
  ProfileMutationResponse,
  ProfilePerson,
  ProfileText,
  ProfileTextMutation,
  PublicProfileResponse,
} from '../types/profile'
import type {
  ReadingMutation,
  ReadingMutationResponse,
  ReadingStatusesResponse,
  ShelfReading,
} from '../types/reading'
import { DEMO_MODE, demoApiRequest } from './demo'

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
  if (DEMO_MODE) {
    return demoApiRequest<T>(path, init)
  }

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

export function getFollowingFeed(limit = 30, signal?: AbortSignal): Promise<FollowingFeedResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  return apiGet<FollowingFeedResponse>(`/api/feed?${params.toString()}`, signal)
}

export function getDiscoverFeed(limit = 24, signal?: AbortSignal): Promise<DiscoverFeedResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  return apiGet<DiscoverFeedResponse>(`/api/feed/discover?${params.toString()}`, signal)
}

export function getReadingNow(
  scope: 'following' | 'discover',
  limit = 12,
  signal?: AbortSignal,
): Promise<ReadingNowResponse> {
  const params = new URLSearchParams({ scope, limit: String(limit) })
  return apiGet<ReadingNowResponse>(`/api/feed/lendo?${params.toString()}`, signal)
}

export function likeReview(readingId: number): Promise<ReviewStateResponse> {
  return apiRequest<ReviewStateResponse>(`/api/reviews/${readingId}/like`, { method: 'POST' })
}

export function unlikeReview(readingId: number): Promise<ReviewStateResponse> {
  return apiRequest<ReviewStateResponse>(`/api/reviews/${readingId}/like`, { method: 'DELETE' })
}

export function saveReview(readingId: number): Promise<ReviewSavedResponse> {
  return apiRequest<ReviewSavedResponse>(`/api/reviews/${readingId}/save`, { method: 'POST' })
}

export function unsaveReview(readingId: number): Promise<ReviewSavedResponse> {
  return apiRequest<ReviewSavedResponse>(`/api/reviews/${readingId}/save`, { method: 'DELETE' })
}

export function getReviewComments(readingId: number, signal?: AbortSignal): Promise<ReviewComment[]> {
  return apiGet<ReviewComment[]>(`/api/reviews/${readingId}/comments`, signal)
}

export function createReviewComment(readingId: number, text: string): Promise<ReviewComment> {
  return apiRequest<ReviewComment>(`/api/reviews/${readingId}/comments`, {
    method: 'POST',
    body: JSON.stringify({ texto: text }),
  })
}

export function deleteReviewComment(commentId: number): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>(`/api/comments/${commentId}`, { method: 'DELETE' })
}

export function followReader(handle: string): Promise<FollowResponse> {
  return apiRequest<FollowResponse>(`/api/u/${encodeURIComponent(handle)}/follow`, { method: 'POST' })
}

export function unfollowReader(handle: string): Promise<FollowResponse> {
  return apiRequest<FollowResponse>(`/api/u/${encodeURIComponent(handle)}/follow`, { method: 'DELETE' })
}

export function getPublicProfile(handle: string, signal?: AbortSignal): Promise<PublicProfileResponse> {
  return apiGet<PublicProfileResponse>(`/api/u/${encodeURIComponent(handle)}`, signal)
}

export function updateProfile(payload: ProfileMutation): Promise<ProfileMutationResponse> {
  return apiRequest<ProfileMutationResponse>('/api/eu/perfil', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function uploadProfileAvatar(data: string): Promise<AvatarMutationResponse> {
  return apiRequest<AvatarMutationResponse>('/api/eu/avatar', {
    method: 'POST',
    body: JSON.stringify({ data }),
  })
}

export function removeProfileAvatar(): Promise<AvatarMutationResponse> {
  return apiRequest<AvatarMutationResponse>('/api/eu/avatar', { method: 'DELETE' })
}

export function getMyProfileTexts(signal?: AbortSignal): Promise<ProfileText[]> {
  return apiGet<ProfileText[]>('/api/eu/textos', signal)
}

export function createProfileText(payload: ProfileTextMutation): Promise<ProfileText> {
  return apiRequest<ProfileText>('/api/eu/textos', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateProfileText(textId: number, payload: ProfileTextMutation): Promise<ProfileText> {
  return apiRequest<ProfileText>(`/api/eu/textos/${textId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteProfileText(textId: number): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>(`/api/eu/textos/${textId}`, { method: 'DELETE' })
}

export function getProfileFollowers(handle: string, signal?: AbortSignal): Promise<ProfilePerson[]> {
  return apiGet<ProfilePerson[]>(`/api/u/${encodeURIComponent(handle)}/followers`, signal)
}

export function getProfileFollowing(handle: string, signal?: AbortSignal): Promise<ProfilePerson[]> {
  return apiGet<ProfilePerson[]>(`/api/u/${encodeURIComponent(handle)}/following`, signal)
}

export function getPeriodRecap(
  period: RecapPeriod,
  offset = 0,
  signal?: AbortSignal,
): Promise<PeriodRecap> {
  const params = new URLSearchParams({ period, offset: String(offset) })
  return apiGet<PeriodRecap>(`/api/eu/retrospectiva?${params.toString()}`, signal)
}

export function getUnreadNotifications(
  signal?: AbortSignal,
): Promise<UnreadNotificationsResponse> {
  return apiGet<UnreadNotificationsResponse>('/api/notificacoes/nao-lidas', signal)
}

/* Abrir a central já marca tudo como lido no servidor — por isso o GET
   também zera a contagem de não-lidas. */
export function getNotifications(
  limit = 30,
  signal?: AbortSignal,
): Promise<AppNotification[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  return apiGet<AppNotification[]>(`/api/notificacoes?${params.toString()}`, signal)
}

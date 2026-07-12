import type { Account } from '../types/account'
import type {
  ReadingMutation,
  ReadingMutationResponse,
  ReadingStatusesResponse,
  ShelfReading,
} from '../types/reading'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string | { detail?: string }
    }
    if (typeof payload.detail === 'string') return payload.detail
    if (payload.detail && typeof payload.detail.detail === 'string') return payload.detail.detail
    return `Erro ${response.status}`
  } catch {
    return `Erro ${response.status}`
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
    throw new ApiError(await readErrorMessage(response), response.status)
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

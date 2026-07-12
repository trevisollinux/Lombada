import type { Account } from '../types/account'

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
    const payload = (await response.json()) as { detail?: string }
    return payload.detail || `Erro ${response.status}`
  } catch {
    return `Erro ${response.status}`
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
  }

  return (await response.json()) as T
}

export function getCurrentAccount(signal?: AbortSignal): Promise<Account> {
  return apiGet<Account>('/api/eu', signal)
}

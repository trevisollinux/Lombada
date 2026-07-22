import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'

import { ApiError, getCurrentAccount } from '../services/api'
import type { Account, SessionErrorKind, SessionStatus } from '../types/account'

interface SessionContextValue {
  account: Account | null
  status: SessionStatus
  error: string | null
  errorKind: SessionErrorKind | null
  refresh: () => Promise<void>
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: PropsWithChildren) {
  const [account, setAccount] = useState<Account | null>(null)
  const [status, setStatus] = useState<SessionStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const [errorKind, setErrorKind] = useState<SessionErrorKind | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading')
    setError(null)
    setErrorKind(null)

    try {
      const nextAccount = await getCurrentAccount(signal)
      setAccount(nextAccount)
      setStatus('ready')
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        return
      }
      setAccount(null)
      setStatus('error')
      setError(cause instanceof Error ? cause.message : 'Erro inesperado')
      setErrorKind(cause instanceof ApiError ? 'http' : 'network')
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const value = useMemo<SessionContextValue>(
    () => ({
      account,
      status,
      error,
      errorKind,
      refresh: async () => load(),
    }),
    [account, error, errorKind, load, status],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error('useSession deve ser usado dentro de SessionProvider')
  }
  return context
}

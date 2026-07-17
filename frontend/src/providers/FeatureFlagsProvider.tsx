import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'

import type {
  FeatureFlagsResponse,
  PublicFeatureName,
  PublicFeatureSnapshot,
} from '../types/features'
import { publicFeatureNames } from '../types/features'

type FeatureStatus = 'loading' | 'ready' | 'error'

interface FeatureFlagsContextValue {
  status: FeatureStatus
  features: PublicFeatureSnapshot
  enabled: (name: PublicFeatureName) => boolean
  refresh: () => Promise<void>
}

function disabledSnapshot(): PublicFeatureSnapshot {
  return Object.fromEntries(publicFeatureNames.map((name) => [name, false])) as PublicFeatureSnapshot
}

const FeatureFlagsContext = createContext<FeatureFlagsContextValue | null>(null)

export function FeatureFlagsProvider({ children }: PropsWithChildren) {
  const [features, setFeatures] = useState<PublicFeatureSnapshot>(disabledSnapshot)
  const [status, setStatus] = useState<FeatureStatus>('loading')

  const refresh = useCallback(async () => {
    setStatus('loading')
    try {
      const response = await fetch('/api/features', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
      })
      if (!response.ok) throw new Error(`Feature flags HTTP ${response.status}`)
      const payload = (await response.json()) as FeatureFlagsResponse
      const next = disabledSnapshot()
      publicFeatureNames.forEach((name) => {
        next[name] = payload.features?.[name] === true
      })
      setFeatures(next)
      setStatus('ready')
    } catch {
      setFeatures(disabledSnapshot())
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const value = useMemo<FeatureFlagsContextValue>(() => ({
    status,
    features,
    enabled: (name) => features[name] === true,
    refresh,
  }), [features, refresh, status])

  return (
    <FeatureFlagsContext.Provider value={value}>
      {children}
    </FeatureFlagsContext.Provider>
  )
}

export function useFeatureFlags(): FeatureFlagsContextValue {
  const context = useContext(FeatureFlagsContext)
  if (!context) throw new Error('useFeatureFlags deve ser usado dentro de FeatureFlagsProvider')
  return context
}

import { useEffect } from 'react'

import { usePreferences } from '../providers/PreferencesProvider'
import { useFeatureFlags } from '../providers/FeatureFlagsProvider'
import { useSession } from '../providers/SessionProvider'
import { setProductAnalyticsEnabled, trackProductEvent } from '../services/analytics'

const OPEN_MARKER = 'lombada_v2_app_opened'

function standaloneMode(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches
    || Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone)
}

export function ProductAnalyticsBridge() {
  const { locale } = usePreferences()
  const { enabled, status: featureStatus } = useFeatureFlags()
  const { status: sessionStatus } = useSession()
  const analyticsEnabled = featureStatus === 'ready' && enabled('product_analytics')

  useEffect(() => {
    setProductAnalyticsEnabled(analyticsEnabled)
  }, [analyticsEnabled])

  useEffect(() => {
    if (!analyticsEnabled || sessionStatus !== 'ready') return
    try {
      if (sessionStorage.getItem(OPEN_MARKER) === '1') return
      sessionStorage.setItem(OPEN_MARKER, '1')
    } catch {
      // A ausência de sessionStorage não impede o evento nem o aplicativo.
    }
    const standalone = standaloneMode()
    trackProductEvent('app_opened', {
      source: standalone ? 'pwa' : 'web',
      locale,
      standalone,
    })
  }, [analyticsEnabled, locale, sessionStatus])

  return null
}

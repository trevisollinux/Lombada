import { useEffect, useRef, useState } from 'react'

import { usePreferences } from '../providers/PreferencesProvider'
import { getAppVersion } from '../services/api'
import { Portal } from './Portal'

const POLL_INTERVAL_MS = 5 * 60 * 1000

/* Compara a versão do servidor (/api/version) com a carregada. Quando um novo
   deploy sobe, oferece recarregar — os assets do Vite têm hash, então o reload
   já pega a versão nova. Silencioso enquanto nada muda. */
export function VersionWatcher() {
  const { t } = usePreferences()
  const baseline = useRef<string | null>(null)
  const [stale, setStale] = useState(false)

  useEffect(() => {
    let active = true

    async function check() {
      try {
        const { version } = await getAppVersion()
        if (!active || !version) return
        if (baseline.current === null) {
          baseline.current = version
        } else if (version !== baseline.current) {
          setStale(true)
        }
      } catch {
        /* rede instável não deve incomodar; tenta de novo no próximo ciclo */
      }
    }

    void check()
    const timer = window.setInterval(check, POLL_INTERVAL_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') void check()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      active = false
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  if (!stale) return null

  return (
    <Portal>
      <div className="version-banner" role="status">
        <span>{t('update_available')}</span>
        <div className="version-banner__actions">
          <button type="button" className="text-button" onClick={() => setStale(false)}>
            {t('update_dismiss')}
          </button>
          <button type="button" className="button button--primary" onClick={() => window.location.reload()}>
            {t('update_action')}
          </button>
        </div>
      </div>
    </Portal>
  )
}

import { useEffect, useState } from 'react'

import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'

/* O backend hiberna no plano gratuito e a primeira requisição pode levar
   ~30s. Sem aviso, a tela fica parada tempo suficiente pra parecer que o
   app quebrou. */
const NOTICE_DELAY_MS = 2500
const FAILURE_TIMEOUT_MS = 40000

export function ColdStartNotice() {
  const { status, errorKind } = useSession()
  const { t } = usePreferences()
  const [slow, setSlow] = useState(false)
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    if (status !== 'loading') return
    const noticeTimer = window.setTimeout(() => setSlow(true), NOTICE_DELAY_MS)
    const failureTimer = window.setTimeout(() => setTimedOut(true), FAILURE_TIMEOUT_MS)
    return () => {
      window.clearTimeout(noticeTimer)
      window.clearTimeout(failureTimer)
      setSlow(false)
      setTimedOut(false)
    }
  }, [status])

  const failed =
    (status === 'loading' && timedOut) || (status === 'error' && errorKind === 'network')

  if (failed) {
    return (
      <div className="cold-start-notice cold-start-notice--error" role="alert">
        <div>
          <strong>{t('cold_start_error')}</strong>
          <span>{t('cold_start_error_hint')}</span>
        </div>
        <button type="button" onClick={() => window.location.reload()}>
          {t('cold_start_reload')}
        </button>
      </div>
    )
  }

  if (status === 'loading' && slow) {
    return (
      <div className="cold-start-notice" role="status">
        <span className="cold-start-notice__spin" aria-hidden="true" />
        <div>
          <strong>{t('cold_start_title')}</strong>
          <span>{t('cold_start_hint')}</span>
        </div>
      </div>
    )
  }

  return null
}

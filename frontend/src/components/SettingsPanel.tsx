import { useEffect } from 'react'
import { Link } from 'react-router'

import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'
import { AccountAvatar } from './AccountAvatar'
import { Icon } from './Icon'

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const { theme, locale, setTheme, setLocale, t } = usePreferences()
  const { account, status, refresh } = useSession()

  useEffect(() => {
    if (!open) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose, open])

  if (!open) return null

  return (
    <div className="panel-layer" role="presentation">
      <button
        className="panel-backdrop"
        type="button"
        aria-label={t('close')}
        onClick={onClose}
      />
      <aside
        className="settings-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <div className="settings-panel__header">
          <div>
            <p className="eyebrow">{t('app_v2')}</p>
            <h2 id="settings-title">{t('settings')}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose}>
            <Icon name="close" />
            <span className="sr-only">{t('close')}</span>
          </button>
        </div>

        <section className="settings-section" aria-labelledby="appearance-title">
          <h3 id="appearance-title">{t('appearance')}</h3>
          <div className="segmented-control">
            <button
              type="button"
              className={theme === 'dark' ? 'is-active' : ''}
              aria-pressed={theme === 'dark'}
              onClick={() => setTheme('dark')}
            >
              <Icon name="moon" size={18} />
              {t('theme_dark')}
            </button>
            <button
              type="button"
              className={theme === 'light' ? 'is-active' : ''}
              aria-pressed={theme === 'light'}
              onClick={() => setTheme('light')}
            >
              <Icon name="sun" size={18} />
              {t('theme_light')}
            </button>
          </div>
        </section>

        <section className="settings-section" aria-labelledby="language-title">
          <h3 id="language-title">{t('language')}</h3>
          <div className="segmented-control segmented-control--text">
            <button
              type="button"
              className={locale === 'pt-BR' ? 'is-active' : ''}
              aria-pressed={locale === 'pt-BR'}
              onClick={() => setLocale('pt-BR')}
            >
              {t('portuguese')}
            </button>
            <button
              type="button"
              className={locale === 'en' ? 'is-active' : ''}
              aria-pressed={locale === 'en'}
              onClick={() => setLocale('en')}
            >
              {t('english')}
            </button>
            <button
              type="button"
              className={locale === 'es' ? 'is-active' : ''}
              aria-pressed={locale === 'es'}
              onClick={() => setLocale('es')}
            >
              {t('spanish')}
            </button>
          </div>
        </section>

        <section className="settings-section" aria-labelledby="account-title">
          <h3 id="account-title">{t('account')}</h3>

          {status === 'loading' && (
            <div className="account-state account-state--loading">
              <span className="loading-dot" />
              {t('loading_account')}
            </div>
          )}

          {status === 'error' && (
            <div className="account-state account-state--error">
              <p>{t('account_error')}</p>
              <button type="button" className="text-button" onClick={() => void refresh()}>
                <Icon name="refresh" size={17} />
                {t('retry')}
              </button>
            </div>
          )}

          {status === 'ready' && account && (
            <div className="account-card">
              <div className="account-card__identity">
                <AccountAvatar account={account} size="large" />
                <div>
                  <strong>{account.nome || `@${account.handle}`}</strong>
                  <span>@{account.handle}</span>
                  <small>
                    {account.logado ? t('account_google') : t('account_anonymous')}
                  </small>
                </div>
              </div>
              <p>{account.logado ? t('logged_hint') : t('anonymous_hint')}</p>
              <div className="account-card__actions">
                <Link className="button button--secondary" to="/perfil" onClick={onClose}>
                  <Icon name="profile" size={16} />
                  {t('nav_profile')}
                </Link>
                {account.logado ? (
                  <a className="button button--secondary" href="/api/auth/logout">
                    {t('sign_out')}
                  </a>
                ) : (
                  <a className="button button--primary" href="/api/auth/google/login">
                    {t('sign_in')}
                  </a>
                )}
                <a className="button button--ghost" href="/">
                  {t('open_legacy')}
                  <Icon name="external" size={16} />
                </a>
              </div>
            </div>
          )}
        </section>
      </aside>
    </div>
  )
}

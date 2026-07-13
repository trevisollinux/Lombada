import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'
import { AccountAvatar } from './AccountAvatar'
import { Icon, type IconName } from './Icon'
import { SettingsPanel } from './SettingsPanel'

interface NavigationItem {
  to: string
  label: 'nav_search' | 'nav_explore' | 'nav_feed' | 'nav_shelf' | 'nav_diary' | 'nav_memories' | 'nav_profile'
  icon: IconName
  end?: boolean
}

const navigationItems: NavigationItem[] = [
  { to: '/', label: 'nav_search', icon: 'search', end: true },
  { to: '/explorar', label: 'nav_explore', icon: 'explore' },
  { to: '/feed', label: 'nav_feed', icon: 'feed' },
  { to: '/estante', label: 'nav_shelf', icon: 'shelf' },
  { to: '/diario', label: 'nav_diary', icon: 'diary' },
  { to: '/memorias', label: 'nav_memories', icon: 'memory' },
  { to: '/perfil', label: 'nav_profile', icon: 'profile' },
]

const mobileNavigationItems = navigationItems.filter((item) =>
  ['/', '/explorar', '/estante', '/perfil'].includes(item.to),
)

export function AppLayout() {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [quickOpen, setQuickOpen] = useState(false)
  const { t } = usePreferences()
  const { account, status, refresh } = useSession()
  const location = useLocation()

  useEffect(() => {
    setQuickOpen(false)
    setSettingsOpen(false)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [location.pathname])

  useEffect(() => {
    if (!quickOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setQuickOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [quickOpen])

  return (
    <div className="app-frame">
      <header className="app-header">
        <Link className="brand" to="/" aria-label={t('app_v2')}>
          <span className="brand-mark" aria-hidden="true">L</span>
          <span className="wordmark">lombada<span>.</span></span>
        </Link>

        <div className="app-header__meta">
          <span className="migration-chip">{t('migration_badge')}</span>
          <button
            className="account-trigger"
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label={t('settings')}
          >
            <AccountAvatar account={account} size="small" />
            <span className="account-trigger__copy">
              <strong>{status === 'ready' && account ? account.nome || `@${account.handle}` : t('app_v2')}</strong>
              <small>{t('settings')}</small>
            </span>
            <Icon name="settings" size={19} />
          </button>
        </div>
      </header>

      {status === 'error' && (
        <div className="global-notice" role="status">
          <span>{t('account_error')}</span>
          <button type="button" onClick={() => void refresh()}>
            <Icon name="refresh" size={16} />
            {t('retry')}
          </button>
        </div>
      )}

      <div className="desktop-layout">
        <aside className="desktop-rail" aria-label="Navegação principal">
          <nav>
            {navigationItems.map((item) => (
              <NavLink
                key={item.to}
                className={({ isActive }) => `rail-link${isActive ? ' is-active' : ''}`}
                to={item.to}
                end={item.end}
              >
                <Icon name={item.icon} />
                <span>{t(item.label)}</span>
              </NavLink>
            ))}
          </nav>
          <button className="rail-add" type="button" onClick={() => setQuickOpen(true)}>
            <Icon name="plus" />
            <span>{t('quick_action')}</span>
          </button>
        </aside>

        <main className="app-content" id="main-content">
          <Outlet />
        </main>
      </div>

      <nav className="bottom-navigation" aria-label="Navegação principal">
        {mobileNavigationItems.slice(0, 2).map((item) => (
          <NavItem key={item.to} item={item} />
        ))}
        <button
          className={`bottom-navigation__add${quickOpen ? ' is-active' : ''}`}
          type="button"
          aria-expanded={quickOpen}
          aria-label={t('quick_action')}
          onClick={() => setQuickOpen((current) => !current)}
        >
          <Icon name={quickOpen ? 'close' : 'plus'} size={26} />
        </button>
        {mobileNavigationItems.slice(2).map((item) => (
          <NavItem key={item.to} item={item} />
        ))}
      </nav>

      {quickOpen && (
        <div className="quick-layer">
          <button
            className="quick-backdrop"
            type="button"
            aria-label={t('close')}
            onClick={() => setQuickOpen(false)}
          />
          <section className="quick-sheet" aria-labelledby="quick-title">
            <div className="quick-sheet__handle" />
            <p className="eyebrow">{t('quick_action')}</p>
            <h2 id="quick-title">{t('quick_title')}</h2>
            <p>{t('quick_copy')}</p>
            <div className="quick-sheet__actions">
              <Link className="quick-action-card" to="/">
                <Icon name="search" />
                <span>{t('quick_register')}</span>
                <Icon name="arrow" size={18} />
              </Link>
              <Link className="quick-action-card" to="/feed">
                <Icon name="feed" />
                <span>{t('nav_feed')}</span>
                <Icon name="arrow" size={18} />
              </Link>
              <Link className="quick-action-card" to="/diario">
                <Icon name="diary" />
                <span>{t('quick_diary')}</span>
                <Icon name="arrow" size={18} />
              </Link>
              <Link className="quick-action-card" to="/memorias">
                <Icon name="memory" />
                <span>{t('quick_memories')}</span>
                <Icon name="arrow" size={18} />
              </Link>
              <a className="quick-action-card" href="/">
                <Icon name="external" />
                <span>{t('quick_legacy')}</span>
                <Icon name="arrow" size={18} />
              </a>
            </div>
          </section>
        </div>
      )}

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

function NavItem({ item }: { item: NavigationItem }) {
  const { t } = usePreferences()
  return (
    <NavLink
      className={({ isActive }) => `bottom-navigation__item${isActive ? ' is-active' : ''}`}
      to={item.to}
      end={item.end}
    >
      <Icon name={item.icon} size={21} />
      <span>{t(item.label)}</span>
    </NavLink>
  )
}

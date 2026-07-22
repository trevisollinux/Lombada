import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

import { NotificationsCenter } from '../features/notifications/NotificationsCenter'
import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'
import { AccountAvatar } from './AccountAvatar'
import { ColdStartNotice } from './ColdStartNotice'
import { Icon, type IconName } from './Icon'
import { SettingsPanel } from './SettingsPanel'
import { VersionWatcher } from './VersionWatcher'

/* Glifo "L" da lombada, o mesmo do favicon e do selo do app legado. */
function BrandGlyph() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="448 397 183 293" focusable="false">
        <path
          fill="currentColor"
          d="M448 397.7c0 .5 2.7 2 5.9 3.5 10.5 4.9 9.6-9.2 9.9 141L464 673l4.3-.6c3.6-.4 5.5.2 13.2 4l9 4.5-14.8.1c-13.5 0-15.2.2-17.8 2.1-1.6 1.1-4.5 2.5-6.5 3.1-2 .5-3.4 1.4-3.1 2.1.3.9 22.3 1.3 91.5 1.5l91.2.2v-29c0-15.9-.4-29-.8-29s-1.8 3.2-3.1 7c-5.2 16.2-10.7 24.9-20.3 32.3-11.6 8.8-13.5 9.1-57.3 9.5-37.9.3-38 .3-42.4-2-5.3-2.7-7.9-6-9.1-11.4-.6-2.2-1-60.8-1-137.2V397h-24.5c-13.5 0-24.5.3-24.5.7"
        />
        <path
          fill="currentColor"
          d="M511.5 399.2c-.3 1.3-.4 61.6-.3 134.1.3 115.8.5 131.9 1.8 132.7.8.5 3.9 1 6.8 1h5.2V538.1c0-110.2.2-129 1.4-130 .8-.7 3.6-1.1 6.3-.9l4.8.3.5 129.2c.3 71 .7 129.4 1 129.6.6.6 6.3 1.1 10.2.8l2.8-.1.2-129.8c.3-123 .4-129.9 2.1-132.5 1-1.5 3.4-3.5 5.2-4.4 1.9-.9 3.5-2 3.5-2.5 0-.4-11.5-.8-25.5-.8H512z"
        />
      </svg>
    </span>
  )
}

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

/* mesma barra do v1: Estante · Buscar · [+] · Explorar · Perfil
   (feed, diário e memórias seguem acessíveis pelo Explorar e pelo botão +) */
const mobileNavigationItems = ['/estante', '/', '/explorar', '/perfil'].map((path) => (
  navigationItems.find((item) => item.to === path) as NavigationItem
))

export function AppLayout() {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [quickOpen, setQuickOpen] = useState(false)
  const { t } = usePreferences()
  const { account, status, errorKind, refresh } = useSession()
  const location = useLocation()

  useEffect(() => {
    setQuickOpen(false)
    setSettingsOpen(false)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [location.pathname])

  // páginas (ex.: engrenagem do Perfil) podem pedir o painel de ajustes
  useEffect(() => {
    const open = () => setSettingsOpen(true)
    window.addEventListener('lombada:open-settings', open)
    return () => window.removeEventListener('lombada:open-settings', open)
  }, [])

  useEffect(() => {
    if (!quickOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setQuickOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [quickOpen])

  const accountName =
    status === 'ready' && account ? account.nome || `@${account.handle}` : t('app_v2')

  return (
    <div className="app-frame">
      <ColdStartNotice />
      <header className="app-header">
        {/* topo do v1: marca à esquerda, sino de atividade à direita —
            ajustes ficam na engrenagem do Perfil */}
        <Link className="brand" to="/" aria-label={t('app_v2')}>
          <BrandGlyph />
          <span className="wordmark">ombada<i>.</i></span>
        </Link>
        <NotificationsCenter />
      </header>

      {status === 'error' && errorKind !== 'network' && (
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
          <div className="rail-head">
            <Link className="brand" to="/" aria-label={t('app_v2')}>
              <span className="rail-brand__text">
                <span className="brand-lockup">
                  <BrandGlyph />
                  <span className="wordmark">ombada<i>.</i></span>
                </span>
                <small className="rail-tagline">diário de leituras</small>
              </span>
            </Link>
          </div>

          <nav className="rail-nav">
            <p className="rail-label">{t('nav_menu')}</p>
            {navigationItems.map((item) => (
              <NavLink
                key={item.to}
                className={({ isActive }) => `rail-link${isActive ? ' is-active' : ''}`}
                to={item.to}
                end={item.end}
              >
                <Icon name={item.icon} size={19} />
                <span>{t(item.label)}</span>
              </NavLink>
            ))}
          </nav>

          <button className="rail-add" type="button" onClick={() => setQuickOpen(true)}>
            <Icon name="plus" size={19} />
            <span>{t('quick_action')}</span>
          </button>

          <div className="rail-foot">
            <button
              className="account-trigger"
              type="button"
              onClick={() => setSettingsOpen(true)}
              aria-label={t('settings')}
            >
              <AccountAvatar account={account} size="small" />
              <span className="account-trigger__copy">
                <strong>{accountName}</strong>
                <small>{t('settings')}</small>
              </span>
              <Icon name="settings" size={17} />
            </button>
            <span className="migration-chip">{t('migration_badge')}</span>
          </div>
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
      <VersionWatcher />
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

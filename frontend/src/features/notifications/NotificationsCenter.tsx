import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'

import { Icon } from '../../components/Icon'
import { usePreferences } from '../../providers/PreferencesProvider'
import { useSession } from '../../providers/SessionProvider'
import { ApiError, getNotifications, getUnreadNotifications } from '../../services/api'
import type { AppNotification } from '../../types/notifications'
import { FeedAvatar } from '../feed/FeedAvatar'
import { notificationLabel, relativeTime } from './notificationsData'
import { notificationsText } from './notificationsI18n'

type ListState =
  | { status: 'loading' }
  | { status: 'ready'; items: AppNotification[] }
  | { status: 'login' }
  | { status: 'error' }

export function NotificationsCenter() {
  const { locale, t } = usePreferences()
  const { status: sessionStatus } = useSession()
  const navigate = useNavigate()

  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const [list, setList] = useState<ListState>({ status: 'loading' })
  const triggerRef = useRef<HTMLButtonElement | null>(null)

  const refreshUnread = useCallback((signal?: AbortSignal) => {
    getUnreadNotifications(signal)
      .then((data) => setUnread(data.count))
      .catch(() => {
        /* anônimo devolve 0; falha de rede não deve acender a bolinha */
      })
  }, [])

  // conta não-lidas quando a sessão fica pronta (o backend só conta pra
  // usuário Google; anônimo sempre devolve 0)
  useEffect(() => {
    if (sessionStatus !== 'ready') return
    const controller = new AbortController()
    refreshUnread(controller.signal)
    return () => controller.abort()
  }, [sessionStatus, refreshUnread])

  const loadList = useCallback(() => {
    setList({ status: 'loading' })
    getNotifications()
      .then((items) => setList({ status: 'ready', items }))
      .catch((cause) => {
        if (cause instanceof ApiError && cause.status === 401) {
          setList({ status: 'login' })
          return
        }
        setList({ status: 'error' })
      })
  }, [])

  // abrir a central busca a lista; o GET marca tudo como lido no servidor,
  // então a bolinha zera na hora
  useEffect(() => {
    if (!open) return
    loadList()
    setUnread(0)

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open, loadList])

  const close = useCallback(() => {
    setOpen(false)
    triggerRef.current?.focus()
  }, [])

  const openActor = useCallback(
    (handle: string) => {
      if (!handle) return
      setOpen(false)
      navigate(`/perfil/${encodeURIComponent(handle)}`)
    },
    [navigate],
  )

  return (
    <>
      <button
        ref={triggerRef}
        className="notif-bell"
        type="button"
        onClick={() => setOpen(true)}
        aria-label={notificationsText(locale, 'open')}
      >
        <Icon name="bell" size={21} />
        {unread > 0 && (
          <span className="notif-bell__dot" aria-hidden="true" />
        )}
        {unread > 0 && <span className="sr-only">{unread}</span>}
      </button>

      {open && (
        <div className="panel-layer" role="presentation">
          <button
            className="panel-backdrop"
            type="button"
            aria-label={notificationsText(locale, 'close')}
            onClick={close}
          />
          <aside
            className="notif-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="notif-title"
          >
            <div className="notif-panel__header">
              <div>
                <p className="eyebrow">{t('app_v2')}</p>
                <h2 id="notif-title">{notificationsText(locale, 'title')}</h2>
              </div>
              <button className="icon-button" type="button" onClick={close}>
                <Icon name="close" />
                <span className="sr-only">{notificationsText(locale, 'close')}</span>
              </button>
            </div>

            <div className="notif-panel__body">
              {list.status === 'loading' && (
                <div className="notif-state">
                  <span className="loading-dot" />
                  {notificationsText(locale, 'loading')}
                </div>
              )}

              {list.status === 'login' && (
                <div className="notif-state notif-state--empty">
                  <span className="notif-state__glyph" aria-hidden="true">🔔</span>
                  <p>{notificationsText(locale, 'login_required')}</p>
                  <a className="button button--primary" href="/api/auth/google/login">
                    {t('sign_in')}
                  </a>
                </div>
              )}

              {list.status === 'error' && (
                <div className="notif-state notif-state--error">
                  <p>{notificationsText(locale, 'error')}</p>
                  <button type="button" className="text-button" onClick={loadList}>
                    <Icon name="refresh" size={17} />
                    {notificationsText(locale, 'retry')}
                  </button>
                </div>
              )}

              {list.status === 'ready' && list.items.length === 0 && (
                <div className="notif-state notif-state--empty">
                  <span className="notif-state__glyph" aria-hidden="true">🔔</span>
                  <p>{notificationsText(locale, 'empty')}</p>
                </div>
              )}

              {list.status === 'ready' && list.items.length > 0 && (
                <ul className="notif-list">
                  {list.items.map((notification) => (
                    <li
                      key={notification.id}
                      className={`notif-item${notification.lida ? '' : ' is-unread'}`}
                    >
                      <button
                        type="button"
                        className="notif-item__main"
                        onClick={() => openActor(notification.ator.handle)}
                      >
                        <FeedAvatar
                          name={notification.ator.nome}
                          handle={notification.ator.handle}
                          url={notification.ator.avatar_url}
                          size="small"
                        />
                        <span className="notif-item__copy">
                          <span className="notif-item__text">
                            {notificationLabel(notification, locale)}
                            {notification.ator.is_demo && (
                              <span className="notif-item__demo">
                                {notificationsText(locale, 'demo_badge')}
                              </span>
                            )}
                          </span>
                          <small>{relativeTime(notification.criado_em, locale)}</small>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </aside>
        </div>
      )}
    </>
  )
}

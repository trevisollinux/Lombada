import { useEffect, useRef, useState } from 'react'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { ReaderSuggestions, ReadingNowRail } from '../features/feed/FeedDiscoveryPanels'
import { FeedItemCard } from '../features/feed/FeedItemCard'
import { feedText } from '../features/feed/feedI18n'
import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'
import {
  getDiscoverFeed,
  getFollowingFeed,
  getReadingNow,
} from '../services/api'
import type { FeedItem, FeedUser, ReadingNowItem } from '../types/feed'

type FeedTab = 'following' | 'discover'

export function FeedPage() {
  const { locale, t } = usePreferences()
  const { account, status: sessionStatus, refresh } = useSession()
  const initialTabChosen = useRef(false)
  const [tab, setTab] = useState<FeedTab>('following')
  const [items, setItems] = useState<FeedItem[]>([])
  const [readers, setReaders] = useState<FeedUser[]>([])
  const [readingNow, setReadingNow] = useState<ReadingNowItem[]>([])
  const [followingCount, setFollowingCount] = useState(0)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [retryVersion, setRetryVersion] = useState(0)

  useEffect(() => {
    if (sessionStatus !== 'ready' || !account || initialTabChosen.current) return
    initialTabChosen.current = true
    setFollowingCount(account.following_count)
    if (account.following_count === 0) setTab('discover')
  }, [account, sessionStatus])

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    setError(null)

    async function load() {
      try {
        if (tab === 'following') {
          const [feedResult, nowResult] = await Promise.allSettled([
            getFollowingFeed(30, controller.signal),
            getReadingNow(tab, 12, controller.signal),
          ] as const)
          if (controller.signal.aborted) return
          if (feedResult.status === 'rejected') throw feedResult.reason
          setItems(feedResult.value.items)
          setReaders([])
          setFollowingCount(feedResult.value.following_count)
          setReadingNow(nowResult.status === 'fulfilled' ? nowResult.value.items : [])
        } else {
          const [feedResult, nowResult] = await Promise.allSettled([
            getDiscoverFeed(30, controller.signal),
            getReadingNow(tab, 12, controller.signal),
          ] as const)
          if (controller.signal.aborted) return
          if (feedResult.status === 'rejected') throw feedResult.reason
          setItems(feedResult.value.reviews)
          setReaders(feedResult.value.readers)
          setReadingNow(nowResult.status === 'fulfilled' ? nowResult.value.items : [])
        }
        setStatus('ready')
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : feedText(locale, 'error'))
        setStatus('error')
      }
    }

    void load()
    return () => controller.abort()
  }, [locale, retryVersion, tab])

  function handleFollowChange(handle: string, following: boolean) {
    setItems((current) => current.map((item) => (
      item.usuario.handle === handle
        ? { ...item, usuario: { ...item.usuario, is_following: following } }
        : item
    )))
    setReaders((current) => current.map((reader) => (
      reader.handle === handle ? { ...reader, is_following: following } : reader
    )))
    setFollowingCount((current) => Math.max(0, current + (following ? 1 : -1)))
    void refresh()
  }

  const loggedIn = Boolean(account?.logado)
  const emptyTitle = tab === 'following'
    ? feedText(locale, 'empty_following')
    : feedText(locale, 'empty_discover')
  const emptyCopy = tab === 'following'
    ? feedText(locale, 'empty_following_copy')
    : feedText(locale, 'empty_discover_copy')

  return (
    <section className="page page--feed">
      <PageHeader
        eyebrow={t('feed_eyebrow')}
        title={t('feed_title')}
        description={t('feed_copy')}
        aside={<span className="stage-stamp">08 · social</span>}
      />

      <div className="feed-toolbar">
        <div className="feed-tabs" role="tablist" aria-label={t('feed_title')}>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'following'}
            className={tab === 'following' ? 'is-active' : ''}
            onClick={() => setTab('following')}
          >
            {feedText(locale, 'following')}
            <span>{followingCount}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'discover'}
            className={tab === 'discover' ? 'is-active' : ''}
            onClick={() => setTab('discover')}
          >
            {feedText(locale, 'discover')}
          </button>
        </div>
        <button
          className="icon-button feed-refresh"
          type="button"
          onClick={() => setRetryVersion((current) => current + 1)}
          aria-label={feedText(locale, 'refresh')}
          title={feedText(locale, 'refresh')}
        >
          <Icon name="refresh" size={18} />
        </button>
      </div>

      {!loggedIn && sessionStatus === 'ready' && (
        <aside className="feed-login-notice">
          <Icon name="people" size={22} />
          <p>{feedText(locale, 'login_required')}</p>
          <a className="button button--primary" href="/api/auth/google/login">
            {feedText(locale, 'sign_in')}
          </a>
        </aside>
      )}

      {status === 'loading' && <FeedLoading label={feedText(locale, 'loading')} />}

      {status === 'error' && (
        <section className="catalog-state" role="alert">
          <Icon name="refresh" size={30} />
          <h2>{feedText(locale, 'error')}</h2>
          <p>{error}</p>
          <button className="button button--secondary" type="button" onClick={() => setRetryVersion((current) => current + 1)}>
            <Icon name="refresh" size={17} />
            {feedText(locale, 'refresh')}
          </button>
        </section>
      )}

      {status === 'ready' && (
        <>
          <ReadingNowRail items={readingNow} locale={locale} />
          {tab === 'discover' && (
            <ReaderSuggestions
              readers={readers}
              locale={locale}
              loggedIn={loggedIn}
              onFollowChange={handleFollowChange}
            />
          )}

          {items.length === 0 ? (
            <section className="catalog-state feed-empty">
              <Icon name={tab === 'following' ? 'feed' : 'people'} size={32} />
              <h2>{emptyTitle}</h2>
              <p>{emptyCopy}</p>
              {tab === 'following' && (
                <button className="button button--primary" type="button" onClick={() => setTab('discover')}>
                  {feedText(locale, 'discover')}
                  <Icon name="arrow" size={16} />
                </button>
              )}
            </section>
          ) : (
            <div className="feed-stream">
              {items.map((item, index) => {
                const id = item.tipo === 'wrote_text'
                  ? `text-${item.texto.texto_id}`
                  : `reading-${item.leitura.leitura_id}`
                return (
                  <FeedItemCard
                    key={`${id}-${index}`}
                    item={item}
                    locale={locale}
                    loggedIn={loggedIn}
                    onFollowChange={handleFollowChange}
                  />
                )
              })}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function FeedLoading({ label }: { label: string }) {
  return (
    <div className="feed-loading" aria-busy="true" aria-label={label}>
      {Array.from({ length: 4 }, (_, index) => (
        <article key={index}>
          <span className="feed-loading__avatar" />
          <div><i /><i /><i /></div>
          <span className="feed-loading__cover" />
        </article>
      ))}
    </div>
  )
}

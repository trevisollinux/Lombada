import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { FeedAvatar } from '../features/feed/FeedAvatar'
import { FollowButton } from '../features/feed/FollowButton'
import { ProfileIdentityEditor } from '../features/profile/ProfileIdentityEditor'
import { ProfileHighlights, ProfileReviews, ProfileShelf } from '../features/profile/ProfileLibrary'
import { ProfilePeoplePanel } from '../features/profile/ProfilePeoplePanel'
import { ProfileTexts } from '../features/profile/ProfileTexts'
import { profileText } from '../features/profile/profileI18n'
import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'
import { getMyProfileTexts, getPublicProfile } from '../services/api'
import type { ProfileText, PublicProfileResponse } from '../types/profile'

type ProfileTab = 'shelf' | 'reviews' | 'texts'
type PeopleDirection = 'followers' | 'following'

export function ProfilePage() {
  const { handle: routeHandle } = useParams<{ handle?: string }>()
  const { locale, t } = usePreferences()
  const { account, status: sessionStatus, refresh } = useSession()
  const [profile, setProfile] = useState<PublicProfileResponse | null>(null)
  const [myTexts, setMyTexts] = useState<ProfileText[]>([])
  const [tab, setTab] = useState<ProfileTab>('shelf')
  const [peopleDirection, setPeopleDirection] = useState<PeopleDirection | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [reloadVersion, setReloadVersion] = useState(0)

  const targetHandle = routeHandle || account?.handle || ''
  const owner = Boolean(profile?.is_me || (!routeHandle && account && profile?.handle === account.handle))

  useEffect(() => {
    if (sessionStatus !== 'ready' || !account || !targetHandle) return
    const currentAccount = account
    const controller = new AbortController()
    setStatus('loading')
    setError(null)

    async function load() {
      try {
        const isOwnTarget = !routeHandle || routeHandle === currentAccount.handle
        const [nextProfile, nextTexts] = await Promise.all([
          getPublicProfile(targetHandle, controller.signal),
          isOwnTarget ? getMyProfileTexts(controller.signal) : Promise.resolve<ProfileText[]>([]),
        ])
        if (controller.signal.aborted) return
        setProfile(nextProfile)
        setMyTexts(nextTexts)
        setStatus('ready')
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setProfile(null)
        setError(cause instanceof Error ? cause.message : profileText(locale, 'profile_error'))
        setStatus('error')
      }
    }

    void load()
    return () => controller.abort()
  }, [account, locale, reloadVersion, routeHandle, sessionStatus, targetHandle])

  const reloadProfile = useCallback(async (handleOverride?: string) => {
    await refresh()
    const handle = handleOverride || targetHandle
    if (handle) {
      const [nextProfile, nextTexts] = await Promise.all([
        getPublicProfile(handle),
        getMyProfileTexts(),
      ])
      setProfile(nextProfile)
      setMyTexts(nextTexts)
    }
  }, [refresh, targetHandle])

  function handleFollowChange(handle: string, following: boolean) {
    setProfile((current) => {
      if (!current) return current
      if (handle === current.handle) {
        return {
          ...current,
          is_following: following,
          followers_count: Math.max(0, current.followers_count + (following ? 1 : -1)),
        }
      }
      if (current.is_me) {
        return {
          ...current,
          following_count: Math.max(0, current.following_count + (following ? 1 : -1)),
        }
      }
      return current
    })
    void refresh()
  }

  const loggedIn = Boolean(account?.logado)
  const profileTexts = owner ? myTexts : profile?.textos || []

  return (
    <section className="page page--profile">
      <PageHeader
        title={owner ? t('profile_title') : profile?.nome || profileText(locale, 'public_profile')}
        description={owner ? t('profile_copy') : profile?.bio || `@${targetHandle}`}
        aside={
          owner ? (
            /* engrenagem no topo do perfil, como no v1 */
            <button
              className="icon-button"
              type="button"
              aria-label={t('settings')}
              onClick={() => window.dispatchEvent(new Event('lombada:open-settings'))}
            >
              <Icon name="settings" size={19} />
            </button>
          ) : undefined
        }
      />

      {status === 'loading' && <ProfileLoading />}

      {status === 'error' && (
        <section className="catalog-state" role="alert">
          <Icon name="profile" size={34} />
          <h2>{profileText(locale, 'profile_not_found')}</h2>
          <p>{error}</p>
          <button className="button button--secondary" type="button" onClick={() => setReloadVersion((current) => current + 1)}>
            <Icon name="refresh" size={17} />
            {profileText(locale, 'retry')}
          </button>
        </section>
      )}

      {status === 'ready' && profile && account && (
        <>
          <article className="profile-hero">
            <div className="profile-hero__identity">
              <FeedAvatar name={profile.nome} handle={profile.handle} url={profile.avatar_url} size="large" />
              <div>
                <p className="eyebrow">
                  {owner
                    ? account.logado ? profileText(locale, 'account_google') : profileText(locale, 'account_anonymous')
                    : profileText(locale, 'public_profile')}
                </p>
                <h2>{profile.nome || `@${profile.handle}`}</h2>
                <p className="profile-hero__handle">@{profile.handle}</p>
                {profile.bio && <p className="profile-hero__bio">{profile.bio}</p>}
              </div>
            </div>
            <div className="profile-hero__actions">
              {owner ? (
                <>
                  <a className="button button--ghost" href={`/u/${encodeURIComponent(profile.handle)}`} target="_blank" rel="noreferrer">
                    {profileText(locale, 'legacy_profile')} <Icon name="external" size={15} />
                  </a>
                  {account.logado && <a className="text-button" href="/api/auth/logout">{t('sign_out')}</a>}
                </>
              ) : (
                <FollowButton
                  handle={profile.handle}
                  following={profile.is_following}
                  isMe={profile.is_me}
                  isDemo={profile.is_demo}
                  loggedIn={loggedIn}
                  locale={locale}
                  onChange={handleFollowChange}
                />
              )}
            </div>
          </article>

          {owner && (
            <ProfileIdentityEditor account={account} locale={locale} onChanged={reloadProfile} />
          )}

          <div className="profile-metric-grid">
            <button type="button" onClick={() => setPeopleDirection('followers')}>
              <strong>{profile.followers_count}</strong>
              <span>{profileText(locale, 'followers')}</span>
            </button>
            <button type="button" onClick={() => setPeopleDirection('following')}>
              <strong>{profile.following_count}</strong>
              <span>{profileText(locale, 'following')}</span>
            </button>
            <article>
              <strong>{profile.stats.total}</strong>
              <span>{profileText(locale, 'books')}</span>
            </article>
            <article>
              <strong>{profile.stats.lidos}</strong>
              <span>{profileText(locale, 'read')}</span>
            </article>
            <article>
              <strong>{profile.stats.lendo}</strong>
              <span>{profileText(locale, 'reading')}</span>
            </article>
            <article>
              <strong>{profile.stats.media_nota ?? '—'}</strong>
              <span>{profileText(locale, 'average_rating')}</span>
            </article>
          </div>

          <div className="profile-edition-metrics">
            <span><strong>{profile.edicoes_possui}</strong>{profileText(locale, 'owned_editions')}</span>
            <span><strong>{profile.edicoes_desejadas}</strong>{profileText(locale, 'wanted_editions')}</span>
          </div>

          <ProfileHighlights
            readingNow={profile.lendo_agora}
            favorites={profile.favoritos}
            locale={locale}
          />

          <nav className="profile-tabs" aria-label={profileText(locale, 'public_profile')}>
            <button type="button" className={tab === 'shelf' ? 'is-active' : ''} onClick={() => setTab('shelf')}>
              {profileText(locale, 'shelf')} <span>{profile.leituras.length}</span>
            </button>
            <button type="button" className={tab === 'reviews' ? 'is-active' : ''} onClick={() => setTab('reviews')}>
              {profileText(locale, 'reviews')} <span>{profile.criticas_publicas.length}</span>
            </button>
            <button type="button" className={tab === 'texts' ? 'is-active' : ''} onClick={() => setTab('texts')}>
              {profileText(locale, 'texts')} <span>{profileTexts.length}</span>
            </button>
          </nav>

          {tab === 'shelf' && <ProfileShelf readings={profile.leituras} locale={locale} />}
          {tab === 'reviews' && <ProfileReviews readings={profile.criticas_publicas} locale={locale} />}
          {tab === 'texts' && (
            <ProfileTexts
              texts={profileTexts}
              readings={profile.leituras}
              owner={owner}
              loggedIn={loggedIn}
              locale={locale}
              onItemsChange={owner ? setMyTexts : undefined}
            />
          )}

          {!owner && account.handle && (
            <p className="profile-back-link">
              <Link to="/perfil"><Icon name="arrow" size={14} /> {profileText(locale, 'my_profile')}</Link>
            </p>
          )}

          <ProfilePeoplePanel
            open={peopleDirection !== null}
            direction={peopleDirection || 'followers'}
            handle={profile.handle}
            locale={locale}
            loggedIn={loggedIn}
            onClose={() => setPeopleDirection(null)}
            onFollowChange={handleFollowChange}
          />
        </>
      )}
    </section>
  )
}

function ProfileLoading() {
  return (
    <div className="profile-loading" aria-busy="true">
      <div className="profile-loading__hero">
        <span />
        <div><i /><i /><i /></div>
      </div>
      <div className="profile-loading__metrics">
        {Array.from({ length: 6 }, (_, index) => <i key={index} />)}
      </div>
      <div className="profile-loading__books">
        {Array.from({ length: 5 }, (_, index) => <i key={index} />)}
      </div>
    </div>
  )
}

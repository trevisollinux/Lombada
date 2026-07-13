import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { Icon } from '../../components/Icon'
import { FeedAvatar } from '../feed/FeedAvatar'
import { FollowButton } from '../feed/FollowButton'
import type { Locale } from '../../i18n'
import { getProfileFollowers, getProfileFollowing } from '../../services/api'
import type { ProfilePerson } from '../../types/profile'
import { profileText } from './profileI18n'

type PeopleDirection = 'followers' | 'following'

interface ProfilePeoplePanelProps {
  open: boolean
  direction: PeopleDirection
  handle: string
  locale: Locale
  loggedIn: boolean
  onClose: () => void
  onFollowChange: (handle: string, following: boolean) => void
}

export function ProfilePeoplePanel({
  open,
  direction,
  handle,
  locale,
  loggedIn,
  onClose,
  onFollowChange,
}: ProfilePeoplePanelProps) {
  const [people, setPeople] = useState<ProfilePerson[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    setStatus('loading')
    setError(null)
    const request = direction === 'followers' ? getProfileFollowers : getProfileFollowing
    void request(handle, controller.signal)
      .then((payload) => {
        setPeople(payload)
        setStatus('ready')
      })
      .catch((cause) => {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(cause instanceof Error ? cause.message : profileText(locale, 'profile_error'))
        setStatus('error')
      })
    return () => controller.abort()
  }, [direction, handle, locale, open])

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

  function handleFollow(personHandle: string, following: boolean) {
    setPeople((current) => current.map((person) => (
      person.handle === personHandle ? { ...person, is_following: following } : person
    )))
    onFollowChange(personHandle, following)
  }

  if (!open) return null

  const title = direction === 'followers'
    ? profileText(locale, 'followers')
    : profileText(locale, 'following')

  return (
    <div className="profile-people-layer" role="presentation">
      <button className="profile-people-backdrop" type="button" aria-label={profileText(locale, 'close')} onClick={onClose} />
      <aside className="profile-people-panel" role="dialog" aria-modal="true" aria-labelledby="profile-people-title">
        <header>
          <div>
            <p className="eyebrow">@{handle}</p>
            <h2 id="profile-people-title">{title}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label={profileText(locale, 'close')}>
            <Icon name="close" />
          </button>
        </header>

        {status === 'loading' && <p className="profile-people-state">{profileText(locale, 'people_loading')}</p>}
        {status === 'error' && <p className="profile-people-state" role="alert">{error}</p>}
        {status === 'ready' && people.length === 0 && <p className="profile-people-state">{profileText(locale, 'people_empty')}</p>}

        {status === 'ready' && people.length > 0 && (
          <div className="profile-people-list">
            {people.map((person) => (
              <article key={person.handle}>
                <Link className="profile-people-identity" to={`/perfil/${encodeURIComponent(person.handle)}`} onClick={onClose}>
                  <FeedAvatar name={person.nome} handle={person.handle} url={person.avatar_url} />
                  <span>
                    <strong>{person.nome || `@${person.handle}`}</strong>
                    <small>@{person.handle}</small>
                    {person.bio && <p>{person.bio}</p>}
                  </span>
                </Link>
                <FollowButton
                  handle={person.handle}
                  following={person.is_following}
                  isMe={person.is_me}
                  isDemo={person.is_demo}
                  loggedIn={loggedIn}
                  locale={locale}
                  compact
                  onChange={handleFollow}
                />
              </article>
            ))}
          </div>
        )}
      </aside>
    </div>
  )
}

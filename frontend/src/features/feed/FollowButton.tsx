import { useState } from 'react'

import type { Locale } from '../../i18n'
import { followReader, unfollowReader } from '../../services/api'
import { feedText } from './feedI18n'

interface FollowButtonProps {
  handle: string
  following: boolean
  isMe?: boolean
  isDemo?: boolean
  loggedIn: boolean
  locale: Locale
  compact?: boolean
  onChange?: (handle: string, following: boolean) => void
}

export function FollowButton({
  handle,
  following,
  isMe = false,
  isDemo = false,
  loggedIn,
  locale,
  compact = false,
  onChange,
}: FollowButtonProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (isMe || isDemo) return null

  async function toggle() {
    if (busy) return
    if (!loggedIn) {
      setError(feedText(locale, 'login_required'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = following ? await unfollowReader(handle) : await followReader(handle)
      onChange?.(handle, result.following)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : feedText(locale, 'error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <span className="follow-action">
      <button
        className={`follow-button${following ? ' is-following' : ''}${compact ? ' is-compact' : ''}`}
        type="button"
        onClick={() => void toggle()}
        disabled={busy}
        aria-pressed={following}
        title={following ? feedText(locale, 'unfollow') : feedText(locale, 'follow')}
      >
        {busy ? '…' : following ? feedText(locale, 'following_action') : feedText(locale, 'follow')}
      </button>
      {error && (
        <span className="follow-action__error" role="status">
          {error}{' '}
          {!loggedIn && <a href="/api/auth/google/login">{feedText(locale, 'sign_in')}</a>}
        </span>
      )}
    </span>
  )
}

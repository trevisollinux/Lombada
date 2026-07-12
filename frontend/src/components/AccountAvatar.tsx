import { useState } from 'react'

import type { Account } from '../types/account'

interface AccountAvatarProps {
  account: Account | null
  size?: 'small' | 'medium' | 'large'
}

function initials(account: Account | null): string {
  const source = account?.nome?.trim() || account?.handle?.trim() || 'L'
  return source
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('') || 'L'
}

export function AccountAvatar({ account, size = 'medium' }: AccountAvatarProps) {
  const [failed, setFailed] = useState(false)
  const avatarUrl = account?.avatar_url?.trim()

  if (avatarUrl && !failed) {
    return (
      <img
        className={`account-avatar account-avatar--${size}`}
        src={avatarUrl}
        alt=""
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
      />
    )
  }

  return (
    <span
      className={`account-avatar account-avatar--${size} account-avatar--fallback`}
      aria-hidden="true"
    >
      {initials(account)}
    </span>
  )
}

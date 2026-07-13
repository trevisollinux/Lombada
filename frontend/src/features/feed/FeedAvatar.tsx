interface FeedAvatarProps {
  name: string
  handle: string
  url?: string
  size?: 'small' | 'medium' | 'large'
}

function initials(name: string, handle: string): string {
  const source = name.trim() || handle.trim() || 'L'
  const parts = source.split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts.at(-1)?.[0] || ''}`.toUpperCase()
}

export function FeedAvatar({ name, handle, url = '', size = 'medium' }: FeedAvatarProps) {
  const label = name || `@${handle}`
  return (
    <span className={`feed-avatar feed-avatar--${size}`} aria-label={label}>
      {url ? <img src={url} alt="" loading="lazy" /> : <span aria-hidden="true">{initials(name, handle)}</span>}
    </span>
  )
}

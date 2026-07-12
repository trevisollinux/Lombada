import { useMemo, useState } from 'react'

interface BookCoverProps {
  title: string
  author: string
  url?: string
  className?: string
}

const palettes = [
  ['#68272b', '#d7aa61'],
  ['#243c48', '#d8c49a'],
  ['#52402e', '#d7b56f'],
  ['#353251', '#d0b8de'],
  ['#315041', '#d9c58c'],
] as const

function hash(value: string): number {
  return Array.from(value).reduce((total, character) => {
    return (total * 31 + character.charCodeAt(0)) >>> 0
  }, 7)
}

export function BookCover({ title, author, url, className = '' }: BookCoverProps) {
  const [failed, setFailed] = useState(false)
  const palette = useMemo(() => palettes[hash(`${title}|${author}`) % palettes.length], [author, title])
  const safeUrl = url?.trim()

  if (safeUrl && !failed) {
    return (
      <span className={`book-cover ${className}`.trim()}>
        <img
          src={safeUrl}
          alt={`Capa de ${title}`}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      </span>
    )
  }

  return (
    <span
      className={`book-cover book-cover--generated ${className}`.trim()}
      style={{
        '--cover-primary': palette[0],
        '--cover-accent': palette[1],
      } as React.CSSProperties}
      role="img"
      aria-label={`Capa gerada para ${title}`}
    >
      <span className="book-cover__rule" />
      <strong>{title}</strong>
      <small>{author || 'Lombada'}</small>
      <span className="book-cover__brand">lombada.</span>
    </span>
  )
}

import { useMemo, useState, type CSSProperties } from 'react'

interface BookCoverProps {
  title: string
  author: string
  url?: string
  className?: string
}

/* Arte de capa idêntica à do app legado (capaArteDados): mesmo hash FNV-1a
   sem acentos, mesmas tintas sobre papel creme e mesmos cinco layouts, para
   o mesmo livro ganhar a mesma capa no v1 e aqui. */
const COVER_INKS = ['#8B0E20', '#11100E', '#1E2F3F', '#1F3A2E', '#9A4A2F', '#DCCEB6'] as const
const COVER_PAPER = '#F1E6D2'
const COVER_LAYOUTS = ['classic', 'modern', 'minimal', 'bold', 'stripe'] as const

function bookHash(title: string, author: string): number {
  const text = `${title || ''}|${author || ''}`
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
  let hash = 2166136261
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

export function BookCover({ title, author, url, className = '' }: BookCoverProps) {
  const [failed, setFailed] = useState(false)
  const art = useMemo(() => {
    const hash = bookHash(title, author)
    return {
      layout: COVER_LAYOUTS[hash % COVER_LAYOUTS.length],
      ink: COVER_INKS[hash % COVER_INKS.length],
      ink2: COVER_INKS[Math.floor(hash / 7) % COVER_INKS.length],
    }
  }, [author, title])
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
      data-layout={art.layout}
      data-initial={(title || '?').charAt(0).toUpperCase()}
      style={{
        '--cover-ink': art.ink,
        '--cover-ink-2': art.ink2,
        '--cover-paper': COVER_PAPER,
      } as CSSProperties}
      role="img"
      aria-label={`Capa gerada para ${title}`}
    >
      <span className="book-cover__rule" />
      <span className="book-cover__copy">
        <strong>{title}</strong>
        {author && <small>{author}</small>}
      </span>
      <span className="book-cover__brand">Lombada</span>
    </span>
  )
}

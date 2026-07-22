import { useEffect, useState } from 'react'

import type { Locale } from '../../i18n'
import { getAppConfig } from '../../services/api'

interface AmazonBuyLinkProps {
  isbn?: string
  fallback?: string
  locale: Locale
  className?: string
}

/* A tag de afiliado é a mesma pro app todo, então busca /api/config uma vez
   e compartilha a promessa entre todas as instâncias do link. */
let tagPromise: Promise<string> | null = null

function loadAmazonTag(): Promise<string> {
  if (!tagPromise) {
    tagPromise = getAppConfig()
      .then((config) => config.amazon_tag || '')
      .catch(() => '')
  }
  return tagPromise
}

/* Link de compra na Amazon com a tag de afiliado. Usa o ISBN (mais robusto)
   e cai pra título+autor quando falta. Não renderiza sem tag ou sem termo. */
export function AmazonBuyLink({ isbn, fallback, locale, className = '' }: AmazonBuyLinkProps) {
  const [tag, setTag] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void loadAmazonTag().then((value) => {
      if (active) setTag(value)
    })
    return () => {
      active = false
    }
  }, [])

  if (!tag) return null

  const code = (isbn || '').replace(/[^0-9Xx]/g, '')
  const term = code || (fallback || '').trim()
  if (!term) return null

  const url = `https://www.amazon.com.br/s?k=${encodeURIComponent(term)}&tag=${encodeURIComponent(tag)}`
  const label = locale === 'en' ? 'Buy on Amazon' : 'Comprar na Amazon'

  return (
    <a
      className={`buy-amazon ${className}`.trim()}
      href={url}
      target="_blank"
      rel="noopener nofollow sponsored"
      onClick={(event) => event.stopPropagation()}
    >
      {label}
    </a>
  )
}

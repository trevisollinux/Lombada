import { Link } from 'react-router'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import type { CatalogWork } from '../../types/catalog'
import { catalogText } from './catalogI18n'

interface SearchResultCardProps {
  work: CatalogWork
  locale: Locale
}

export function SearchResultCard({ work, locale }: SearchResultCardProps) {
  const params = new URLSearchParams({
    work_key: work.work_key,
    titulo: work.titulo,
    autor: work.autor,
  })
  const social = [
    work.leituras_count ? `${work.leituras_count} ${catalogText(locale, 'readings')}` : '',
    work.nota_media !== null && work.nota_media !== undefined
      ? `${catalogText(locale, 'average')} ${work.nota_media.toFixed(1)}`
      : '',
    work.lendo_agora_count ? `${work.lendo_agora_count} ${catalogText(locale, 'reading_now')}` : '',
  ].filter(Boolean)

  return (
    <article className="catalog-result">
      <Link
        className="catalog-result__cover-link"
        to={`/obra?${params.toString()}`}
        state={{ work }}
        aria-label={`${catalogText(locale, 'open_work')}: ${work.titulo}`}
      >
        <BookCover
          title={work.titulo}
          author={work.autor}
          url={work.capa_url}
          className="catalog-result__cover"
        />
      </Link>

      <div className="catalog-result__body">
        <div>
          <p className="eyebrow">
            {[work.ano, work.editora].filter(Boolean).join(' · ') || catalogText(locale, 'edition')}
          </p>
          <h2>{work.titulo}</h2>
          <p className="catalog-result__author">{work.autor || '—'}</p>
        </div>

        {social.length > 0 && (
          <div className="catalog-result__social">
            {social.map((item) => <span key={item}>{item}</span>)}
          </div>
        )}

        <Link className="catalog-result__action" to={`/obra?${params.toString()}`} state={{ work }}>
          {catalogText(locale, 'open_work')}
          <Icon name="arrow" size={16} />
        </Link>
      </div>
    </article>
  )
}

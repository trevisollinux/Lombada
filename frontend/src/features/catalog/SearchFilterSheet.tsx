import { useEffect } from 'react'

import { Icon } from '../../components/Icon'
import { Portal } from '../../components/Portal'
import { SelectMenu } from '../../components/SelectMenu'
import type { Locale } from '../../i18n'
import type { CatalogPublisher, CatalogSort } from '../../types/catalog'
import { exploreText } from '../explore/exploreI18n'

export interface SearchFilters {
  publisher: string
  sort: CatalogSort
  withReviews: boolean
  readingNow: boolean
  withCover: boolean
  withIsbn: boolean
  portuguese: boolean
}

export function countActiveFilters(filters: SearchFilters): number {
  return (
    (filters.publisher ? 1 : 0) +
    (filters.sort ? 1 : 0) +
    (filters.withReviews ? 1 : 0) +
    (filters.readingNow ? 1 : 0) +
    (filters.withCover ? 1 : 0) +
    (filters.withIsbn ? 1 : 0) +
    (filters.portuguese ? 1 : 0)
  )
}

interface SearchFilterSheetProps {
  locale: Locale
  filters: SearchFilters
  publishers: CatalogPublisher[]
  onChange: (patch: Partial<SearchFilters>) => void
  onClear: () => void
  onClose: () => void
}

export function SearchFilterSheet({
  locale,
  filters,
  publishers,
  onChange,
  onClear,
  onClose,
}: SearchFilterSheetProps) {
  useEffect(() => {
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
  }, [onClose])

  const active = countActiveFilters(filters)

  return (
    <Portal>
    <div className="panel-layer" role="presentation">
      <button
        className="panel-backdrop"
        type="button"
        aria-label={exploreText(locale, 'see_results')}
        onClick={onClose}
      />
      <section
        className="search-filter-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="search-filter-title"
      >
        <div className="search-filter-sheet__handle" aria-hidden="true" />
        <header className="search-filter-sheet__header">
          <div>
            <p className="eyebrow">{exploreText(locale, 'filters')}</p>
            <h2 id="search-filter-title">{exploreText(locale, 'search_filters_title')}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose}>
            <Icon name="close" />
            <span className="sr-only">{exploreText(locale, 'see_results')}</span>
          </button>
        </header>

        <p className="search-filter-sheet__hint">{exploreText(locale, 'search_filters_hint')}</p>

        <div className="search-filter-sheet__grid">
          <SelectMenu
            label={exploreText(locale, 'publisher')}
            value={filters.publisher}
            placeholder={exploreText(locale, 'all_publishers')}
            searchable
            searchPlaceholder={exploreText(locale, 'all_publishers')}
            onChange={(value) => onChange({ publisher: value })}
            options={[
              { value: '', label: exploreText(locale, 'all_publishers') },
              ...publishers.map((item) => ({
                value: item.editora,
                label: item.editora,
                hint: String(item.obras_count),
              })),
            ]}
          />

          <SelectMenu
            label={exploreText(locale, 'sort')}
            value={filters.sort}
            placeholder={exploreText(locale, 'relevance')}
            onChange={(value) => onChange({ sort: value as CatalogSort })}
            options={[
              { value: '', label: exploreText(locale, 'relevance') },
              { value: 'popular', label: exploreText(locale, 'most_read') },
              { value: 'avaliacao', label: exploreText(locale, 'best_rated') },
              { value: 'recentes', label: exploreText(locale, 'recent') },
            ]}
          />
        </div>

        <div className="search-filter-sheet__toggles">
          <FilterToggle
            active={filters.withReviews}
            label={exploreText(locale, 'with_reviews')}
            onClick={() => onChange({ withReviews: !filters.withReviews })}
          />
          <FilterToggle
            active={filters.readingNow}
            label={exploreText(locale, 'reading_now')}
            onClick={() => onChange({ readingNow: !filters.readingNow })}
          />
          <FilterToggle
            active={filters.withCover}
            label={exploreText(locale, 'with_cover')}
            onClick={() => onChange({ withCover: !filters.withCover })}
          />
          <FilterToggle
            active={filters.withIsbn}
            label={exploreText(locale, 'with_isbn')}
            onClick={() => onChange({ withIsbn: !filters.withIsbn })}
          />
          <FilterToggle
            active={filters.portuguese}
            label={exploreText(locale, 'portuguese')}
            onClick={() => onChange({ portuguese: !filters.portuguese })}
          />
        </div>

        <footer className="search-filter-sheet__actions">
          <button
            type="button"
            className="text-button"
            onClick={onClear}
            disabled={active === 0}
          >
            {exploreText(locale, 'clear')}
          </button>
          <button type="button" className="button button--primary" onClick={onClose}>
            {exploreText(locale, 'see_results')}
          </button>
        </footer>
      </section>
    </div>
    </Portal>
  )
}

function FilterToggle({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button type="button" className={active ? 'is-active' : ''} aria-pressed={active} onClick={onClick}>
      <span aria-hidden="true">{active ? '✓' : '+'}</span>
      {label}
    </button>
  )
}

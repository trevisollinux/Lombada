import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { usePreferences } from '../providers/PreferencesProvider'

const suggestions = [
  'Virginia Woolf',
  'Crime e Castigo',
  'literatura brasileira',
  'Companhia das Letras',
]

export function SearchPage() {
  const { t } = usePreferences()
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const activeQuery = searchParams.get('q')?.trim() || ''

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = query.trim()
    if (normalized) setSearchParams({ q: normalized })
    else setSearchParams({})
  }

  return (
    <section className="page page--search">
      <PageHeader
        eyebrow={t('search_eyebrow')}
        title={t('search_title')}
        description={t('search_copy')}
        aside={<span className="stage-stamp">01 · shell</span>}
      />

      <form className="search-form" onSubmit={submit} role="search">
        <Icon name="search" size={24} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('search_placeholder')}
          aria-label={t('search_placeholder')}
        />
        <button type="submit">{t('search_button')}</button>
      </form>

      <div className="suggestion-row" aria-label="Sugestões">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => {
              setQuery(suggestion)
              setSearchParams({ q: suggestion })
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>

      <section className="migration-preview" aria-live="polite">
        <div className="migration-preview__number">01</div>
        <div>
          <p className="eyebrow">{t('feature_next')}</p>
          <h2>{activeQuery ? `“${activeQuery}”` : t('search_preview')}</h2>
          <p>
            {activeQuery
              ? t('search_preview')
              : 'A URL, o formulário e o estado já estão no React. A consulta ao catálogo entra na etapa de busca.'}
          </p>
        </div>
        <Icon name="arrow" size={28} />
      </section>
    </section>
  )
}

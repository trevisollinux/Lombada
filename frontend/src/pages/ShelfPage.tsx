import { PageHeader } from '../components/PageHeader'
import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'

export function ShelfPage() {
  const { t } = usePreferences()
  const { account, status } = useSession()

  const stats = [
    { value: account?.edicoes_possui ?? 0, label: t('owned_editions') },
    { value: account?.edicoes_desejadas ?? 0, label: t('wanted_editions') },
    { value: account?.followers_count ?? 0, label: t('followers') },
    { value: account?.following_count ?? 0, label: t('following') },
  ]

  return (
    <section className="page">
      <PageHeader
        eyebrow={t('shelf_eyebrow')}
        title={t('shelf_title')}
        description={t('shelf_copy')}
        aside={<span className="stage-stamp">03 · dados</span>}
      />

      <div className="stat-grid" aria-busy={status === 'loading'}>
        {stats.map((stat) => (
          <article className="stat-card" key={stat.label}>
            <strong>{status === 'loading' ? '—' : stat.value}</strong>
            <span>{stat.label}</span>
          </article>
        ))}
      </div>

      <section className="empty-library">
        <div className="book-spines" aria-hidden="true">
          <span /><span /><span /><span /><span />
        </div>
        <div>
          <p className="eyebrow">{t('feature_next')}</p>
          <h2>Cards, filtros e detalhes de leitura</h2>
          <p>A conta já está conectada. A próxima etapa desta tela será consumir `/api/prateleira`.</p>
        </div>
      </section>
    </section>
  )
}

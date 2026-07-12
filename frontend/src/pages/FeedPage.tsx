import { PageHeader } from '../components/PageHeader'
import { usePreferences } from '../providers/PreferencesProvider'

const previewItems = [
  { initials: 'VL', width: '82%' },
  { initials: 'MC', width: '68%' },
  { initials: 'AB', width: '76%' },
]

export function FeedPage() {
  const { t } = usePreferences()

  return (
    <section className="page">
      <PageHeader
        eyebrow={t('feed_eyebrow')}
        title={t('feed_title')}
        description={t('feed_copy')}
        aside={<span className="stage-stamp">06 · social</span>}
      />

      <div className="preview-list" aria-hidden="true">
        {previewItems.map((item, index) => (
          <article className="feed-preview-card" key={item.initials}>
            <span className="preview-avatar">{item.initials}</span>
            <div className="preview-lines">
              <span style={{ width: item.width }} />
              <span style={{ width: `${54 + index * 8}%` }} />
              <span style={{ width: '38%' }} />
            </div>
            <div className="preview-cover" />
          </article>
        ))}
      </div>

      <p className="migration-note">{t('feature_next')} · explorar, críticas e atividade</p>
    </section>
  )
}

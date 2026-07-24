import { PageHeader } from '../components/PageHeader'
import { CommunityFeed } from '../features/feed/CommunityFeed'
import { usePreferences } from '../providers/PreferencesProvider'

export function FeedPage() {
  const { t } = usePreferences()
  return (
    <section className="page page--feed">
      <PageHeader title={t('feed_title')} description={t('feed_copy')} />
      <CommunityFeed />
    </section>
  )
}

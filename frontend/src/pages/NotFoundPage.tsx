import { Link } from 'react-router'

import { Icon } from '../components/Icon'
import { usePreferences } from '../providers/PreferencesProvider'

export function NotFoundPage() {
  const { t } = usePreferences()

  return (
    <section className="page not-found-page">
      <p className="not-found-page__code">404</p>
      <p className="eyebrow">{t('app_v2')}</p>
      <h1>{t('route_not_found')}</h1>
      <p>{t('route_not_found_copy')}</p>
      <Link className="button button--primary" to="/">
        {t('go_home')}
        <Icon name="arrow" size={18} />
      </Link>
    </section>
  )
}

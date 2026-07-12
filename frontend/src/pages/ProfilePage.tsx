import { AccountAvatar } from '../components/AccountAvatar'
import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { usePreferences } from '../providers/PreferencesProvider'
import { useSession } from '../providers/SessionProvider'

export function ProfilePage() {
  const { t } = usePreferences()
  const { account, status, refresh } = useSession()

  return (
    <section className="page">
      <PageHeader
        eyebrow={t('profile_eyebrow')}
        title={t('profile_title')}
        description={t('profile_copy')}
        aside={<span className="stage-stamp">05 · identidade</span>}
      />

      {status === 'loading' && (
        <div className="profile-card profile-card--loading" aria-busy="true">
          <div className="profile-skeleton profile-skeleton--avatar" />
          <div className="profile-skeleton-group">
            <div className="profile-skeleton" />
            <div className="profile-skeleton profile-skeleton--short" />
          </div>
        </div>
      )}

      {status === 'error' && (
        <div className="profile-card profile-card--error">
          <p>{t('account_error')}</p>
          <button className="button button--secondary" type="button" onClick={() => void refresh()}>
            <Icon name="refresh" size={17} />
            {t('retry')}
          </button>
        </div>
      )}

      {status === 'ready' && account && (
        <>
          <article className="profile-card">
            <AccountAvatar account={account} size="large" />
            <div className="profile-card__identity">
              <p className="eyebrow">{account.logado ? t('account_google') : t('account_anonymous')}</p>
              <h2>{account.nome || `@${account.handle}`}</h2>
              <p className="profile-handle">@{account.handle}</p>
              {account.bio && <p className="profile-bio">{account.bio}</p>}
            </div>
            <div className="profile-card__actions">
              {account.logado ? (
                <a className="button button--secondary" href="/api/auth/logout">{t('sign_out')}</a>
              ) : (
                <a className="button button--primary" href="/api/auth/google/login">{t('sign_in')}</a>
              )}
              <a className="button button--ghost" href={`/u/${account.handle}`} target="_blank" rel="noreferrer">
                {t('public_profile')}
                <Icon name="external" size={16} />
              </a>
            </div>
          </article>

          <div className="stat-grid stat-grid--profile">
            <article className="stat-card">
              <strong>{account.followers_count}</strong>
              <span>{t('followers')}</span>
            </article>
            <article className="stat-card">
              <strong>{account.following_count}</strong>
              <span>{t('following')}</span>
            </article>
            <article className="stat-card">
              <strong>{account.edicoes_possui}</strong>
              <span>{t('owned_editions')}</span>
            </article>
            <article className="stat-card">
              <strong>{account.edicoes_desejadas}</strong>
              <span>{t('wanted_editions')}</span>
            </article>
          </div>
        </>
      )}
    </section>
  )
}

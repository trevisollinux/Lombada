import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import { progressText } from './progressI18n'

interface OnboardingValueCardProps {
  locale: Locale
  onStart: () => void
  onDismiss: () => void
}

export const ONBOARDING_MARKER = 'lombada_onboarding_value'
export const ONBOARDING_DISMISSED = 'lombada_v2_onboarding_dismissed'

export function OnboardingValueCard({ locale, onStart, onDismiss }: OnboardingValueCardProps) {
  return (
    <section className="onboarding-value" aria-labelledby="onboarding-value-title">
      <div className="onboarding-value__mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="onboarding-value__copy">
        <p className="eyebrow">{progressText(locale, 'onboarding_eyebrow')}</p>
        <h2 id="onboarding-value-title">{progressText(locale, 'onboarding_title')}</h2>
        <p>{progressText(locale, 'onboarding_copy')}</p>
        <div className="onboarding-value__actions">
          <button className="button button--primary" type="button" onClick={onStart}>
            <Icon name="search" size={17} />
            {progressText(locale, 'onboarding_cta')}
          </button>
          <a className="button button--secondary" href="/">
            {progressText(locale, 'onboarding_missing')}
            <Icon name="external" size={15} />
          </a>
          <button className="text-button" type="button" onClick={onDismiss}>
            {progressText(locale, 'onboarding_close')}
          </button>
        </div>
      </div>
    </section>
  )
}

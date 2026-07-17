export const publicFeatureNames = [
  'home_ritual',
  'product_analytics',
  'progress_sessions',
  'progress_feedback',
  'onboarding_value',
  'favorite_books',
  'period_recaps',
  'literary_reactions',
  'progress_comments',
  'weekly_rhythm',
  'editorial_achievements',
  'reading_twin',
  'push_notifications',
] as const

export type PublicFeatureName = (typeof publicFeatureNames)[number]

export type PublicFeatureSnapshot = Record<PublicFeatureName, boolean>

export interface FeatureFlagsResponse {
  version: number
  features: Partial<Record<PublicFeatureName, boolean>>
}

export interface ReadingProgressSummary {
  paginas_total: number | null
  pagina_atual: number | null
  porcentagem: number | null
  paginas_restantes: number | null
  sessoes: number
  delta_ultima: number | null
  paginas_7d: number | null
  previsao_dias: number | null
  ultima_sessao_em: string | null
}

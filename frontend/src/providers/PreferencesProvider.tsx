import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react'

import { translate, type Locale, type TranslationKey } from '../i18n'

export type Theme = 'dark' | 'light'

interface PreferencesContextValue {
  theme: Theme
  locale: Locale
  setTheme: (theme: Theme) => void
  setLocale: (locale: Locale) => void
  t: (key: TranslationKey) => string
}

const THEME_KEY = 'lombada_theme'
const LOCALE_KEY = 'lombada_locale'

const PreferencesContext = createContext<PreferencesContextValue | null>(null)

function initialTheme(): Theme {
  return localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark'
}

function initialLocale(): Locale {
  return localStorage.getItem(LOCALE_KEY) === 'en' ? 'en' : 'pt-BR'
}

export function PreferencesProvider({ children }: PropsWithChildren) {
  const [theme, setThemeState] = useState<Theme>(initialTheme)
  const [locale, setLocaleState] = useState<Locale>(initialLocale)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.lang = locale
    localStorage.setItem(LOCALE_KEY, locale)
  }, [locale])

  const value = useMemo<PreferencesContextValue>(
    () => ({
      theme,
      locale,
      setTheme: setThemeState,
      setLocale: setLocaleState,
      t: (key) => translate(locale, key),
    }),
    [locale, theme],
  )

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  )
}

export function usePreferences(): PreferencesContextValue {
  const context = useContext(PreferencesContext)
  if (!context) {
    throw new Error('usePreferences deve ser usado dentro de PreferencesProvider')
  }
  return context
}

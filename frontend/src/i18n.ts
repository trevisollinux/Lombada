export type Locale = 'pt-BR' | 'en'

export type TranslationKey =
  | 'app_v2'
  | 'development_label'
  | 'settings'
  | 'close'
  | 'nav_search'
  | 'nav_explore'
  | 'nav_feed'
  | 'nav_shelf'
  | 'nav_diary'
  | 'nav_profile'
  | 'quick_action'
  | 'search_eyebrow'
  | 'search_title'
  | 'search_copy'
  | 'search_placeholder'
  | 'search_button'
  | 'search_preview'
  | 'feed_eyebrow'
  | 'feed_title'
  | 'feed_copy'
  | 'shelf_eyebrow'
  | 'shelf_title'
  | 'shelf_copy'
  | 'diary_eyebrow'
  | 'diary_title'
  | 'diary_copy'
  | 'profile_eyebrow'
  | 'profile_title'
  | 'profile_copy'
  | 'appearance'
  | 'theme_dark'
  | 'theme_light'
  | 'language'
  | 'portuguese'
  | 'english'
  | 'account'
  | 'account_anonymous'
  | 'account_google'
  | 'anonymous_hint'
  | 'logged_hint'
  | 'sign_in'
  | 'sign_out'
  | 'open_legacy'
  | 'loading_account'
  | 'account_error'
  | 'retry'
  | 'followers'
  | 'following'
  | 'owned_editions'
  | 'wanted_editions'
  | 'public_profile'
  | 'quick_title'
  | 'quick_copy'
  | 'quick_register'
  | 'quick_diary'
  | 'quick_legacy'
  | 'route_not_found'
  | 'route_not_found_copy'
  | 'go_home'
  | 'migration_badge'
  | 'feature_next'

const messages: Record<Locale, Record<TranslationKey, string>> = {
  'pt-BR': {
    app_v2: 'Lombada v2',
    development_label: 'frontend React em migração',
    settings: 'Configurações',
    close: 'Fechar',
    nav_search: 'Buscar',
    nav_explore: 'Explorar',
    nav_feed: 'Feed',
    nav_shelf: 'Estante',
    nav_diary: 'Diário',
    nav_profile: 'Perfil',
    quick_action: 'Adicionar',
    search_eyebrow: 'descobrir · registrar · lembrar',
    search_title: 'O que você está lendo?',
    search_copy: 'Busque por título, autor ou ISBN e escolha a edição que entrou na sua história.',
    search_placeholder: 'título, autor ou ISBN…',
    search_button: 'buscar',
    search_preview: 'Consulte o catálogo e registre a edição certa na sua estante.',
    feed_eyebrow: 'comunidade',
    feed_title: 'Feed',
    feed_copy: 'Leituras, críticas e textos da comunidade, com interações em tempo real.',
    shelf_eyebrow: 'sua biblioteca',
    shelf_title: 'Estante',
    shelf_copy: 'Todas as suas leituras, edições e relatos em um só lugar.',
    diary_eyebrow: 'durante a leitura',
    diary_title: 'Diário',
    diary_copy: 'Progresso, impressões e capítulos organizados ao longo da leitura.',
    profile_eyebrow: 'sua identidade leitora',
    profile_title: 'Perfil',
    profile_copy: 'Os dados abaixo já vêm da conta e da sessão atuais do Lombada.',
    appearance: 'Aparência',
    theme_dark: 'Escuro',
    theme_light: 'Claro',
    language: 'Idioma',
    portuguese: 'Português',
    english: 'English',
    account: 'Conta',
    account_anonymous: 'Conta anônima',
    account_google: 'Conta Google',
    anonymous_hint: 'Suas leituras ficam nesta sessão. Entre com Google para protegê-las e sincronizá-las.',
    logged_hint: 'Sua sessão Google está conectada ao mesmo acervo do aplicativo atual.',
    sign_in: 'Entrar com Google',
    sign_out: 'Sair da conta',
    open_legacy: 'Abrir aplicativo atual',
    loading_account: 'Carregando sua conta…',
    account_error: 'Não foi possível carregar a conta agora.',
    retry: 'Tentar novamente',
    followers: 'seguidores',
    following: 'seguindo',
    owned_editions: 'edições na coleção',
    wanted_editions: 'edições desejadas',
    public_profile: 'Abrir perfil público',
    quick_title: 'Registrar uma leitura',
    quick_copy: 'Busque a obra, escolha a edição ou registre uma anotação no diário.',
    quick_register: 'Buscar e adicionar',
    quick_diary: 'Abrir diário',
    quick_legacy: 'Abrir app atual',
    route_not_found: 'Página não encontrada',
    route_not_found_copy: 'Esta rota ainda não existe no Lombada v2.',
    go_home: 'Voltar para buscar',
    migration_badge: 'v2 em construção',
    feature_next: 'próxima etapa da migração',
  },
  en: {
    app_v2: 'Lombada v2',
    development_label: 'React frontend migration',
    settings: 'Settings',
    close: 'Close',
    nav_search: 'Search',
    nav_explore: 'Explore',
    nav_feed: 'Feed',
    nav_shelf: 'Shelf',
    nav_diary: 'Diary',
    nav_profile: 'Profile',
    quick_action: 'Add',
    search_eyebrow: 'discover · log · remember',
    search_title: 'What are you reading?',
    search_copy: 'Search by title, author or ISBN and choose the edition that became part of your story.',
    search_placeholder: 'title, author or ISBN…',
    search_button: 'search',
    search_preview: 'Search the catalog and log the right edition on your shelf.',
    feed_eyebrow: 'community',
    feed_title: 'Feed',
    feed_copy: 'Community readings, reviews and texts, with real-time interactions.',
    shelf_eyebrow: 'your library',
    shelf_title: 'Shelf',
    shelf_copy: 'All your readings, editions and notes in one place.',
    diary_eyebrow: 'while reading',
    diary_title: 'Diary',
    diary_copy: 'Progress, impressions and chapters organized throughout your reading.',
    profile_eyebrow: 'your reader identity',
    profile_title: 'Profile',
    profile_copy: 'The data below already comes from your current Lombada account and session.',
    appearance: 'Appearance',
    theme_dark: 'Dark',
    theme_light: 'Light',
    language: 'Language',
    portuguese: 'Português',
    english: 'English',
    account: 'Account',
    account_anonymous: 'Anonymous account',
    account_google: 'Google account',
    anonymous_hint: 'Your readings stay in this session. Sign in with Google to protect and sync them.',
    logged_hint: 'Your Google session uses the same collection as the current app.',
    sign_in: 'Sign in with Google',
    sign_out: 'Sign out',
    open_legacy: 'Open current app',
    loading_account: 'Loading your account…',
    account_error: 'The account could not be loaded right now.',
    retry: 'Try again',
    followers: 'followers',
    following: 'following',
    owned_editions: 'editions owned',
    wanted_editions: 'wanted editions',
    public_profile: 'Open public profile',
    quick_title: 'Log a reading',
    quick_copy: 'Find the work, choose the edition or add a journal entry.',
    quick_register: 'Search and add',
    quick_diary: 'Open diary',
    quick_legacy: 'Open current app',
    route_not_found: 'Page not found',
    route_not_found_copy: 'This route does not exist in Lombada v2 yet.',
    go_home: 'Back to search',
    migration_badge: 'v2 in progress',
    feature_next: 'next migration step',
  },
}

export function translate(locale: Locale, key: TranslationKey): string {
  return messages[locale][key]
}

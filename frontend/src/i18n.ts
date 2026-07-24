export type Locale = 'pt-BR' | 'en' | 'es'

export type TranslationKey =
  | 'app_v2'
  | 'development_label'
  | 'settings'
  | 'close'
  | 'nav_menu'
  | 'nav_search'
  | 'nav_explore'
  | 'nav_feed'
  | 'nav_shelf'
  | 'nav_diary'
  | 'nav_memories'
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
  | 'memories_eyebrow'
  | 'memories_title'
  | 'memories_copy'
  | 'profile_eyebrow'
  | 'profile_title'
  | 'profile_copy'
  | 'appearance'
  | 'theme_dark'
  | 'theme_light'
  | 'language'
  | 'portuguese'
  | 'english'
  | 'spanish'
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
  | 'cold_start_title'
  | 'cold_start_hint'
  | 'cold_start_error'
  | 'cold_start_error_hint'
  | 'cold_start_reload'
  | 'update_available'
  | 'update_action'
  | 'update_dismiss'
  | 'followers'
  | 'following'
  | 'owned_editions'
  | 'wanted_editions'
  | 'public_profile'
  | 'quick_title'
  | 'quick_copy'
  | 'quick_register'
  | 'quick_diary'
  | 'quick_memories'
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
    nav_menu: 'menu',
    nav_search: 'Buscar',
    nav_explore: 'Explorar',
    nav_feed: 'Feed',
    nav_shelf: 'Estante',
    nav_diary: 'Diário',
    nav_memories: 'Memórias',
    nav_profile: 'Perfil',
    quick_action: 'Adicionar',
    search_eyebrow: 'descobrir · registrar · lembrar',
    search_title: 'O que você está lendo?',
    search_copy: 'Busque por título, autor ou ISBN e escolha a edição que entrou na sua história.',
    search_placeholder: 'que livro você está lendo agora?',
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
    memories_eyebrow: 'memória de leitura',
    memories_title: 'Memórias',
    memories_copy: 'Cards, retrospectivas e imagens prontas para compartilhar ou guardar.',
    profile_eyebrow: 'sua identidade leitora',
    profile_title: 'Perfil',
    profile_copy: 'Os dados abaixo já vêm da conta e da sessão atuais do Lombada.',
    appearance: 'Aparência',
    theme_dark: 'Escuro',
    theme_light: 'Claro',
    language: 'Idioma',
    portuguese: 'Português',
    english: 'English',
    spanish: 'Español',
    account: 'Conta',
    account_anonymous: 'Conta anônima',
    account_google: 'Conta Google',
    anonymous_hint: 'Suas leituras ficam nesta sessão. Entre com Google para protegê-las e sincronizá-las.',
    logged_hint: 'Sua sessão Google mantém suas leituras salvas e sincronizadas.',
    sign_in: 'Entrar com Google',
    sign_out: 'Sair da conta',
    open_legacy: 'Abrir aplicativo atual',
    loading_account: 'Carregando sua conta…',
    account_error: 'Não foi possível carregar a conta agora.',
    retry: 'Tentar novamente',
    cold_start_title: 'acordando a estante…',
    cold_start_hint: 'a primeira visita depois de um tempo parado pode levar até 30 segundos.',
    cold_start_error: 'Não consegui carregar agora.',
    cold_start_error_hint: 'Verifique a conexão ou recarregue a página.',
    cold_start_reload: 'Recarregar',
    update_available: 'Nova versão da Lombada disponível.',
    update_action: 'Atualizar',
    update_dismiss: 'Agora não',
    followers: 'seguidores',
    following: 'seguindo',
    owned_editions: 'edições na coleção',
    wanted_editions: 'edições desejadas',
    public_profile: 'Abrir perfil público',
    quick_title: 'Registrar uma leitura',
    quick_copy: 'Busque a obra, escolha a edição ou registre uma anotação no diário.',
    quick_register: 'Buscar e adicionar',
    quick_diary: 'Abrir diário',
    quick_memories: 'Criar card ou retrospectiva',
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
    nav_menu: 'menu',
    nav_search: 'Search',
    nav_explore: 'Explore',
    nav_feed: 'Feed',
    nav_shelf: 'Shelf',
    nav_diary: 'Diary',
    nav_memories: 'Memories',
    nav_profile: 'Profile',
    quick_action: 'Add',
    search_eyebrow: 'discover · log · remember',
    search_title: 'What are you reading?',
    search_copy: 'Search by title, author or ISBN and choose the edition that became part of your story.',
    search_placeholder: 'what book are you reading right now?',
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
    memories_eyebrow: 'reading memory',
    memories_title: 'Memories',
    memories_copy: 'Cards, recaps and images ready to share or keep.',
    profile_eyebrow: 'your reader identity',
    profile_title: 'Profile',
    profile_copy: 'The data below already comes from your current Lombada account and session.',
    appearance: 'Appearance',
    theme_dark: 'Dark',
    theme_light: 'Light',
    language: 'Language',
    portuguese: 'Português',
    english: 'English',
    spanish: 'Español',
    account: 'Account',
    account_anonymous: 'Anonymous account',
    account_google: 'Google account',
    anonymous_hint: 'Your readings stay in this session. Sign in with Google to protect and sync them.',
    logged_hint: 'Your Google session keeps your readings saved and synced.',
    sign_in: 'Sign in with Google',
    sign_out: 'Sign out',
    open_legacy: 'Open current app',
    loading_account: 'Loading your account…',
    account_error: 'The account could not be loaded right now.',
    retry: 'Try again',
    cold_start_title: 'waking up the shelf…',
    cold_start_hint: 'the first visit after a while can take up to 30 seconds.',
    cold_start_error: "Couldn't load right now.",
    cold_start_error_hint: 'Check your connection or reload the page.',
    cold_start_reload: 'Reload',
    update_available: 'A new version of Lombada is available.',
    update_action: 'Update',
    update_dismiss: 'Not now',
    followers: 'followers',
    following: 'following',
    owned_editions: 'editions owned',
    wanted_editions: 'wanted editions',
    public_profile: 'Open public profile',
    quick_title: 'Log a reading',
    quick_copy: 'Find the work, choose the edition or add a journal entry.',
    quick_register: 'Search and add',
    quick_diary: 'Open diary',
    quick_memories: 'Create a card or recap',
    quick_legacy: 'Open current app',
    route_not_found: 'Page not found',
    route_not_found_copy: 'This route does not exist in Lombada v2 yet.',
    go_home: 'Back to search',
    migration_badge: 'v2 in progress',
    feature_next: 'next migration step',
  },
  es: {
    app_v2: 'Lombada v2',
    development_label: 'Migración del frontend React',
    settings: 'Ajustes',
    close: 'Cerrar',
    nav_menu: 'menú',
    nav_search: 'Buscar',
    nav_explore: 'Explorar',
    nav_feed: 'Feed',
    nav_shelf: 'Estantería',
    nav_diary: 'Diario',
    nav_memories: 'Memorias',
    nav_profile: 'Perfil',
    quick_action: 'Añadir',
    search_eyebrow: 'descubre · registra · recuerda',
    search_title: '¿Qué estás leyendo?',
    search_copy: 'Busca por título, autor o ISBN y elige la edición que entró en tu historia.',
    search_placeholder: '¿qué libro estás leyendo ahora?',
    search_button: 'buscar',
    search_preview: 'Consulta el catálogo y registra la edición correcta en tu estantería.',
    feed_eyebrow: 'comunidad',
    feed_title: 'Feed',
    feed_copy: 'Lecturas, reseñas y textos de la comunidad, con interacciones en tiempo real.',
    shelf_eyebrow: 'tu biblioteca',
    shelf_title: 'Estantería',
    shelf_copy: 'Todas tus lecturas, ediciones y notas en un solo lugar.',
    diary_eyebrow: 'durante la lectura',
    diary_title: 'Diario',
    diary_copy: 'Progreso, impresiones y capítulos organizados a lo largo de la lectura.',
    memories_eyebrow: 'memoria de lectura',
    memories_title: 'Memorias',
    memories_copy: 'Tarjetas, retrospectivas e imágenes listas para compartir o guardar.',
    profile_eyebrow: 'tu identidad lectora',
    profile_title: 'Perfil',
    profile_copy: 'Los datos de abajo ya vienen de la cuenta y la sesión actuales de Lombada.',
    appearance: 'Apariencia',
    theme_dark: 'Oscuro',
    theme_light: 'Claro',
    language: 'Idioma',
    portuguese: 'Português',
    english: 'English',
    spanish: 'Español',
    account: 'Cuenta',
    account_anonymous: 'Cuenta anónima',
    account_google: 'Cuenta Google',
    anonymous_hint: 'Tus lecturas quedan en esta sesión. Entra con Google para protegerlas y sincronizarlas.',
    logged_hint: 'Tu sesión de Google mantiene tus lecturas guardadas y sincronizadas.',
    sign_in: 'Entrar con Google',
    sign_out: 'Cerrar sesión',
    open_legacy: 'Abrir app actual',
    loading_account: 'Cargando tu cuenta…',
    account_error: 'No se pudo cargar la cuenta ahora.',
    retry: 'Reintentar',
    cold_start_title: 'despertando la estantería…',
    cold_start_hint: 'la primera visita tras un tiempo inactiva puede tardar hasta 30 segundos.',
    cold_start_error: 'No pude cargar ahora.',
    cold_start_error_hint: 'Revisa la conexión o recarga la página.',
    cold_start_reload: 'Recargar',
    update_available: 'Hay una nueva versión de Lombada.',
    update_action: 'Actualizar',
    update_dismiss: 'Ahora no',
    followers: 'seguidores',
    following: 'siguiendo',
    owned_editions: 'ediciones en la colección',
    wanted_editions: 'ediciones deseadas',
    public_profile: 'Abrir perfil público',
    quick_title: 'Registrar una lectura',
    quick_copy: 'Busca la obra, elige la edición o añade una nota al diario.',
    quick_register: 'Buscar y añadir',
    quick_diary: 'Abrir diario',
    quick_memories: 'Crear tarjeta o retrospectiva',
    quick_legacy: 'Abrir app actual',
    route_not_found: 'Página no encontrada',
    route_not_found_copy: 'Esta ruta aún no existe en Lombada v2.',
    go_home: 'Volver a buscar',
    migration_badge: 'v2 en construcción',
    feature_next: 'siguiente etapa de la migración',
  },
}

export function translate(locale: Locale, key: TranslationKey): string {
  return messages[locale][key]
}

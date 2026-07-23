import type { Locale } from '../../i18n'

export type MemoriesTextKey =
  | 'eyebrow'
  | 'title'
  | 'copy'
  | 'period_title'
  | 'period_copy'
  | 'week'
  | 'month'
  | 'current_week'
  | 'current_month'
  | 'previous'
  | 'next'
  | 'sessions'
  | 'active_days'
  | 'books_touched'
  | 'pages_advanced'
  | 'updates'
  | 'highlights'
  | 'period_empty_current'
  | 'period_empty_past'
  | 'period_unavailable'
  | 'library_title'
  | 'library_copy'
  | 'books_read'
  | 'pages_read'
  | 'top_author'
  | 'average_rating'
  | 'favorite'
  | 'library_empty'
  | 'share_card'
  | 'download_card'
  | 'copy_profile_link'
  | 'link_copied'
  | 'card_downloaded'
  | 'card_shared'
  | 'card_error'
  | 'card_preview'
  | 'card_theme'
  | 'theme_auto'
  | 'theme_light'
  | 'theme_dark'
  | 'cover_style'
  | 'cover_original'
  | 'cover_editorial'
  | 'cover_editorial_dark'
  | 'include_excerpt'
  | 'excerpt_spoiler_warning'
  | 'close'
  | 'generating'
  | 'open_diary'
  | 'reading_card'
  | 'review_card'
  | 'diary_card'
  | 'period_card_week'
  | 'period_card_month'
  | 'library_card'
  | 'reading_memory'
  | 'completed_period'
  | 'period_in_progress'
  | 'page'
  | 'chapter'
  | 'public_profile'

const messages: Record<Locale, Record<MemoriesTextKey, string>> = {
  'pt-BR': {
    eyebrow: 'memória de leitura',
    title: 'Memórias',
    copy: 'Cards, retrospectivas e imagens prontas para compartilhar ou guardar.',
    period_title: 'Sua retrospectiva de leitura',
    period_copy: 'Revise semanas e meses a partir dos registros reais do diário.',
    week: 'Semana',
    month: 'Mês',
    current_week: 'Sua semana até agora',
    current_month: 'Seu mês até agora',
    previous: 'Período anterior',
    next: 'Período seguinte',
    sessions: 'sessões',
    active_days: 'dias ativos',
    books_touched: 'livros tocados',
    pages_advanced: 'páginas avançadas',
    updates: 'atualizações',
    highlights: 'Livros deste período',
    period_empty_current: 'Este período ainda está em branco. Ele começa quando você registra “Li mais”.',
    period_empty_past: 'Nenhuma sessão foi registrada neste período — e tudo bem.',
    period_unavailable: 'A retrospectiva semanal e mensal não está disponível nesta configuração.',
    library_title: 'Retrospectiva da estante',
    library_copy: 'Um panorama acumulado dos livros marcados como lidos.',
    books_read: 'livros lidos',
    pages_read: 'páginas',
    top_author: 'autor mais lido',
    average_rating: 'média das notas',
    favorite: 'favorito',
    library_empty: 'Marque ao menos um livro como lido para montar sua retrospectiva.',
    share_card: 'Compartilhar imagem',
    download_card: 'Baixar imagem',
    copy_profile_link: 'Copiar perfil',
    link_copied: 'Link do perfil copiado.',
    card_downloaded: 'Imagem baixada.',
    card_shared: 'Imagem compartilhada.',
    card_error: 'Não foi possível criar a imagem agora.',
    card_preview: 'Prévia do card',
    card_theme: 'Tema',
    theme_auto: 'Automático',
    theme_light: 'Claro',
    theme_dark: 'Escuro',
    cover_style: 'Capa',
    cover_original: 'Original',
    cover_editorial: 'Editorial clara',
    cover_editorial_dark: 'Editorial escura',
    include_excerpt: 'Incluir trecho',
    excerpt_spoiler_warning: 'O trecho contém spoiler e começa oculto.',
    close: 'Fechar',
    generating: 'Gerando imagem…',
    open_diary: 'Abrir diário',
    reading_card: 'Leitura',
    review_card: 'Crítica',
    diary_card: 'Diário de leitura',
    period_card_week: 'MINHA SEMANA DE LEITURA',
    period_card_month: 'MEU MÊS DE LEITURA',
    library_card: 'MINHA RETROSPECTIVA',
    reading_memory: 'uma memória de leitura',
    completed_period: 'período fechado',
    period_in_progress: 'em andamento',
    page: 'página',
    chapter: 'capítulo',
    public_profile: 'Perfil público',
  },
  en: {
    eyebrow: 'reading memory',
    title: 'Memories',
    copy: 'Cards, recaps and images ready to share or keep.',
    period_title: 'Your reading recap',
    period_copy: 'Review weeks and months using real diary entries.',
    week: 'Week',
    month: 'Month',
    current_week: 'This week so far',
    current_month: 'This month so far',
    previous: 'Previous period',
    next: 'Next period',
    sessions: 'sessions',
    active_days: 'active days',
    books_touched: 'books touched',
    pages_advanced: 'pages advanced',
    updates: 'updates',
    highlights: 'Books in this period',
    period_empty_current: 'This period is still blank. It begins when you log “Read more”.',
    period_empty_past: 'No reading session was logged in this period — and that is all right.',
    period_unavailable: 'Weekly and monthly recaps are not available in this configuration.',
    library_title: 'Shelf recap',
    library_copy: 'A cumulative view of books marked as read.',
    books_read: 'books read',
    pages_read: 'pages',
    top_author: 'top author',
    average_rating: 'average rating',
    favorite: 'favorite',
    library_empty: 'Mark at least one book as read to build your recap.',
    share_card: 'Share image',
    download_card: 'Download image',
    copy_profile_link: 'Copy profile',
    link_copied: 'Profile link copied.',
    card_downloaded: 'Image downloaded.',
    card_shared: 'Image shared.',
    card_error: 'The image could not be created right now.',
    card_preview: 'Card preview',
    card_theme: 'Theme',
    theme_auto: 'Automatic',
    theme_light: 'Light',
    theme_dark: 'Dark',
    cover_style: 'Cover',
    cover_original: 'Original',
    cover_editorial: 'Light editorial',
    cover_editorial_dark: 'Dark editorial',
    include_excerpt: 'Include excerpt',
    excerpt_spoiler_warning: 'The excerpt contains spoilers and starts hidden.',
    close: 'Close',
    generating: 'Generating image…',
    open_diary: 'Open diary',
    reading_card: 'Reading',
    review_card: 'Review',
    diary_card: 'Reading diary',
    period_card_week: 'MY READING WEEK',
    period_card_month: 'MY READING MONTH',
    library_card: 'MY READING RECAP',
    reading_memory: 'a reading memory',
    completed_period: 'completed period',
    period_in_progress: 'in progress',
    page: 'page',
    chapter: 'chapter',
    public_profile: 'Public profile',
  },
  es: {
    eyebrow: 'memoria de lectura',
    title: 'Memorias',
    copy: 'Tarjetas, retrospectivas e imágenes listas para compartir o guardar.',
    period_title: 'Tu retrospectiva de lectura',
    period_copy: 'Repasa semanas y meses con entradas reales del diario.',
    week: 'Semana',
    month: 'Mes',
    current_week: 'Esta semana hasta ahora',
    current_month: 'Este mes hasta ahora',
    previous: 'Período anterior',
    next: 'Período siguiente',
    sessions: 'sesiones',
    active_days: 'días activos',
    books_touched: 'libros tocados',
    pages_advanced: 'páginas avanzadas',
    updates: 'actualizaciones',
    highlights: 'Libros de este período',
    period_empty_current: 'Este período aún está en blanco. Empieza cuando registras “Leer más”.',
    period_empty_past: 'No se registró ninguna sesión de lectura en este período, y no pasa nada.',
    period_unavailable: 'Las retrospectivas semanales y mensuales no están disponibles en esta configuración.',
    library_title: 'Retrospectiva de la estantería',
    library_copy: 'Una vista acumulada de los libros marcados como leídos.',
    books_read: 'libros leídos',
    pages_read: 'páginas',
    top_author: 'autor más leído',
    average_rating: 'nota media',
    favorite: 'favorito',
    library_empty: 'Marca al menos un libro como leído para armar tu retrospectiva.',
    share_card: 'Compartir imagen',
    download_card: 'Descargar imagen',
    copy_profile_link: 'Copiar perfil',
    link_copied: 'Enlace del perfil copiado.',
    card_downloaded: 'Imagen descargada.',
    card_shared: 'Imagen compartida.',
    card_error: 'No se pudo crear la imagen ahora.',
    card_preview: 'Vista previa de la tarjeta',
    card_theme: 'Tema',
    theme_auto: 'Automático',
    theme_light: 'Claro',
    theme_dark: 'Oscuro',
    cover_style: 'Portada',
    cover_original: 'Original',
    cover_editorial: 'Editorial clara',
    cover_editorial_dark: 'Editorial oscura',
    include_excerpt: 'Incluir fragmento',
    excerpt_spoiler_warning: 'El fragmento contiene spoiler y empieza oculto.',
    close: 'Cerrar',
    generating: 'Generando imagen…',
    open_diary: 'Abrir diario',
    reading_card: 'Lectura',
    review_card: 'Reseña',
    diary_card: 'Diario de lectura',
    period_card_week: 'MI SEMANA DE LECTURA',
    period_card_month: 'MI MES DE LECTURA',
    library_card: 'MI RETROSPECTIVA',
    reading_memory: 'una memoria de lectura',
    completed_period: 'período cerrado',
    period_in_progress: 'en curso',
    page: 'página',
    chapter: 'capítulo',
    public_profile: 'Perfil público',
  },
}

export function memoriesText(locale: Locale, key: MemoriesTextKey): string {
  return messages[locale][key]
}

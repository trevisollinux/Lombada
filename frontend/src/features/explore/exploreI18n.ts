import type { Locale } from '../../i18n'

export type ExploreTextKey =
  | 'eyebrow'
  | 'title'
  | 'copy'
  | 'popular'
  | 'paths'
  | 'genres'
  | 'literatures'
  | 'publishers'
  | 'filters'
  | 'filter_copy'
  | 'publisher'
  | 'all_publishers'
  | 'literature'
  | 'all_literatures'
  | 'sort'
  | 'relevance'
  | 'most_read'
  | 'best_rated'
  | 'recent'
  | 'with_reviews'
  | 'reading_now'
  | 'with_cover'
  | 'with_isbn'
  | 'portuguese'
  | 'clear'
  | 'results'
  | 'loading'
  | 'error'
  | 'empty'
  | 'empty_copy'
  | 'show_all'
  | 'works'
  | 'editions'
  | 'coverage'
  | 'explore_publisher'
  | 'active_filters'
  | 'search_filters_title'
  | 'search_filters_hint'
  | 'see_results'
  | 'open_filters'

const messages: Record<Locale, Record<ExploreTextKey, string>> = {
  'pt-BR': {
    eyebrow: 'descoberta editorial',
    title: 'Explorar',
    copy: 'Encontre leituras por gênero, origem, editora e sinais reais da comunidade.',
    popular: 'Mais lidos na Lombada',
    paths: 'Caminhos para descobrir',
    genres: 'Gêneros',
    literatures: 'Literaturas',
    publishers: 'Editoras no catálogo',
    filters: 'Refinar descoberta',
    filter_copy: 'Combine caminhos editoriais e sinais de qualidade.',
    publisher: 'Editora',
    all_publishers: 'Todas as editoras',
    literature: 'Literatura',
    all_literatures: 'Todas as literaturas',
    sort: 'Ordenar',
    relevance: 'Relevância',
    most_read: 'Mais lidos',
    best_rated: 'Melhor avaliados',
    recent: 'Edições recentes',
    with_reviews: 'Com críticas públicas',
    reading_now: 'Lendo agora',
    with_cover: 'Com capa',
    with_isbn: 'Com ISBN',
    portuguese: 'Em português',
    clear: 'Limpar filtros',
    results: 'resultados',
    loading: 'Montando sua vitrine…',
    error: 'Não foi possível carregar o explorar.',
    empty: 'Nenhuma obra neste caminho',
    empty_copy: 'Retire um filtro ou experimente outro gênero, literatura ou editora.',
    show_all: 'Ver todos',
    works: 'obras',
    editions: 'edições',
    coverage: 'com capa',
    explore_publisher: 'Explorar editora',
    active_filters: 'Filtros ativos',
    search_filters_title: 'Filtros da busca',
    search_filters_hint: 'Refine por editora, ordenação e sinais da comunidade.',
    see_results: 'Ver resultados',
    open_filters: 'Filtros',
  },
  en: {
    eyebrow: 'editorial discovery',
    title: 'Explore',
    copy: 'Find books by genre, origin, publisher and real community signals.',
    popular: 'Most read on Lombada',
    paths: 'Paths to discover',
    genres: 'Genres',
    literatures: 'Literatures',
    publishers: 'Publishers in the catalog',
    filters: 'Refine discovery',
    filter_copy: 'Combine editorial paths and quality signals.',
    publisher: 'Publisher',
    all_publishers: 'All publishers',
    literature: 'Literature',
    all_literatures: 'All literatures',
    sort: 'Sort',
    relevance: 'Relevance',
    most_read: 'Most read',
    best_rated: 'Best rated',
    recent: 'Recent editions',
    with_reviews: 'With public reviews',
    reading_now: 'Reading now',
    with_cover: 'With cover',
    with_isbn: 'With ISBN',
    portuguese: 'In Portuguese',
    clear: 'Clear filters',
    results: 'results',
    loading: 'Building your showcase…',
    error: 'Explore could not be loaded.',
    empty: 'No books on this path',
    empty_copy: 'Remove a filter or try another genre, literature or publisher.',
    show_all: 'Show all',
    works: 'works',
    editions: 'editions',
    coverage: 'with covers',
    explore_publisher: 'Explore publisher',
    active_filters: 'Active filters',
    search_filters_title: 'Search filters',
    search_filters_hint: 'Refine by publisher, sorting and community signals.',
    see_results: 'See results',
    open_filters: 'Filters',
  },
  es: {
    eyebrow: 'descubrimiento editorial',
    title: 'Explorar',
    copy: 'Encuentra libros por género, origen, editorial y señales reales de la comunidad.',
    popular: 'Más leídos en Lombada',
    paths: 'Caminos para descubrir',
    genres: 'Géneros',
    literatures: 'Literaturas',
    publishers: 'Editoriales en el catálogo',
    filters: 'Refinar descubrimiento',
    filter_copy: 'Combina caminos editoriales y señales de calidad.',
    publisher: 'Editorial',
    all_publishers: 'Todas las editoriales',
    literature: 'Literatura',
    all_literatures: 'Todas las literaturas',
    sort: 'Ordenar',
    relevance: 'Relevancia',
    most_read: 'Más leídos',
    best_rated: 'Mejor valorados',
    recent: 'Ediciones recientes',
    with_reviews: 'Con reseñas públicas',
    reading_now: 'Leyendo ahora',
    with_cover: 'Con portada',
    with_isbn: 'Con ISBN',
    portuguese: 'En portugués',
    clear: 'Limpiar filtros',
    results: 'resultados',
    loading: 'Preparando tu vitrina…',
    error: 'No se pudo cargar Explorar.',
    empty: 'No hay libros en este camino',
    empty_copy: 'Quita un filtro o prueba otro género, literatura o editorial.',
    show_all: 'Ver todo',
    works: 'obras',
    editions: 'ediciones',
    coverage: 'con portada',
    explore_publisher: 'Explorar editorial',
    active_filters: 'Filtros activos',
    search_filters_title: 'Filtros de búsqueda',
    search_filters_hint: 'Refina por editorial, orden y señales de la comunidad.',
    see_results: 'Ver resultados',
    open_filters: 'Filtros',
  },
}

export function exploreText(locale: Locale, key: ExploreTextKey): string {
  return messages[locale][key]
}

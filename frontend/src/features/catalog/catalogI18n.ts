import type { Locale } from '../../i18n'

export type CatalogTextKey =
  | 'loading'
  | 'error'
  | 'no_results'
  | 'no_results_copy'
  | 'popular_searches'
  | 'popular_books'
  | 'results'
  | 'readings'
  | 'reviews'
  | 'reading_now'
  | 'open_work'
  | 'back_search'
  | 'editions'
  | 'edition'
  | 'publisher'
  | 'translator'
  | 'language'
  | 'year'
  | 'pages'
  | 'isbn'
  | 'unknown_edition'
  | 'no_editions'
  | 'no_editions_copy'
  | 'register'
  | 'register_title'
  | 'status'
  | 'rating'
  | 'no_rating'
  | 'reading_date'
  | 'reading_date_placeholder'
  | 'review'
  | 'review_placeholder'
  | 'make_public'
  | 'mark_spoiler'
  | 'own_edition'
  | 'want_edition'
  | 'save'
  | 'saving'
  | 'cancel'
  | 'registered'
  | 'registered_copy'
  | 'go_shelf'
  | 'duplicate'
  | 'save_error'
  | 'selected'
  | 'already_read'
  | 'owned'
  | 'wanted'
  | 'average'
  | 'edition_readings'

const messages: Record<Locale, Record<CatalogTextKey, string>> = {
  'pt-BR': {
    loading: 'Buscando no catálogo…',
    error: 'Não foi possível consultar o catálogo.',
    no_results: 'Nenhum livro encontrado',
    no_results_copy: 'Tente outro título, autor ou ISBN.',
    popular_searches: 'Buscas populares',
    popular_books: 'Livros em destaque',
    results: 'resultados',
    readings: 'leituras',
    reviews: 'críticas',
    reading_now: 'lendo agora',
    open_work: 'Ver obra e edições',
    back_search: 'Voltar à busca',
    editions: 'Edições',
    edition: 'Edição',
    publisher: 'Editora',
    translator: 'Tradução',
    language: 'Idioma',
    year: 'Ano',
    pages: 'páginas',
    isbn: 'ISBN',
    unknown_edition: 'Edição sem detalhes completos',
    no_editions: 'Nenhuma edição encontrada',
    no_editions_copy: 'A obra existe, mas ainda não encontramos edições disponíveis para registro.',
    register: 'Registrar leitura',
    register_title: 'Adicionar à estante',
    status: 'Status',
    rating: 'Nota',
    no_rating: 'sem nota',
    reading_date: 'Quando você leu',
    reading_date_placeholder: 'ex.: julho de 2026',
    review: 'Relato',
    review_placeholder: 'Você poderá editar ou complementar depois na estante.',
    make_public: 'Tornar relato público',
    mark_spoiler: 'Contém spoiler',
    own_edition: 'Tenho esta edição',
    want_edition: 'Quero esta edição',
    save: 'Adicionar à estante',
    saving: 'Adicionando…',
    cancel: 'Cancelar',
    registered: 'Leitura adicionada',
    registered_copy: 'A edição foi registrada na sua estante.',
    go_shelf: 'Abrir estante',
    duplicate: 'Esta edição já está registrada na sua estante.',
    save_error: 'Não foi possível adicionar a leitura.',
    selected: 'selecionada',
    already_read: 'já lida',
    owned: 'na coleção',
    wanted: 'desejada',
    average: 'média',
    edition_readings: 'leituras desta edição',
  },
  en: {
    loading: 'Searching the catalog…',
    error: 'The catalog could not be searched.',
    no_results: 'No books found',
    no_results_copy: 'Try another title, author or ISBN.',
    popular_searches: 'Popular searches',
    popular_books: 'Featured books',
    results: 'results',
    readings: 'readings',
    reviews: 'reviews',
    reading_now: 'reading now',
    open_work: 'View work and editions',
    back_search: 'Back to search',
    editions: 'Editions',
    edition: 'Edition',
    publisher: 'Publisher',
    translator: 'Translation',
    language: 'Language',
    year: 'Year',
    pages: 'pages',
    isbn: 'ISBN',
    unknown_edition: 'Edition details unavailable',
    no_editions: 'No editions found',
    no_editions_copy: 'The work exists, but no edition is available to log yet.',
    register: 'Log reading',
    register_title: 'Add to shelf',
    status: 'Status',
    rating: 'Rating',
    no_rating: 'not rated',
    reading_date: 'When you read it',
    reading_date_placeholder: 'e.g. July 2026',
    review: 'Reading note',
    review_placeholder: 'You can edit or expand it later from your shelf.',
    make_public: 'Make note public',
    mark_spoiler: 'Contains spoilers',
    own_edition: 'I own this edition',
    want_edition: 'I want this edition',
    save: 'Add to shelf',
    saving: 'Adding…',
    cancel: 'Cancel',
    registered: 'Reading added',
    registered_copy: 'The edition was added to your shelf.',
    go_shelf: 'Open shelf',
    duplicate: 'This edition is already on your shelf.',
    save_error: 'The reading could not be added.',
    selected: 'selected',
    already_read: 'already read',
    owned: 'owned',
    wanted: 'wanted',
    average: 'average',
    edition_readings: 'edition readings',
  },
}

export function catalogText(locale: Locale, key: CatalogTextKey): string {
  return messages[locale][key]
}

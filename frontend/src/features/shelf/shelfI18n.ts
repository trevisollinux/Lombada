import type { Locale } from '../../i18n'

export type ShelfTextKey =
  | 'all'
  | 'read'
  | 'reading'
  | 'want'
  | 'other'
  | 'grid'
  | 'list'
  | 'loading'
  | 'error'
  | 'empty_title'
  | 'empty_copy'
  | 'empty_filtered'
  | 'register'
  | 'books_count'
  | 'rating'
  | 'no_rating'
  | 'publisher'
  | 'translator'
  | 'edition'
  | 'isbn'
  | 'pages'
  | 'review'
  | 'private_review'
  | 'public_review'
  | 'spoiler'
  | 'owned'
  | 'wanted'
  | 'open_detail'
  | 'close_detail'
  | 'open_legacy'
  | 'no_review'

const messages: Record<Locale, Record<ShelfTextKey, string>> = {
  'pt-BR': {
    all: 'Todos',
    read: 'Lidos',
    reading: 'Lendo',
    want: 'Quero ler',
    other: 'Outros',
    grid: 'Grade',
    list: 'Lista',
    loading: 'Carregando sua estante…',
    error: 'Não foi possível carregar sua estante.',
    empty_title: 'Sua estante ainda está vazia',
    empty_copy: 'Registre uma leitura para começar a construir sua biblioteca pessoal.',
    empty_filtered: 'Nenhuma leitura corresponde a este filtro.',
    register: 'Buscar um livro',
    books_count: 'leituras',
    rating: 'Sua nota',
    no_rating: 'sem nota',
    publisher: 'Editora',
    translator: 'Tradução',
    edition: 'Edição',
    isbn: 'ISBN',
    pages: 'páginas',
    review: 'Relato de leitura',
    private_review: 'privado',
    public_review: 'público',
    spoiler: 'contém spoiler',
    owned: 'na sua coleção',
    wanted: 'edição desejada',
    open_detail: 'Abrir detalhes',
    close_detail: 'Fechar detalhes',
    open_legacy: 'Editar no app atual',
    no_review: 'Nenhum relato registrado para esta leitura.',
  },
  en: {
    all: 'All',
    read: 'Read',
    reading: 'Reading',
    want: 'Want to read',
    other: 'Other',
    grid: 'Grid',
    list: 'List',
    loading: 'Loading your shelf…',
    error: 'Your shelf could not be loaded.',
    empty_title: 'Your shelf is still empty',
    empty_copy: 'Log a reading to start building your personal library.',
    empty_filtered: 'No reading matches this filter.',
    register: 'Find a book',
    books_count: 'readings',
    rating: 'Your rating',
    no_rating: 'not rated',
    publisher: 'Publisher',
    translator: 'Translation',
    edition: 'Edition',
    isbn: 'ISBN',
    pages: 'pages',
    review: 'Reading note',
    private_review: 'private',
    public_review: 'public',
    spoiler: 'contains spoiler',
    owned: 'in your collection',
    wanted: 'wanted edition',
    open_detail: 'Open details',
    close_detail: 'Close details',
    open_legacy: 'Edit in current app',
    no_review: 'No reading note was saved for this book.',
  },
}

export function shelfText(locale: Locale, key: ShelfTextKey): string {
  return messages[locale][key]
}

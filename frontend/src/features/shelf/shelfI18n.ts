import type { Locale } from '../../i18n'

export type ShelfTextKey =
  | 'all'
  | 'read'
  | 'reading'
  | 'want'
  | 'other'
  | 'grid'
  | 'list'
  | 'spines'
  | 'loading'
  | 'error'
  | 'empty_title'
  | 'empty_copy'
  | 'empty_filtered'
  | 'register'
  | 'books_count'
  | 'status'
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
  | 'edit_reading'
  | 'reading_date'
  | 'reading_date_placeholder'
  | 'review_placeholder'
  | 'make_public'
  | 'make_public_hint'
  | 'mark_spoiler'
  | 'mark_spoiler_hint'
  | 'save_changes'
  | 'saving'
  | 'cancel'
  | 'remove_reading'
  | 'remove_hint'
  | 'remove_confirmation'
  | 'keep_reading'
  | 'confirm_remove'
  | 'remove'
  | 'deleting'
  | 'save_error'
  | 'delete_error'
  | 'saved_success'
  | 'deleted_success'

const messages: Record<Locale, Record<ShelfTextKey, string>> = {
  'pt-BR': {
    all: 'Todos',
    read: 'Lidos',
    reading: 'Lendo',
    want: 'Quero ler',
    other: 'Outros',
    grid: 'Grade',
    list: 'Lista',
    spines: 'Lombadas',
    loading: 'Carregando sua estante…',
    error: 'Não foi possível carregar sua estante.',
    empty_title: 'Sua estante ainda está vazia',
    empty_copy: 'Registre uma leitura para começar a construir sua biblioteca pessoal.',
    empty_filtered: 'Nenhuma leitura corresponde a este filtro.',
    register: 'Buscar um livro',
    books_count: 'livros',
    status: 'Status',
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
    open_legacy: 'Abrir no app atual',
    no_review: 'Nenhum relato registrado para esta leitura.',
    edit_reading: 'Editar leitura',
    reading_date: 'Quando você leu',
    reading_date_placeholder: 'ex.: julho de 2026',
    review_placeholder: 'Escreva suas impressões sobre a leitura…',
    make_public: 'Tornar relato público',
    make_public_hint: 'O relato poderá aparecer no seu perfil e na comunidade.',
    mark_spoiler: 'Este relato contém spoiler',
    mark_spoiler_hint: 'O conteúdo será protegido por um aviso para outros leitores.',
    save_changes: 'Salvar alterações',
    saving: 'Salvando…',
    cancel: 'Cancelar',
    remove_reading: 'Remover da estante',
    remove_hint: 'A leitura e as entradas do diário vinculadas serão apagadas.',
    remove_confirmation: 'Esta ação é permanente. Confirme para remover a leitura e seu diário.',
    keep_reading: 'Manter leitura',
    confirm_remove: 'Confirmar remoção',
    remove: 'Remover',
    deleting: 'Removendo…',
    save_error: 'Não foi possível salvar as alterações.',
    delete_error: 'Não foi possível remover a leitura.',
    saved_success: 'Leitura atualizada.',
    deleted_success: 'Leitura removida da estante.',
  },
  en: {
    all: 'All',
    read: 'Read',
    reading: 'Reading',
    want: 'Want to read',
    other: 'Other',
    grid: 'Grid',
    list: 'List',
    spines: 'Spines',
    loading: 'Loading your shelf…',
    error: 'Your shelf could not be loaded.',
    empty_title: 'Your shelf is still empty',
    empty_copy: 'Log a reading to start building your personal library.',
    empty_filtered: 'No reading matches this filter.',
    register: 'Find a book',
    books_count: 'books',
    status: 'Status',
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
    open_legacy: 'Open in current app',
    no_review: 'No reading note was saved for this book.',
    edit_reading: 'Edit reading',
    reading_date: 'When you read it',
    reading_date_placeholder: 'e.g. July 2026',
    review_placeholder: 'Write your thoughts about this reading…',
    make_public: 'Make note public',
    make_public_hint: 'The note may appear on your profile and in the community.',
    mark_spoiler: 'This note contains spoilers',
    mark_spoiler_hint: 'The content will be hidden behind a warning for other readers.',
    save_changes: 'Save changes',
    saving: 'Saving…',
    cancel: 'Cancel',
    remove_reading: 'Remove from shelf',
    remove_hint: 'The reading and its linked journal entries will be deleted.',
    remove_confirmation: 'This action is permanent. Confirm to remove the reading and its journal.',
    keep_reading: 'Keep reading',
    confirm_remove: 'Confirm removal',
    remove: 'Remove',
    deleting: 'Removing…',
    save_error: 'The changes could not be saved.',
    delete_error: 'The reading could not be removed.',
    saved_success: 'Reading updated.',
    deleted_success: 'Reading removed from your shelf.',
  },
}

export function shelfText(locale: Locale, key: ShelfTextKey): string {
  return messages[locale][key]
}

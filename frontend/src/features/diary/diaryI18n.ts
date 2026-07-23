import type { Locale } from '../../i18n'

export type DiaryTextKey =
  | 'loading'
  | 'error'
  | 'new_entry'
  | 'all_books'
  | 'filter_book'
  | 'select_book'
  | 'no_readings'
  | 'empty_title'
  | 'empty_copy'
  | 'find_book'
  | 'entries'
  | 'create_title'
  | 'edit_title'
  | 'progress_type'
  | 'page'
  | 'percent'
  | 'chapter'
  | 'free'
  | 'page_label'
  | 'page_of'
  | 'total_pages'
  | 'total_pages_hint'
  | 'percent_label'
  | 'chapter_label'
  | 'chapter_placeholder'
  | 'chapter_page'
  | 'note'
  | 'note_placeholder'
  | 'make_public'
  | 'make_public_hint'
  | 'mark_spoiler'
  | 'mark_spoiler_hint'
  | 'save'
  | 'saving'
  | 'cancel'
  | 'edit'
  | 'remove'
  | 'confirm_remove'
  | 'keep'
  | 'removing'
  | 'validation_page'
  | 'validation_percent'
  | 'validation_chapter'
  | 'validation_note'
  | 'save_error'
  | 'delete_error'
  | 'created'
  | 'saved'
  | 'deleted'
  | 'private'
  | 'public'
  | 'spoiler'
  | 'estimated_page'
  | 'pages_advanced'
  | 'pages_returned'
  | 'origin_more'
  | 'no_note'
  | 'close_editor'

const messages: Record<Locale, Record<DiaryTextKey, string>> = {
  'pt-BR': {
    loading: 'Carregando seu diário…',
    error: 'Não foi possível carregar o diário.',
    new_entry: 'Nova entrada',
    all_books: 'Todos os livros',
    filter_book: 'Filtrar por livro',
    select_book: 'Escolha uma leitura',
    no_readings: 'Adicione um livro à estante antes de criar uma entrada.',
    empty_title: 'Seu diário ainda está em branco',
    empty_copy: 'Registre progresso, capítulos e impressões ao longo da leitura.',
    find_book: 'Buscar um livro',
    entries: 'entradas',
    create_title: 'Registrar no diário',
    edit_title: 'Editar entrada',
    progress_type: 'Tipo de registro',
    page: 'Página',
    percent: 'Porcentagem',
    chapter: 'Capítulo',
    free: 'Anotação livre',
    page_label: 'Página atual',
    page_of: 'de',
    total_pages: 'Total de páginas',
    total_pages_hint: 'Preencha uma vez para melhorar o cálculo de progresso.',
    percent_label: 'Progresso em porcentagem',
    chapter_label: 'Capítulo atual',
    chapter_placeholder: 'Digite ou escolha um capítulo',
    chapter_page: 'Página inicial do capítulo (opcional)',
    note: 'Anotação',
    note_placeholder: 'O que chamou sua atenção nesta leitura?',
    make_public: 'Tornar esta entrada pública',
    make_public_hint: 'A anotação poderá aparecer no seu perfil e na comunidade.',
    mark_spoiler: 'Esta entrada contém spoiler',
    mark_spoiler_hint: 'O conteúdo ficará protegido por um aviso.',
    save: 'Salvar entrada',
    saving: 'Salvando…',
    cancel: 'Cancelar',
    edit: 'Editar',
    remove: 'Remover',
    confirm_remove: 'Confirmar remoção',
    keep: 'Manter entrada',
    removing: 'Removendo…',
    validation_page: 'Informe uma página válida.',
    validation_percent: 'Informe uma porcentagem entre 0 e 100.',
    validation_chapter: 'Informe o capítulo atual.',
    validation_note: 'Escreva uma anotação.',
    save_error: 'Não foi possível salvar a entrada.',
    delete_error: 'Não foi possível remover a entrada.',
    created: 'Entrada adicionada ao diário.',
    saved: 'Entrada atualizada.',
    deleted: 'Entrada removida.',
    private: 'privada',
    public: 'pública',
    spoiler: 'spoiler',
    estimated_page: 'página estimada',
    pages_advanced: 'páginas avançadas',
    pages_returned: 'páginas retornadas',
    origin_more: 'registrado em “Li mais”',
    no_note: 'Sem anotação nesta entrada.',
    close_editor: 'Fechar editor',
  },
  en: {
    loading: 'Loading your journal…',
    error: 'Your journal could not be loaded.',
    new_entry: 'New entry',
    all_books: 'All books',
    filter_book: 'Filter by book',
    select_book: 'Choose a reading',
    no_readings: 'Add a book to your shelf before creating an entry.',
    empty_title: 'Your journal is still blank',
    empty_copy: 'Log progress, chapters and thoughts throughout your reading.',
    find_book: 'Find a book',
    entries: 'entries',
    create_title: 'Add to journal',
    edit_title: 'Edit entry',
    progress_type: 'Entry type',
    page: 'Page',
    percent: 'Percentage',
    chapter: 'Chapter',
    free: 'Free note',
    page_label: 'Current page',
    page_of: 'of',
    total_pages: 'Total pages',
    total_pages_hint: 'Fill this once to improve progress calculations.',
    percent_label: 'Progress percentage',
    chapter_label: 'Current chapter',
    chapter_placeholder: 'Type or choose a chapter',
    chapter_page: 'Chapter starting page (optional)',
    note: 'Note',
    note_placeholder: 'What stood out during this reading?',
    make_public: 'Make this entry public',
    make_public_hint: 'The note may appear on your profile and in the community.',
    mark_spoiler: 'This entry contains spoilers',
    mark_spoiler_hint: 'The content will be hidden behind a warning.',
    save: 'Save entry',
    saving: 'Saving…',
    cancel: 'Cancel',
    edit: 'Edit',
    remove: 'Remove',
    confirm_remove: 'Confirm removal',
    keep: 'Keep entry',
    removing: 'Removing…',
    validation_page: 'Enter a valid page.',
    validation_percent: 'Enter a percentage between 0 and 100.',
    validation_chapter: 'Enter the current chapter.',
    validation_note: 'Write a note.',
    save_error: 'The entry could not be saved.',
    delete_error: 'The entry could not be removed.',
    created: 'Entry added to your journal.',
    saved: 'Entry updated.',
    deleted: 'Entry removed.',
    private: 'private',
    public: 'public',
    spoiler: 'spoiler',
    estimated_page: 'estimated page',
    pages_advanced: 'pages advanced',
    pages_returned: 'pages returned',
    origin_more: 'logged through “Read more”',
    no_note: 'No note in this entry.',
    close_editor: 'Close editor',
  },
  es: {
    loading: 'Cargando tu diario…',
    error: 'No se pudo cargar tu diario.',
    new_entry: 'Nueva entrada',
    all_books: 'Todos los libros',
    filter_book: 'Filtrar por libro',
    select_book: 'Elige una lectura',
    no_readings: 'Añade un libro a tu estantería antes de crear una entrada.',
    empty_title: 'Tu diario aún está en blanco',
    empty_copy: 'Registra progreso, capítulos e ideas a lo largo de la lectura.',
    find_book: 'Buscar un libro',
    entries: 'entradas',
    create_title: 'Añadir al diario',
    edit_title: 'Editar entrada',
    progress_type: 'Tipo de entrada',
    page: 'Página',
    percent: 'Porcentaje',
    chapter: 'Capítulo',
    free: 'Nota libre',
    page_label: 'Página actual',
    page_of: 'de',
    total_pages: 'Total de páginas',
    total_pages_hint: 'Complétalo una vez para mejorar los cálculos de progreso.',
    percent_label: 'Porcentaje de progreso',
    chapter_label: 'Capítulo actual',
    chapter_placeholder: 'Escribe o elige un capítulo',
    chapter_page: 'Página inicial del capítulo (opcional)',
    note: 'Nota',
    note_placeholder: '¿Qué te llamó la atención en esta lectura?',
    make_public: 'Hacer pública esta entrada',
    make_public_hint: 'La nota podrá aparecer en tu perfil y en la comunidad.',
    mark_spoiler: 'Esta entrada contiene spoiler',
    mark_spoiler_hint: 'El contenido quedará protegido tras un aviso.',
    save: 'Guardar entrada',
    saving: 'Guardando…',
    cancel: 'Cancelar',
    edit: 'Editar',
    remove: 'Quitar',
    confirm_remove: 'Confirmar eliminación',
    keep: 'Mantener entrada',
    removing: 'Quitando…',
    validation_page: 'Ingresa una página válida.',
    validation_percent: 'Ingresa un porcentaje entre 0 y 100.',
    validation_chapter: 'Ingresa el capítulo actual.',
    validation_note: 'Escribe una nota.',
    save_error: 'No se pudo guardar la entrada.',
    delete_error: 'No se pudo quitar la entrada.',
    created: 'Entrada añadida a tu diario.',
    saved: 'Entrada actualizada.',
    deleted: 'Entrada quitada.',
    private: 'privada',
    public: 'pública',
    spoiler: 'spoiler',
    estimated_page: 'página estimada',
    pages_advanced: 'páginas avanzadas',
    pages_returned: 'páginas retrocedidas',
    origin_more: 'registrado con “Leer más”',
    no_note: 'Sin nota en esta entrada.',
    close_editor: 'Cerrar editor',
  },
}

export function diaryText(locale: Locale, key: DiaryTextKey): string {
  return messages[locale][key]
}

import type { Locale } from '../../i18n'

export type ManualTextKey =
  | 'cta_text'
  | 'cta_button'
  | 'title'
  | 'book_group'
  | 'edition_group'
  | 'work_title'
  | 'author'
  | 'work_year'
  | 'original_language'
  | 'edition_title'
  | 'publisher'
  | 'translator'
  | 'isbn'
  | 'language'
  | 'edition_year'
  | 'cover_url'
  | 'pages'
  | 'submit'
  | 'submitting'
  | 'cancel'
  | 'close'
  | 'required_error'
  | 'error'
  | 'success'
  | 'success_title'

const messages: Record<Locale, Record<ManualTextKey, string>> = {
  'pt-BR': {
    cta_text: 'Não encontrou o livro?',
    cta_button: 'Cadastrar manualmente',
    title: 'Cadastro manual',
    book_group: 'Livro',
    edition_group: 'Edição',
    work_title: 'Título da obra',
    author: 'Autor',
    work_year: 'Ano da obra',
    original_language: 'Idioma original',
    edition_title: 'Título da edição',
    publisher: 'Editora',
    translator: 'Tradução',
    isbn: 'ISBN',
    language: 'Idioma',
    edition_year: 'Ano da edição',
    cover_url: 'URL da capa',
    pages: 'Páginas',
    submit: 'Enviar para revisão',
    submitting: 'Enviando…',
    cancel: 'Cancelar',
    close: 'Fechar cadastro manual',
    required_error: 'Título e autor são obrigatórios.',
    error: 'Não consegui enviar o cadastro agora.',
    success: 'Cadastro enviado para revisão. Se aprovado, aparecerá na Lombada.',
    success_title: 'Recebido!',
  },
  en: {
    cta_text: "Didn't find the book?",
    cta_button: 'Add manually',
    title: 'Manual entry',
    book_group: 'Book',
    edition_group: 'Edition',
    work_title: 'Work title',
    author: 'Author',
    work_year: 'Work year',
    original_language: 'Original language',
    edition_title: 'Edition title',
    publisher: 'Publisher',
    translator: 'Translation',
    isbn: 'ISBN',
    language: 'Language',
    edition_year: 'Edition year',
    cover_url: 'Cover URL',
    pages: 'Pages',
    submit: 'Submit for review',
    submitting: 'Submitting…',
    cancel: 'Cancel',
    close: 'Close manual entry',
    required_error: 'Title and author are required.',
    error: "I couldn't submit the entry right now.",
    success: 'Entry submitted for review. If approved, it will appear on Lombada.',
    success_title: 'Received!',
  },
  es: {
    cta_text: '¿No encontraste el libro?',
    cta_button: 'Registrar manualmente',
    title: 'Registro manual',
    book_group: 'Libro',
    edition_group: 'Edición',
    work_title: 'Título de la obra',
    author: 'Autor',
    work_year: 'Año de la obra',
    original_language: 'Idioma original',
    edition_title: 'Título de la edición',
    publisher: 'Editorial',
    translator: 'Traducción',
    isbn: 'ISBN',
    language: 'Idioma',
    edition_year: 'Año de la edición',
    cover_url: 'URL de la portada',
    pages: 'Páginas',
    submit: 'Enviar para revisión',
    submitting: 'Enviando…',
    cancel: 'Cancelar',
    close: 'Cerrar registro manual',
    required_error: 'El título y el autor son obligatorios.',
    error: 'No pude enviar el registro ahora.',
    success: 'Registro enviado para revisión. Si se aprueba, aparecerá en Lombada.',
    success_title: '¡Recibido!',
  },
}

export function manualText(locale: Locale, key: ManualTextKey): string {
  return messages[locale][key]
}

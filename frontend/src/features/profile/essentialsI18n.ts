import type { Locale } from '../../i18n'

export type EssentialsTextKey =
  | 'label'
  | 'title'
  | 'hint'
  | 'empty'
  | 'choose'
  | 'edit'
  | 'editor_title'
  | 'editor_hint'
  | 'selected'
  | 'shelf'
  | 'save'
  | 'saving'
  | 'cancel'
  | 'no_shelf'
  | 'save_error'
  | 'close'
  | 'position'

const messages: Record<Locale, Record<EssentialsTextKey, string>> = {
  'pt-BR': {
    label: 'identidade literária',
    title: 'Quatro essenciais',
    hint: 'Até quatro livros da sua estante que dizem algo sobre você como leitor.',
    empty: 'Seu retrato literário começa com um livro.',
    choose: 'Escolher meus essenciais',
    edit: 'Editar essenciais',
    editor_title: 'Escolha seus essenciais',
    editor_hint: 'Toque para adicionar ou remover. A ordem segue a escolha; até quatro.',
    selected: 'Selecionados',
    shelf: 'Sua estante',
    save: 'Salvar essenciais',
    saving: 'Salvando…',
    cancel: 'Cancelar',
    no_shelf: 'Adicione livros à estante antes de escolher seus essenciais.',
    save_error: 'Não consegui salvar seus essenciais agora.',
    close: 'Fechar editor de essenciais',
    position: 'Posição {n}',
  },
  en: {
    label: 'literary identity',
    title: 'Four essentials',
    hint: 'Up to four books from your shelf that say something about you as a reader.',
    empty: 'Your literary portrait starts with one book.',
    choose: 'Choose my essentials',
    edit: 'Edit essentials',
    editor_title: 'Choose your essentials',
    editor_hint: 'Tap to add or remove. Order follows your picks; up to four.',
    selected: 'Selected',
    shelf: 'Your shelf',
    save: 'Save essentials',
    saving: 'Saving…',
    cancel: 'Cancel',
    no_shelf: 'Add books to your shelf before choosing essentials.',
    save_error: "I couldn't save your essentials right now.",
    close: 'Close essentials editor',
    position: 'Position {n}',
  },
  es: {
    label: 'identidad literaria',
    title: 'Cuatro esenciales',
    hint: 'Hasta cuatro libros de tu estantería que dicen algo sobre ti como lector.',
    empty: 'Tu retrato literario empieza con un libro.',
    choose: 'Elegir mis esenciales',
    edit: 'Editar esenciales',
    editor_title: 'Elige tus esenciales',
    editor_hint: 'Toca para añadir o quitar. El orden sigue tu elección; hasta cuatro.',
    selected: 'Seleccionados',
    shelf: 'Tu estantería',
    save: 'Guardar esenciales',
    saving: 'Guardando…',
    cancel: 'Cancelar',
    no_shelf: 'Añade libros a tu estantería antes de elegir tus esenciales.',
    save_error: 'No pude guardar tus esenciales ahora.',
    close: 'Cerrar editor de esenciales',
    position: 'Posición {n}',
  },
}

export function essentialsText(locale: Locale, key: EssentialsTextKey): string {
  return messages[locale][key]
}

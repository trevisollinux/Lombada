import type { Locale } from '../../i18n'

export type ProfileTextKey =
  | 'my_profile'
  | 'public_profile'
  | 'edit_profile'
  | 'save_profile'
  | 'cancel'
  | 'name'
  | 'handle'
  | 'bio'
  | 'bio_hint'
  | 'profile_saved'
  | 'avatar_change'
  | 'avatar_remove'
  | 'avatar_processing'
  | 'avatar_hint'
  | 'followers'
  | 'following'
  | 'books'
  | 'read'
  | 'reading'
  | 'want_to_read'
  | 'average_rating'
  | 'owned_editions'
  | 'wanted_editions'
  | 'shelf'
  | 'reviews'
  | 'texts'
  | 'favorites'
  | 'reading_now'
  | 'all_statuses'
  | 'empty_shelf'
  | 'empty_reviews'
  | 'empty_texts'
  | 'spoiler'
  | 'show_spoiler'
  | 'hide_spoiler'
  | 'open_work'
  | 'manage_texts'
  | 'new_text'
  | 'edit_text'
  | 'text_title'
  | 'text_content'
  | 'text_work'
  | 'text_no_work'
  | 'text_public'
  | 'text_private'
  | 'save_text'
  | 'delete_text'
  | 'confirm_delete_text'
  | 'text_saved'
  | 'people_loading'
  | 'people_empty'
  | 'close'
  | 'follow'
  | 'following_action'
  | 'login_to_edit'
  | 'login_to_interact'
  | 'profile_not_found'
  | 'profile_error'
  | 'retry'
  | 'legacy_profile'
  | 'account_anonymous'
  | 'account_google'
  | 'public'
  | 'private'

const messages: Record<Locale, Record<ProfileTextKey, string>> = {
  'pt-BR': {
    my_profile: 'Meu perfil',
    public_profile: 'Perfil público',
    edit_profile: 'Editar perfil',
    save_profile: 'Salvar perfil',
    cancel: 'Cancelar',
    name: 'Nome exibido',
    handle: 'Nome de usuário',
    bio: 'Bio curta',
    bio_hint: 'Até 160 caracteres. Evite informações pessoais sensíveis.',
    profile_saved: 'Perfil atualizado.',
    avatar_change: 'Trocar foto',
    avatar_remove: 'Remover foto',
    avatar_processing: 'Preparando imagem…',
    avatar_hint: 'A imagem será recortada ao centro e comprimida antes do envio.',
    followers: 'Seguidores',
    following: 'Seguindo',
    books: 'livros',
    read: 'lidos',
    reading: 'lendo',
    want_to_read: 'quero ler',
    average_rating: 'média',
    owned_editions: 'edições na coleção',
    wanted_editions: 'edições desejadas',
    shelf: 'Estante',
    reviews: 'Críticas',
    texts: 'Textos',
    favorites: 'Favoritos',
    reading_now: 'Lendo agora',
    all_statuses: 'Todos',
    empty_shelf: 'Nenhum livro nesta parte da estante.',
    empty_reviews: 'Nenhuma crítica pública por aqui.',
    empty_texts: 'Nenhum texto publicado por aqui.',
    spoiler: 'Contém spoiler',
    show_spoiler: 'Mostrar crítica',
    hide_spoiler: 'Ocultar crítica',
    open_work: 'Abrir obra',
    manage_texts: 'Gerenciar textos',
    new_text: 'Novo texto',
    edit_text: 'Editar texto',
    text_title: 'Título',
    text_content: 'Texto',
    text_work: 'Obra relacionada',
    text_no_work: 'Sem obra relacionada',
    text_public: 'Público',
    text_private: 'Privado',
    save_text: 'Salvar texto',
    delete_text: 'Excluir texto',
    confirm_delete_text: 'Toque novamente para confirmar a exclusão.',
    text_saved: 'Texto salvo.',
    people_loading: 'Carregando leitores…',
    people_empty: 'Nenhum leitor nesta lista.',
    close: 'Fechar',
    follow: 'Seguir',
    following_action: 'Seguindo',
    login_to_edit: 'Entre com Google para editar seu perfil e publicar textos.',
    login_to_interact: 'Entre com Google para seguir leitores.',
    profile_not_found: 'Este perfil não foi encontrado.',
    profile_error: 'Não foi possível carregar o perfil agora.',
    retry: 'Tentar novamente',
    legacy_profile: 'Ver perfil público',
    account_anonymous: 'Conta anônima',
    account_google: 'Conta Google',
    public: 'público',
    private: 'privado',
  },
  en: {
    my_profile: 'My profile',
    public_profile: 'Public profile',
    edit_profile: 'Edit profile',
    save_profile: 'Save profile',
    cancel: 'Cancel',
    name: 'Display name',
    handle: 'Username',
    bio: 'Short bio',
    bio_hint: 'Up to 160 characters. Avoid sensitive personal information.',
    profile_saved: 'Profile updated.',
    avatar_change: 'Change photo',
    avatar_remove: 'Remove photo',
    avatar_processing: 'Preparing image…',
    avatar_hint: 'The image will be center-cropped and compressed before upload.',
    followers: 'Followers',
    following: 'Following',
    books: 'books',
    read: 'read',
    reading: 'reading',
    want_to_read: 'want to read',
    average_rating: 'average',
    owned_editions: 'editions owned',
    wanted_editions: 'wanted editions',
    shelf: 'Shelf',
    reviews: 'Reviews',
    texts: 'Texts',
    favorites: 'Favorites',
    reading_now: 'Reading now',
    all_statuses: 'All',
    empty_shelf: 'No books in this part of the shelf.',
    empty_reviews: 'No public reviews here yet.',
    empty_texts: 'No published texts here yet.',
    spoiler: 'Contains spoilers',
    show_spoiler: 'Show review',
    hide_spoiler: 'Hide review',
    open_work: 'Open work',
    manage_texts: 'Manage texts',
    new_text: 'New text',
    edit_text: 'Edit text',
    text_title: 'Title',
    text_content: 'Text',
    text_work: 'Related work',
    text_no_work: 'No related work',
    text_public: 'Public',
    text_private: 'Private',
    save_text: 'Save text',
    delete_text: 'Delete text',
    confirm_delete_text: 'Tap again to confirm deletion.',
    text_saved: 'Text saved.',
    people_loading: 'Loading readers…',
    people_empty: 'No readers in this list.',
    close: 'Close',
    follow: 'Follow',
    following_action: 'Following',
    login_to_edit: 'Sign in with Google to edit your profile and publish texts.',
    login_to_interact: 'Sign in with Google to follow readers.',
    profile_not_found: 'This profile was not found.',
    profile_error: 'The profile could not be loaded right now.',
    retry: 'Try again',
    legacy_profile: 'View public profile',
    account_anonymous: 'Anonymous account',
    account_google: 'Google account',
    public: 'public',
    private: 'private',
  },
  es: {
    my_profile: 'Mi perfil',
    public_profile: 'Perfil público',
    edit_profile: 'Editar perfil',
    save_profile: 'Guardar perfil',
    cancel: 'Cancelar',
    name: 'Nombre visible',
    handle: 'Nombre de usuario',
    bio: 'Biografía breve',
    bio_hint: 'Hasta 160 caracteres. Evita información personal sensible.',
    profile_saved: 'Perfil actualizado.',
    avatar_change: 'Cambiar foto',
    avatar_remove: 'Quitar foto',
    avatar_processing: 'Preparando imagen…',
    avatar_hint: 'La imagen se recortará al centro y se comprimirá antes de subirla.',
    followers: 'Seguidores',
    following: 'Siguiendo',
    books: 'libros',
    read: 'leídos',
    reading: 'leyendo',
    want_to_read: 'quiere leer',
    average_rating: 'media',
    owned_editions: 'ediciones en la colección',
    wanted_editions: 'ediciones deseadas',
    shelf: 'Estantería',
    reviews: 'Reseñas',
    texts: 'Textos',
    favorites: 'Favoritos',
    reading_now: 'Leyendo ahora',
    all_statuses: 'Todos',
    empty_shelf: 'No hay libros en esta parte de la estantería.',
    empty_reviews: 'Aún no hay reseñas públicas aquí.',
    empty_texts: 'Aún no hay textos publicados aquí.',
    spoiler: 'Contiene spoilers',
    show_spoiler: 'Mostrar reseña',
    hide_spoiler: 'Ocultar reseña',
    open_work: 'Abrir obra',
    manage_texts: 'Gestionar textos',
    new_text: 'Nuevo texto',
    edit_text: 'Editar texto',
    text_title: 'Título',
    text_content: 'Texto',
    text_work: 'Obra relacionada',
    text_no_work: 'Sin obra relacionada',
    text_public: 'Público',
    text_private: 'Privado',
    save_text: 'Guardar texto',
    delete_text: 'Eliminar texto',
    confirm_delete_text: 'Toca de nuevo para confirmar la eliminación.',
    text_saved: 'Texto guardado.',
    people_loading: 'Cargando lectores…',
    people_empty: 'No hay lectores en esta lista.',
    close: 'Cerrar',
    follow: 'Seguir',
    following_action: 'Siguiendo',
    login_to_edit: 'Entra con Google para editar tu perfil y publicar textos.',
    login_to_interact: 'Entra con Google para seguir lectores.',
    profile_not_found: 'No se encontró este perfil.',
    profile_error: 'No se pudo cargar el perfil ahora.',
    retry: 'Reintentar',
    legacy_profile: 'Ver perfil público',
    account_anonymous: 'Cuenta anónima',
    account_google: 'Cuenta Google',
    public: 'público',
    private: 'privado',
  },
}

export function profileText(locale: Locale, key: ProfileTextKey): string {
  return messages[locale][key]
}

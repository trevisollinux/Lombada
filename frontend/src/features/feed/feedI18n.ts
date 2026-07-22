import type { Locale } from '../../i18n'

export type FeedTextKey =
  | 'following'
  | 'discover'
  | 'reading_now'
  | 'reader_suggestions'
  | 'follow'
  | 'following_action'
  | 'unfollow'
  | 'like'
  | 'save'
  | 'saved'
  | 'comments'
  | 'comment_placeholder'
  | 'comment_send'
  | 'comment_delete'
  | 'comment_empty'
  | 'comment_loading'
  | 'login_required'
  | 'own_review'
  | 'report'
  | 'reported'
  | 'report_confirm'
  | 'spoiler'
  | 'reveal_spoiler'
  | 'hide_spoiler'
  | 'loading'
  | 'error'
  | 'empty_following'
  | 'empty_following_copy'
  | 'empty_discover'
  | 'empty_discover_copy'
  | 'refresh'
  | 'reviews'
  | 'followers'
  | 'wrote_review'
  | 'started_reading'
  | 'finished_reading'
  | 'wants_to_read'
  | 'created_reading'
  | 'wrote_text'
  | 'edition'
  | 'rating'
  | 'open_book'
  | 'open_profile'
  | 'sign_in'

const messages: Record<Locale, Record<FeedTextKey, string>> = {
  'pt-BR': {
    following: 'Seguindo',
    discover: 'Descobrir',
    reading_now: 'Lendo agora',
    reader_suggestions: 'Leitores para acompanhar',
    follow: 'Seguir',
    following_action: 'Seguindo',
    unfollow: 'Deixar de seguir',
    like: 'Curtir',
    save: 'Salvar',
    saved: 'Salvo',
    comments: 'Comentários',
    comment_placeholder: 'Escreva um comentário…',
    comment_send: 'Comentar',
    comment_delete: 'Excluir',
    comment_empty: 'Ainda não há comentários.',
    comment_loading: 'Carregando comentários…',
    login_required: 'Entre com Google para interagir com a comunidade.',
    own_review: 'Esta crítica é sua.',
    report: 'Denunciar',
    reported: 'Denunciado',
    report_confirm: 'Denunciar esta crítica para análise?',
    spoiler: 'Contém spoiler',
    reveal_spoiler: 'Mostrar crítica',
    hide_spoiler: 'Ocultar crítica',
    loading: 'Carregando atividade…',
    error: 'Não foi possível carregar o feed.',
    empty_following: 'Seu feed ainda está silencioso',
    empty_following_copy: 'Acompanhe leitores na aba Descobrir para ver leituras, críticas e textos aqui.',
    empty_discover: 'Ainda não há atividade pública',
    empty_discover_copy: 'Quando leitores publicarem críticas e textos, eles aparecerão aqui.',
    refresh: 'Tentar novamente',
    reviews: 'críticas',
    followers: 'seguidores',
    wrote_review: 'publicou uma crítica',
    started_reading: 'começou a ler',
    finished_reading: 'terminou de ler',
    wants_to_read: 'quer ler',
    created_reading: 'adicionou à estante',
    wrote_text: 'publicou um texto',
    edition: 'edição',
    rating: 'nota',
    open_book: 'Abrir obra',
    open_profile: 'Abrir perfil',
    sign_in: 'Entrar com Google',
  },
  en: {
    following: 'Following',
    discover: 'Discover',
    reading_now: 'Reading now',
    reader_suggestions: 'Readers to follow',
    follow: 'Follow',
    following_action: 'Following',
    unfollow: 'Unfollow',
    like: 'Like',
    save: 'Save',
    saved: 'Saved',
    comments: 'Comments',
    comment_placeholder: 'Write a comment…',
    comment_send: 'Comment',
    comment_delete: 'Delete',
    comment_empty: 'No comments yet.',
    comment_loading: 'Loading comments…',
    login_required: 'Sign in with Google to interact with the community.',
    own_review: 'This is your review.',
    report: 'Report',
    reported: 'Reported',
    report_confirm: 'Report this review for moderation?',
    spoiler: 'Contains spoilers',
    reveal_spoiler: 'Show review',
    hide_spoiler: 'Hide review',
    loading: 'Loading activity…',
    error: 'The feed could not be loaded.',
    empty_following: 'Your feed is still quiet',
    empty_following_copy: 'Follow readers in Discover to see readings, reviews and texts here.',
    empty_discover: 'There is no public activity yet',
    empty_discover_copy: 'When readers publish reviews and texts, they will appear here.',
    refresh: 'Try again',
    reviews: 'reviews',
    followers: 'followers',
    wrote_review: 'published a review',
    started_reading: 'started reading',
    finished_reading: 'finished reading',
    wants_to_read: 'wants to read',
    created_reading: 'added to the shelf',
    wrote_text: 'published a text',
    edition: 'edition',
    rating: 'rating',
    open_book: 'Open work',
    open_profile: 'Open profile',
    sign_in: 'Sign in with Google',
  },
  es: {
    following: 'Siguiendo',
    discover: 'Descubrir',
    reading_now: 'Leyendo ahora',
    reader_suggestions: 'Lectores para seguir',
    follow: 'Seguir',
    following_action: 'Siguiendo',
    unfollow: 'Dejar de seguir',
    like: 'Me gusta',
    save: 'Guardar',
    saved: 'Guardado',
    comments: 'Comentarios',
    comment_placeholder: 'Escribe un comentario…',
    comment_send: 'Comentar',
    comment_delete: 'Eliminar',
    comment_empty: 'Aún no hay comentarios.',
    comment_loading: 'Cargando comentarios…',
    login_required: 'Entra con Google para interactuar con la comunidad.',
    own_review: 'Esta es tu reseña.',
    report: 'Denunciar',
    reported: 'Denunciada',
    report_confirm: '¿Denunciar esta reseña para moderación?',
    spoiler: 'Contiene spoilers',
    reveal_spoiler: 'Mostrar reseña',
    hide_spoiler: 'Ocultar reseña',
    loading: 'Cargando actividad…',
    error: 'No se pudo cargar el feed.',
    empty_following: 'Tu feed aún está tranquilo',
    empty_following_copy: 'Sigue lectores en Descubrir para ver lecturas, reseñas y textos aquí.',
    empty_discover: 'Aún no hay actividad pública',
    empty_discover_copy: 'Cuando los lectores publiquen reseñas y textos, aparecerán aquí.',
    refresh: 'Reintentar',
    reviews: 'reseñas',
    followers: 'seguidores',
    wrote_review: 'publicó una reseña',
    started_reading: 'empezó a leer',
    finished_reading: 'terminó de leer',
    wants_to_read: 'quiere leer',
    created_reading: 'añadió a la estantería',
    wrote_text: 'publicó un texto',
    edition: 'edición',
    rating: 'nota',
    open_book: 'Abrir obra',
    open_profile: 'Abrir perfil',
    sign_in: 'Entrar con Google',
  },
}

export function feedText(locale: Locale, key: FeedTextKey): string {
  return messages[locale][key]
}

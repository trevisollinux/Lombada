import type { Locale } from '../../i18n'

export type ProgressTextKey =
  | 'continue_reading'
  | 'continue_copy'
  | 'log_more'
  | 'open_diary'
  | 'sessions'
  | 'pages_last_week'
  | 'page_of'
  | 'percent_complete'
  | 'remaining'
  | 'forecast'
  | 'days'
  | 'quick_title'
  | 'quick_copy'
  | 'page'
  | 'percentage'
  | 'current_page'
  | 'current_percentage'
  | 'save'
  | 'saving'
  | 'cancel'
  | 'success_delta'
  | 'success_page'
  | 'success_percent'
  | 'validation_page'
  | 'validation_percent'
  | 'load_error'
  | 'save_error'
  | 'onboarding_eyebrow'
  | 'onboarding_title'
  | 'onboarding_copy'
  | 'onboarding_cta'
  | 'onboarding_missing'
  | 'onboarding_close'

const messages: Record<Locale, Record<ProgressTextKey, string>> = {
  'pt-BR': {
    continue_reading: 'Continue sua leitura',
    continue_copy: 'Um registro rápido mantém viva a memória da leitura, sem interromper o livro.',
    log_more: 'Li mais',
    open_diary: 'Abrir diário completo',
    sessions: 'sessões',
    pages_last_week: 'páginas nos últimos 7 dias',
    page_of: 'página {current} de {total}',
    percent_complete: '{value}% concluído',
    remaining: '{value} páginas restantes',
    forecast: 'ritmo atual: cerca de {value} dias',
    days: 'dias',
    quick_title: 'Até onde você chegou?',
    quick_copy: 'Registre só o ponto atual. Anotações, capítulos e privacidade continuam no diário completo.',
    page: 'Página',
    percentage: 'Porcentagem',
    current_page: 'Página atual',
    current_percentage: 'Porcentagem atual',
    save: 'Registrar progresso',
    saving: 'Registrando…',
    cancel: 'Cancelar',
    success_delta: '+{value} páginas nesta sessão',
    success_page: 'Leitura registrada na página {value}',
    success_percent: 'Leitura registrada em {value}%',
    validation_page: 'Informe uma página válida.',
    validation_percent: 'Informe uma porcentagem entre 0 e 100.',
    load_error: 'Não foi possível carregar o resumo desta leitura.',
    save_error: 'Não foi possível registrar o progresso.',
    onboarding_eyebrow: 'Seu primeiro valor no Lombada',
    onboarding_title: 'Qual livro está com você agora?',
    onboarding_copy: 'Encontre o livro, adicione como Lendo e volte depois para registrar até onde chegou.',
    onboarding_cta: 'Buscar meu livro atual',
    onboarding_missing: 'Meu livro não está no catálogo',
    onboarding_close: 'Agora não',
  },
  en: {
    continue_reading: 'Continue reading',
    continue_copy: 'A quick entry keeps the reading memory alive without interrupting the book.',
    log_more: 'Read more',
    open_diary: 'Open full diary',
    sessions: 'sessions',
    pages_last_week: 'pages in the last 7 days',
    page_of: 'page {current} of {total}',
    percent_complete: '{value}% complete',
    remaining: '{value} pages remaining',
    forecast: 'current pace: about {value} days',
    days: 'days',
    quick_title: 'How far did you get?',
    quick_copy: 'Record only your current position. Notes, chapters and privacy remain in the full diary.',
    page: 'Page',
    percentage: 'Percentage',
    current_page: 'Current page',
    current_percentage: 'Current percentage',
    save: 'Log progress',
    saving: 'Logging…',
    cancel: 'Cancel',
    success_delta: '+{value} pages in this session',
    success_page: 'Reading logged at page {value}',
    success_percent: 'Reading logged at {value}%',
    validation_page: 'Enter a valid page.',
    validation_percent: 'Enter a percentage between 0 and 100.',
    load_error: 'This reading summary could not be loaded.',
    save_error: 'Progress could not be logged.',
    onboarding_eyebrow: 'Your first value in Lombada',
    onboarding_title: 'Which book is with you now?',
    onboarding_copy: 'Find the book, add it as Reading and return later to log how far you got.',
    onboarding_cta: 'Find my current book',
    onboarding_missing: 'My book is not in the catalog',
    onboarding_close: 'Not now',
  },
  es: {
    continue_reading: 'Seguir leyendo',
    continue_copy: 'Una nota rápida mantiene viva la memoria de lectura sin interrumpir el libro.',
    log_more: 'Leer más',
    open_diary: 'Abrir diario completo',
    sessions: 'sesiones',
    pages_last_week: 'páginas en los últimos 7 días',
    page_of: 'página {current} de {total}',
    percent_complete: '{value}% completado',
    remaining: '{value} páginas restantes',
    forecast: 'ritmo actual: unos {value} días',
    days: 'días',
    quick_title: '¿Hasta dónde llegaste?',
    quick_copy: 'Registra solo tu posición actual. Las notas, capítulos y privacidad siguen en el diario completo.',
    page: 'Página',
    percentage: 'Porcentaje',
    current_page: 'Página actual',
    current_percentage: 'Porcentaje actual',
    save: 'Registrar progreso',
    saving: 'Registrando…',
    cancel: 'Cancelar',
    success_delta: '+{value} páginas en esta sesión',
    success_page: 'Lectura registrada en la página {value}',
    success_percent: 'Lectura registrada al {value}%',
    validation_page: 'Ingresa una página válida.',
    validation_percent: 'Ingresa un porcentaje entre 0 y 100.',
    load_error: 'No se pudo cargar este resumen de lectura.',
    save_error: 'No se pudo registrar el progreso.',
    onboarding_eyebrow: 'Tu primer valor en Lombada',
    onboarding_title: '¿Qué libro te acompaña ahora?',
    onboarding_copy: 'Busca el libro, añádelo como Leyendo y vuelve luego para registrar hasta dónde llegaste.',
    onboarding_cta: 'Buscar mi libro actual',
    onboarding_missing: 'Mi libro no está en el catálogo',
    onboarding_close: 'Ahora no',
  },
}

export function progressText(locale: Locale, key: ProgressTextKey, values: Record<string, string | number> = {}): string {
  return Object.entries(values).reduce(
    (text, [name, value]) => text.replace(`{${name}}`, String(value)),
    messages[locale][key],
  )
}

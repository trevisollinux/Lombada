const DEFAULT_LOCALE = 'pt-BR';
const LOCALE_KEY = 'lombada_locale';

const I18N = {
  'pt-BR': {
    app_description: 'Registre o que leu, com qual edição e tradução. Tipo Letterboxd, mas pra livros.',
    app_title: 'Lombada — diário de leituras',
    crumb_reading_diary: 'diário de leitura',
    nav_search: 'buscar',
    nav_shelf: 'estante',
    nav_diary: 'diário',
    nav_profile: 'perfil',
    search_placeholder: 'título, autor ou ISBN…',
    search_button: 'buscar',
    home_label: 'um diário de leituras',
    home_title_html: 'o que você<br>está lendo<span class="q">?</span>',
    popular_works_label: 'explore · obras populares',
    shelf_title: 'Estante',
    share: 'compartilhar',
    diary_title: 'Diário',
    diary_subtitle: 'seus relatos de leitura',
    close_detail: 'fechar detalhe',
    share_card: 'compartilhar card',
    edit_reading: 'editar leitura',
    remove: 'remover',
    reading_now: 'lendo agora',
    continue_reading: 'Continue sua leitura',
    see_shelf: 'ver estante →',
    percent_done: '{count}% concluído',
    searching: 'buscando',
    manual_prominent_text: 'Não encontramos uma edição boa para essa busca.',
    manual_prominent_button: 'Cadastrar livro manualmente',
    manual_cta_text: 'Não encontrou o livro?',
    manual_cta_button: 'Cadastrar manualmente',
    no_connection: 'sem conexão. tenta de novo.',
    works_found: 'obras encontradas',
    edition_found_one: '{count} edição encontrada',
    edition_found_many: '{count} edições encontradas',
    see_editions: 'ver edições',
    back_results: '‹ resultados',
    work_not_found: 'não encontrei essa obra. tente buscar de novo.',
    loading_editions: 'carregando edições…',
    editions_load_error: 'não consegui carregar as edições.',
    no_average: 'sem média',
    no_rating: 'sem nota',
    community_reviews: 'Críticas da comunidade',
    no_public_reviews_html: 'Ainda não há críticas públicas para esta obra.<br>Seja a primeira pessoa a registrar uma leitura.',
    register_my_reading: 'Registrar minha leitura',
    featured: 'mais destacadas',
    recent: 'recentes',
    choose_edition_to_register: 'escolha uma edição para registrar sua leitura',
    no_editions: 'sem edições listadas.',
    no_average_yet: 'sem média ainda',
    reading_one: '{count} leitura',
    reading_many: '{count} leituras',
    review_one: '{count} crítica',
    review_many: '{count} críticas',
    work: 'obra',
    register_reading: 'Registrar leitura',
    register_edition_manually: 'Cadastrar edição manualmente',
    see_my_reading: 'Ver minha leitura',
    most_read: 'mais lida',
    portuguese_brazil: 'português/Brasil',
    other_editions: 'outras edições',
    translator_missing: 'tradutor não informado',
    publisher_missing: 'editora não informada',
    add_this_edition: 'Adicionar esta edição',
    community_average: 'média da comunidade',
    public_reviews: 'críticas públicas',
    editions: 'Edições',
    back_editions: '‹ edições',
    selected_edition: 'Edição escolhida',
    catalog_data_missing: 'dados catalográficos não informados',
    catalog_data_notice: 'Dados de livro, edição, capa, editora, tradutor, ISBN, idioma e ano fazem parte do catálogo e não podem ser alterados no registro da leitura.',
    your_rating: 'sua nota',
    status: 'status',
    when: 'quando',
    date_placeholder: 'ex: jun 2026',
    reading_note: 'relato',
    reading_note_placeholder: 'o que ficou dessa leitura…',
    save_to_shelf: 'salvar na estante',
    save_error: 'não consegui salvar. tenta de novo.',
    saved_to_shelf: 'salvo na sua estante',
    manual_registration: 'cadastro manual',
    book: 'livro',
    work_title_required: 'título da obra *',
    author_required: 'autor *',
    work_year: 'ano da obra',
    original_language: 'idioma original',
    edition: 'edição',
    edition_title: 'título da edição',
    publisher: 'editora',
    translator: 'tradutor(a)',
    edition_year: 'ano da edição',
    cover_url: 'URL da capa',
    your_reading: 'sua leitura',
    date: 'data',
    rating: 'nota',
    submit_for_review: 'enviar para revisão',
    required_title_author: 'título e autor são obrigatórios.',
    manual_success: 'Cadastro enviado para revisão. Se aprovado, aparecerá na Lombada.',
    shelf_empty_html: 'sua estante ainda está vazia.<br>busque um livro, escolha a edição e registre sua primeira leitura.',
    search_first_book: 'buscar meu primeiro livro →',
    filter_shelf_status: 'filtrar estante por status',
    shelf_view: 'visualização da estante',
    view_grid: 'grade',
    view_list: 'lista',
    filter_all: 'Todos',
    status_read: 'Lido',
    status_reading: 'Lendo',
    status_want: 'Quero ler',
    book_count_one: '{count} livro',
    book_count_many: '{count} livros',
    shelf_summary: '{total} · {read} lidos · {reading} lendo · {want} quero ler',
    shelf_filter_empty: 'nenhum livro em “{filter}” por enquanto.',
    diary_empty_html: 'seu diário começa quando você registra uma leitura.<br>adicione nota, status ou relato para lembrar do que ficou.',
    account: 'conta',
    account_connected: 'sua estante está vinculada ao Google',
    logout: 'sair',
    account_anon: 'você está usando a Lombada sem conta',
    account_login_hint: 'entre com Google para guardar sua estante e recuperá-la depois',
    login_google: 'entrar com Google',
    lombada_reader: 'Leitor Lombada',
    appearance: 'aparência',
    appearance_hint: 'escolha como a Lombada aparece neste dispositivo',
    theme: 'tema',
    theme_light: 'Claro',
    theme_dark: 'Escuro',
    language: 'Idioma',
    language_hint: 'escolha o idioma da interface neste dispositivo',
    language_pt_br: 'Português (Brasil)',
    language_en: 'English',
    language_es: 'Español',
    library: 'biblioteca',
    library_hint: 'adicione uma obra que não apareceu na busca',
    share_shelf: 'compartilhar estante',
    open_public_shelf: 'abrir estante pública',
    duplicate_book: 'Este livro já está na sua estante.',
    account_connected_success: 'conta conectada com sucesso',
    account_connected_error: 'não foi possível conectar sua conta',
    login_saved_hint: 'sua leitura foi salva. conecte o Google para não perder sua estante.',
    login_hint: 'conecte o Google para não perder sua estante.',
    connect_google: 'conectar Google',
    continue_without_account: 'continuar sem conta'
  },
  'en': {
    nav_search: 'search', nav_shelf: 'shelf', nav_diary: 'diary', nav_profile: 'profile', search_placeholder: 'title, author or ISBN…', search_button: 'search', shelf_title: 'Shelf', diary_title: 'Diary', appearance: 'Appearance', theme_light: 'Light', theme_dark: 'Dark', language: 'Language', language_pt_br: 'Português (Brasil)', language_en: 'English', language_es: 'Español'
  },
  'es': {
    nav_search: 'buscar', nav_shelf: 'estantería', nav_diary: 'diario', nav_profile: 'perfil', search_placeholder: 'título, autor o ISBN…', search_button: 'buscar', shelf_title: 'Estantería', diary_title: 'Diario', appearance: 'Apariencia', theme_light: 'Claro', theme_dark: 'Oscuro', language: 'Idioma', language_pt_br: 'Português (Brasil)', language_en: 'English', language_es: 'Español'
  }
};

function getLocale(){
  const saved = localStorage.getItem(LOCALE_KEY);
  return I18N[saved] ? saved : DEFAULT_LOCALE;
}
function setLocale(locale){
  const next = I18N[locale] ? locale : DEFAULT_LOCALE;
  localStorage.setItem(LOCALE_KEY, next);
  document.documentElement.lang = next;
  applyI18n();
}
function t(key, vars = {}){
  const locale = getLocale();
  const dict = I18N[locale] || I18N[DEFAULT_LOCALE];
  let text = dict[key] || I18N[DEFAULT_LOCALE][key] || key;
  Object.entries(vars).forEach(([k, v]) => {
    text = text.replaceAll(`{${k}}`, v);
  });
  return text;
}
function plural(count, oneKey, manyKey){
  return t(count === 1 ? oneKey : manyKey, { count });
}
function applyI18n(root = document){
  document.documentElement.lang = getLocale();
  root.querySelectorAll('[data-i18n]').forEach(el => { el.innerHTML = t(el.getAttribute('data-i18n')); });
  root.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder'))); });
  root.querySelectorAll('[data-i18n-title]').forEach(el => { el.setAttribute('title', t(el.getAttribute('data-i18n-title'))); });
  root.querySelectorAll('[data-i18n-aria-label]').forEach(el => { el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria-label'))); });
  document.title = t('app_title');
  document.querySelector('meta[name="description"]')?.setAttribute('content', t('app_description'));
}

document.addEventListener('DOMContentLoaded', () => applyI18n());

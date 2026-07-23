/**
 * Modo demonstração (preview estático).
 *
 * Ativado apenas quando o build define VITE_DEMO=1. Nesse caso, todas as
 * chamadas de `apiRequest` são desviadas para este backend em memória, com
 * dados literários realistas. Em produção (VITE_DEMO ausente), este módulo
 * não altera nada — `apiRequest` segue para o FastAPI normalmente.
 */

import type { Account } from '../types/account'
import type { CatalogPublisher, CatalogWork } from '../types/catalog'
import type { DiaryEntry } from '../types/diary'
import type { FeedItem, FeedUser, ReadingNowItem, ReviewComment } from '../types/feed'
import type { ProfilePerson, ProfileReading, ProfileText, PublicProfileResponse } from '../types/profile'
import type { ShelfReading } from '../types/reading'

export const DEMO_MODE = import.meta.env.VITE_DEMO === '1'

/* ------------------------------------------------------------------ */
/* Acervo de demonstração                                              */
/* ------------------------------------------------------------------ */

const GB = (id: string) =>
  `https://books.google.com/books/content?id=${id}&printsec=frontcover&img=1&zoom=1&source=gbs_api`
const CDL = (isbn: string, slug: string) =>
  `https://cdl-static.s3-sa-east-1.amazonaws.com/covers/160/${isbn}/${slug}.jpg`

const works: CatalogWork[] = [
  {
    obra_id: 1, edicao_id: 101, work_key: 'demo:crime-e-castigo',
    titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', ano: 1866,
    idioma_original: 'Russo', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp', editora: 'Editora 34',
    tem_pt: true, leituras_count: 42, nota_media: 4.6, criticas_publicas: 12,
    lendo_agora_count: 3, generos: ['romance', 'clássico'], literatura_pais: 'Rússia',
  },
  {
    obra_id: 2, edicao_id: 102, work_key: 'demo:dom-casmurro',
    titulo: 'Dom Casmurro', autor: 'Machado de Assis', ano: 1899,
    idioma_original: 'Português', capa_url: CDL('9788582850350', 'dom-casmurro'),
    editora: 'Companhia das Letras', tem_pt: true, leituras_count: 58,
    nota_media: 4.4, criticas_publicas: 15, lendo_agora_count: 5,
    generos: ['romance', 'clássico'], literatura_pais: 'Brasil',
  },
  {
    obra_id: 3, edicao_id: 103, work_key: 'demo:paixao-gh',
    titulo: 'A paixão segundo G.H.', autor: 'Clarice Lispector', ano: 1964,
    idioma_original: 'Português', capa_url: '', editora: 'Rocco',
    tem_pt: true, leituras_count: 31, nota_media: 4.8, criticas_publicas: 9,
    lendo_agora_count: 2, generos: ['romance'], literatura_pais: 'Brasil',
  },
  {
    obra_id: 4, edicao_id: 104, work_key: 'demo:grande-sertao',
    titulo: 'Grande sertão: veredas', autor: 'João Guimarães Rosa', ano: 1956,
    idioma_original: 'Português', capa_url: GB('3MaCDQAAQBAJ'), editora: 'Companhia das Letras',
    tem_pt: true, leituras_count: 27, nota_media: 4.9, criticas_publicas: 8,
    lendo_agora_count: 4, generos: ['romance', 'clássico'], literatura_pais: 'Brasil',
  },
  {
    obra_id: 5, edicao_id: 105, work_key: 'demo:tecnofeudalismo',
    titulo: 'Tecnofeudalismo: o que matou o capitalismo', autor: 'Yanis Varoufakis',
    ano: 2024, idioma_original: 'Inglês',
    capa_url: 'https://covers.openlibrary.org/b/isbn/8542233840-L.jpg?default=false',
    editora: 'Crítica', tem_pt: true, leituras_count: 19, nota_media: 4.1,
    criticas_publicas: 5, lendo_agora_count: 6, generos: ['ensaio', 'política'],
    literatura_pais: 'Grécia',
  },
  {
    obra_id: 6, edicao_id: 106, work_key: 'demo:comporte-se',
    titulo: 'Comporte-se', autor: 'Robert M. Sapolsky', ano: 2017,
    idioma_original: 'Inglês', capa_url: CDL('9786559210824', 'comporte-se'),
    editora: 'Companhia das Letras', tem_pt: true, leituras_count: 14,
    nota_media: 4.3, criticas_publicas: 4, lendo_agora_count: 1,
    generos: ['ensaio', 'ciência'], literatura_pais: 'Estados Unidos',
  },
  {
    obra_id: 7, edicao_id: 107, work_key: 'demo:estado-e-revolucao',
    titulo: 'O Estado e a revolução', autor: 'Vladímir Lênin', ano: 1917,
    idioma_original: 'Russo', capa_url: GB('vL9DDwAAQBAJ'), editora: 'Boitempo Editorial',
    tem_pt: true, leituras_count: 11, nota_media: 4.0, criticas_publicas: 3,
    lendo_agora_count: 1, generos: ['ensaio', 'política'], literatura_pais: 'Rússia',
  },
  {
    obra_id: 8, edicao_id: 108, work_key: 'demo:cus-de-judas',
    titulo: 'Os cus de Judas', autor: 'António Lobo Antunes', ano: 1979,
    idioma_original: 'Português', capa_url: GB('2fo6zgEACAAJ'), editora: 'Objetiva',
    tem_pt: true, leituras_count: 9, nota_media: 4.2, criticas_publicas: 2,
    lendo_agora_count: 0, generos: ['romance'], literatura_pais: 'Portugal',
  },
  {
    obra_id: 9, edicao_id: 109, work_key: 'demo:dostoievski-frank',
    titulo: 'Dostoiévski', autor: 'Joseph Frank', ano: 2002,
    idioma_original: 'Inglês', capa_url: CDL('9788535931303', 'dostoievski'),
    editora: 'Companhia das Letras', tem_pt: true, leituras_count: 8,
    nota_media: 4.7, criticas_publicas: 2, lendo_agora_count: 1,
    generos: ['biografia'], literatura_pais: 'Estados Unidos',
  },
  {
    obra_id: 10, edicao_id: 110, work_key: 'demo:infiel',
    titulo: 'Infiel', autor: 'Ayaan Hirsi Ali', ano: 2006,
    idioma_original: 'Holandês', capa_url: CDL('9788535920253', 'infiel'),
    editora: 'Companhia das Letras', tem_pt: true, leituras_count: 7,
    nota_media: 4.2, criticas_publicas: 2, lendo_agora_count: 0,
    generos: ['biografia'], literatura_pais: 'Somália',
  },
  {
    obra_id: 11, edicao_id: 111, work_key: 'demo:memorias-postumas',
    titulo: 'Memórias póstumas de Brás Cubas', autor: 'Machado de Assis', ano: 1881,
    idioma_original: 'Português', capa_url: '', editora: 'Penguin-Companhia',
    tem_pt: true, leituras_count: 33, nota_media: 4.5, criticas_publicas: 10,
    lendo_agora_count: 2, generos: ['romance', 'clássico'], literatura_pais: 'Brasil',
  },
  {
    obra_id: 12, edicao_id: 112, work_key: 'demo:early-years',
    titulo: 'The Early Years: The Lyrics of Tom Waits 1971-1983', autor: 'Tom Waits',
    ano: 2009, idioma_original: 'Inglês', capa_url: GB('ZsNdEQAAQBAJ'),
    editora: 'Harper Collins', tem_pt: false, leituras_count: 2, nota_media: null,
    criticas_publicas: 0, lendo_agora_count: 0, generos: ['música'],
    literatura_pais: 'Estados Unidos',
  },
]

const byKey = (key: string) => works.find((work) => work.work_key === key)

/* ------------------------------------------------------------------ */
/* Conta e estante                                                     */
/* ------------------------------------------------------------------ */

const account: Account = {
  handle: 'leitor-demo',
  nome: 'Leitor da Lombada',
  bio: 'lendo devagar, anotando sempre.',
  avatar_url: '',
  avatar_custom: false,
  email: null,
  logado: false,
  provedor: 'anonimo',
  admin: false,
  followers_count: 3,
  following_count: 4,
  edicoes_possui: 5,
  edicoes_desejadas: 3,
}

let shelf: ShelfReading[] = [
  {
    leitura_id: 1, status: 'Lendo', nota: null, relato: '', publico: true,
    spoiler: false, data: '2026-07-02', titulo: 'Crime e castigo',
    autor: 'Fiódor Dostoiévski', work_key: 'demo:crime-e-castigo', edicao_id: 101,
    ol_edition_key: null, editora: 'Editora 34', tradutor: 'Paulo Bezerra',
    ano: 2016, isbn: '9788573265975', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp', paginas: 592,
    tenho_edicao: true, quero_edicao: false, li_edicao: false,
  },
  {
    leitura_id: 2, status: 'Lendo', nota: null, relato: '', publico: true,
    spoiler: false, data: '2026-06-28', titulo: 'Tecnofeudalismo: o que matou o capitalismo',
    autor: 'Yanis Varoufakis', work_key: 'demo:tecnofeudalismo', edicao_id: 105,
    ol_edition_key: null, editora: 'Crítica', tradutor: '',
    ano: 2024, isbn: '9788542233844', capa_url: 'https://covers.openlibrary.org/b/isbn/8542233840-L.jpg?default=false',
    paginas: 296, tenho_edicao: true, quero_edicao: false, li_edicao: false,
  },
  {
    leitura_id: 3, status: 'Lido', nota: 5, publico: true, spoiler: false,
    relato: 'Releitura anual. Cada frase parece escrita hoje — o sertão continua sendo o mundo.',
    data: '2026-06-14', titulo: 'Grande sertão: veredas', autor: 'João Guimarães Rosa',
    work_key: 'demo:grande-sertao', edicao_id: 104, ol_edition_key: null,
    editora: 'Companhia das Letras', tradutor: '', ano: 2015, isbn: '9788535928457',
    capa_url: GB('3MaCDQAAQBAJ'), paginas: 624, tenho_edicao: true, quero_edicao: false, li_edicao: true,
  },
  {
    leitura_id: 4, status: 'Lido', nota: 4.5, publico: true, spoiler: true,
    relato: 'Capitu é um enigma que o narrador não merecia resolver. Arquitetura perfeita.',
    data: '2026-05-30', titulo: 'Dom Casmurro', autor: 'Machado de Assis',
    work_key: 'demo:dom-casmurro', edicao_id: 102, ol_edition_key: null,
    editora: 'Companhia das Letras', tradutor: '', ano: 2019, isbn: '9788582850350',
    capa_url: CDL('9788582850350', 'dom-casmurro'), paginas: 256,
    tenho_edicao: true, quero_edicao: false, li_edicao: true,
  },
  {
    leitura_id: 5, status: 'Lido', nota: 5, publico: true, spoiler: false,
    relato: 'Uma barata, uma cena mística e a prosa mais corajosa do Brasil.',
    data: '2026-05-11', titulo: 'A paixão segundo G.H.', autor: 'Clarice Lispector',
    work_key: 'demo:paixao-gh', edicao_id: 103, ol_edition_key: null,
    editora: 'Rocco', tradutor: '', ano: 2021, isbn: '9786555320576',
    capa_url: '', paginas: 192, tenho_edicao: true, quero_edicao: false, li_edicao: true,
  },
  {
    leitura_id: 6, status: 'Lido', nota: 4, publico: true, spoiler: false,
    relato: 'Denso como poucos. O capítulo sobre o 25 de Abril fica na cabeça por dias.',
    data: '2026-04-22', titulo: 'Os cus de Judas', autor: 'António Lobo Antunes',
    work_key: 'demo:cus-de-judas', edicao_id: 108, ol_edition_key: null,
    editora: 'Objetiva', tradutor: 'Cristina Rodriguez', ano: 2010,
    isbn: '9788539000058', capa_url: GB('2fo6zgEACAAJ'), paginas: 224,
    tenho_edicao: false, quero_edicao: false, li_edicao: true,
  },
  {
    leitura_id: 7, status: 'Quero ler', nota: null, relato: '', publico: true,
    spoiler: false, data: '2026-07-10', titulo: 'Comporte-se', autor: 'Robert M. Sapolsky',
    work_key: 'demo:comporte-se', edicao_id: 106, ol_edition_key: null,
    editora: 'Companhia das Letras', tradutor: 'Ivo Korytowski', ano: 2018,
    isbn: '9786559210824', capa_url: CDL('9786559210824', 'comporte-se'), paginas: 688,
    tenho_edicao: false, quero_edicao: true, li_edicao: false,
  },
  {
    leitura_id: 8, status: 'Quero ler', nota: null, relato: '', publico: true,
    spoiler: false, data: '2026-07-08', titulo: 'Dostoiévski', autor: 'Joseph Frank',
    work_key: 'demo:dostoievski-frank', edicao_id: 109, ol_edition_key: null,
    editora: 'Companhia das Letras', tradutor: 'Sérgio Flaksman', ano: 2002,
    isbn: '9788535931303', capa_url: CDL('9788535931303', 'dostoievski'), paginas: 384,
    tenho_edicao: false, quero_edicao: true, li_edicao: false,
  },
]

/* ------------------------------------------------------------------ */
/* Diário                                                              */
/* ------------------------------------------------------------------ */

let diary: DiaryEntry[] = [
  {
    id: 5, leitura_id: 1, progresso_tipo: 'pagina', pagina: 312, porcentagem: 53,
    capitulo: '', capitulo_ordem: null, pagina_estimada: null, origem: 'diario',
    paginas_delta: 44, nota: 'O capítulo do sonho do cavalo é insuportável e perfeito.',
    publico: true, spoiler: false, created_at: '2026-07-15T21:34:00Z',
    updated_at: '2026-07-15T21:34:00Z', status: 'Lendo',
    titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp',
  },
  {
    id: 4, leitura_id: 2, progresso_tipo: 'porcentagem', pagina: null, porcentagem: 38,
    capitulo: '', capitulo_ordem: null, pagina_estimada: 112, origem: 'li_mais',
    paginas_delta: 31, nota: '',
    publico: true, spoiler: false, created_at: '2026-07-14T12:10:00Z',
    updated_at: '2026-07-14T12:10:00Z', status: 'Lendo',
    titulo: 'Tecnofeudalismo', autor: 'Yanis Varoufakis',
    capa_url: 'https://covers.openlibrary.org/b/isbn/8542233840-L.jpg?default=false',
  },
  {
    id: 3, leitura_id: 1, progresso_tipo: 'pagina', pagina: 268, porcentagem: 45,
    capitulo: '', capitulo_ordem: null, pagina_estimada: null, origem: 'diario',
    paginas_delta: 52, nota: 'Porfírio é o melhor antagonista silencioso que já li.',
    publico: true, spoiler: false, created_at: '2026-07-12T22:01:00Z',
    updated_at: '2026-07-12T22:01:00Z', status: 'Lendo',
    titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp',
  },
  {
    id: 2, leitura_id: 1, progresso_tipo: 'livre', pagina: null, porcentagem: null,
    capitulo: '', capitulo_ordem: null, pagina_estimada: null, origem: 'diario',
    paginas_delta: null, nota: 'Comecei a anotar os nomes dos personagens na margem. Raskólnikov, Razumikhin, Luzhin…',
    publico: true, spoiler: false, created_at: '2026-07-06T20:45:00Z',
    updated_at: '2026-07-06T20:45:00Z', status: 'Lendo',
    titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp',
  },
  {
    id: 1, leitura_id: 1, progresso_tipo: 'pagina', pagina: 40, porcentagem: 7,
    capitulo: '', capitulo_ordem: null, pagina_estimada: null, origem: 'diario',
    paginas_delta: 40, nota: 'Primeiras páginas. Petersburgo sufoca desde a abertura.',
    publico: true, spoiler: false, created_at: '2026-07-02T19:20:00Z',
    updated_at: '2026-07-02T19:20:00Z', status: 'Lendo',
    titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp',
  },
]

/* ------------------------------------------------------------------ */
/* Feed e comunidade                                                   */
/* ------------------------------------------------------------------ */

const readers: FeedUser[] = [
  { handle: 'margem-2226', nome: 'Gustavo Trevisolli', avatar_url: '', is_demo: true, is_following: true, is_me: false, bio: 'fundador da lombada.', reviews_count: 5, followers_count: 12 },
  { handle: 'capitulo-7', nome: 'Marina Albuquerque', avatar_url: '', is_demo: true, is_following: false, is_me: false, bio: 'clássicos russos e brasileiros.', reviews_count: 18, followers_count: 34 },
  { handle: 'verso-e-reverso', nome: 'Tomás Rocha', avatar_url: '', is_demo: true, is_following: false, is_me: false, bio: 'poesia, ensaio e o que mais couber.', reviews_count: 9, followers_count: 21 },
]

function feedReading(partial: Partial<import('../types/feed').FeedReading>): import('../types/feed').FeedReading {
  return {
    leitura_id: 0, status: 'Lido', nota: null, publico: true, is_demo: true,
    spoiler: false, relato: '', likes_count: 0, liked_by_me: false,
    saved_by_me: false, reported_by_me: false, comments_count: 0, ...partial,
  }
}

let feedItems: FeedItem[] = [
  {
    tipo: 'wrote_review', usuario: readers[0],
    livro: { titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', work_key: 'demo:crime-e-castigo', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp' },
    edicao: { editora: 'Editora 34', tradutor: 'Paulo Bezerra', ano: 2016 },
    leitura: feedReading({
      leitura_id: 501, nota: 5,
      relato: 'O mais dinâmico livro entre as quatro grandes obras de Dostoiévski.',
      likes_count: 6, comments_count: 2,
    }),
    created_at: '2026-07-14T18:22:00Z',
  },
  {
    tipo: 'wrote_review', usuario: readers[1],
    livro: { titulo: 'A paixão segundo G.H.', autor: 'Clarice Lispector', work_key: 'demo:paixao-gh', capa_url: '' },
    edicao: { editora: 'Rocco', tradutor: '', ano: 2021 },
    leitura: feedReading({
      leitura_id: 502, nota: 5,
      relato: 'Terminei em silêncio e fiquei olhando para a parede por dez minutos. Clarice reescreve o que a gente acha que a linguagem pode fazer.',
      likes_count: 11, comments_count: 1,
    }),
    created_at: '2026-07-13T09:15:00Z',
  },
  {
    tipo: 'started_reading', usuario: readers[2],
    livro: { titulo: 'Tecnofeudalismo', autor: 'Yanis Varoufakis', work_key: 'demo:tecnofeudalismo', capa_url: 'https://covers.openlibrary.org/b/isbn/8542233840-L.jpg?default=false' },
    edicao: { editora: 'Crítica', tradutor: '', ano: 2024 },
    leitura: feedReading({ leitura_id: 503, status: 'Lendo', likes_count: 2 }),
    created_at: '2026-07-12T16:40:00Z',
  },
  {
    tipo: 'wrote_review', usuario: readers[1],
    livro: { titulo: 'Dom Casmurro', autor: 'Machado de Assis', work_key: 'demo:dom-casmurro', capa_url: CDL('9788582850350', 'dom-casmurro') },
    edicao: { editora: 'Companhia das Letras', tradutor: '', ano: 2019 },
    leitura: feedReading({
      leitura_id: 504, nota: 4.5, spoiler: true,
      relato: 'Dessa vez prestei atenção só nas vezes em que Bentinho contradiz a si mesmo. É um tribunal onde o réu é o narrador.',
      likes_count: 4,
    }),
    created_at: '2026-07-10T14:05:00Z',
  },
  {
    tipo: 'wants_to_read', usuario: readers[0],
    livro: { titulo: 'Comporte-se', autor: 'Robert M. Sapolsky', work_key: 'demo:comporte-se', capa_url: CDL('9786559210824', 'comporte-se') },
    edicao: { editora: 'Companhia das Letras', tradutor: 'Ivo Korytowski', ano: 2018 },
    leitura: feedReading({ leitura_id: 505, status: 'Quero ler' }),
    created_at: '2026-07-09T11:30:00Z',
  },
]

const readingNow: ReadingNowItem[] = [
  { handle: 'margem-2226', nome: 'Gustavo Trevisolli', avatar_url: '', is_demo: true, titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', capa_url: 'https://acdn-us.mitiendanube.com/stores/005/277/283/products/9788544002162-d0dc365a2ebc263a4217380849257775-480-0.webp', work_key: 'demo:crime-e-castigo' },
  { handle: 'capitulo-7', nome: 'Marina Albuquerque', avatar_url: '', is_demo: true, titulo: 'Grande sertão: veredas', autor: 'João Guimarães Rosa', capa_url: GB('3MaCDQAAQBAJ'), work_key: 'demo:grande-sertao' },
  { handle: 'verso-e-reverso', nome: 'Tomás Rocha', avatar_url: '', is_demo: true, titulo: 'Tecnofeudalismo', autor: 'Yanis Varoufakis', capa_url: 'https://covers.openlibrary.org/b/isbn/8542233840-L.jpg?default=false', work_key: 'demo:tecnofeudalismo' },
]

let comments: ReviewComment[] = [
  { id: 1, texto: 'Concordo demais — a estrutura policial engana: o centro é outro.', criado_em: '2026-07-14T19:02:00Z', usuario: { handle: 'capitulo-7', nome: 'Marina Albuquerque', avatar_url: '', is_demo: true }, is_me: false },
  { id: 2, texto: 'A tradução do Paulo Bezerra carrega metade desse dinamismo.', criado_em: '2026-07-14T20:41:00Z', usuario: { handle: 'verso-e-reverso', nome: 'Tomás Rocha', avatar_url: '', is_demo: true }, is_me: false },
]

/* ------------------------------------------------------------------ */
/* Perfil, editoras, literaturas                                       */
/* ------------------------------------------------------------------ */

let profileTexts: ProfileText[] = [
  {
    texto_id: 1, titulo: 'Por que reler Dostoiévski aos poucos',
    conteudo: 'Percebi que os russos rendem mais em doses de quarenta páginas. Mais que isso e a angústia vira ruído; menos, e ela não tem tempo de assentar. Anoto aqui para o futuro eu: devagar, sempre.',
    trecho: false, publico: true, criado_em: '2026-07-11T13:00:00Z',
    obra: { titulo: 'Crime e castigo', autor: 'Fiódor Dostoiévski', work_key: 'demo:crime-e-castigo' },
  },
  {
    texto_id: 2, titulo: 'O sertão é o mundo',
    conteudo: '"O sertão é sem lugar." Riobaldo mente: o sertão é todo lugar.',
    trecho: true, publico: true, criado_em: '2026-06-15T10:30:00Z',
    obra: { titulo: 'Grande sertão: veredas', autor: 'João Guimarães Rosa', work_key: 'demo:grande-sertao' },
  },
]

const people: ProfilePerson[] = readers.map((reader) => ({
  handle: reader.handle, nome: reader.nome, bio: reader.bio ?? '',
  avatar_url: reader.avatar_url, is_demo: true, is_following: reader.is_following, is_me: false,
}))

const publishers: CatalogPublisher[] = [
  { editora: 'Companhia das Letras', slug: 'companhia-das-letras', obras_count: 8153, edicoes_count: 12040, com_capa_count: 7901, com_isbn_count: 8022 },
  { editora: 'Grupo Editorial Record', slug: 'grupo-editorial-record', obras_count: 7983, edicoes_count: 11020, com_capa_count: 7402, com_isbn_count: 7510 },
  { editora: 'Alta Books', slug: 'alta-books', obras_count: 5298, edicoes_count: 6010, com_capa_count: 5011, com_isbn_count: 5100 },
  { editora: 'Rocco', slug: 'rocco', obras_count: 2229, edicoes_count: 3050, com_capa_count: 2104, com_isbn_count: 2166 },
  { editora: 'Autêntica', slug: 'autentica', obras_count: 1755, edicoes_count: 2010, com_capa_count: 1690, com_isbn_count: 1702 },
  { editora: 'Intrínseca', slug: 'intrinseca', obras_count: 1332, edicoes_count: 1650, com_capa_count: 1301, com_isbn_count: 1312 },
  { editora: 'Editora 34', slug: 'editora-34', obras_count: 794, edicoes_count: 980, com_capa_count: 760, com_isbn_count: 770 },
  { editora: 'Boitempo Editorial', slug: 'boitempo-editorial', obras_count: 711, edicoes_count: 820, com_capa_count: 698, com_isbn_count: 705 },
]

const literatures = [
  { slug: 'brasileira', label: 'Literatura brasileira', pais: 'Brasil', regiao: 'América do Sul' },
  { slug: 'portuguesa', label: 'Literatura portuguesa', pais: 'Portugal', regiao: 'Europa' },
  { slug: 'russa', label: 'Literatura russa', pais: 'Rússia', regiao: 'Europa' },
  { slug: 'norte-americana', label: 'Literatura norte-americana', pais: 'Estados Unidos', regiao: 'América do Norte' },
  { slug: 'japonesa', label: 'Literatura japonesa', pais: 'Japão', regiao: 'Ásia' },
  { slug: 'francesa', label: 'Literatura francesa', pais: 'França', regiao: 'Europa' },
  { slug: 'argentea', label: 'Literatura argentina', pais: 'Argentina', regiao: 'América do Sul' },
  { slug: 'inglesa', label: 'Literatura inglesa', pais: 'Inglaterra', regiao: 'Europa' },
]

/* ------------------------------------------------------------------ */
/* Roteador do modo demo                                               */
/* ------------------------------------------------------------------ */

const delay = (ms = 160) => new Promise((resolve) => setTimeout(resolve, ms))

function toProfileReading(reading: ShelfReading): ProfileReading {
  return {
    ...reading,
    likes_count: 0, liked_by_me: false, saved_by_me: false,
    reported_by_me: false, comments_count: 0,
  }
}

function publicProfile(handle: string): PublicProfileResponse {
  const mine = handle === account.handle
  const owner = people.find((person) => person.handle === handle)
  const readings = mine ? shelf.map(toProfileReading) : []
  const stats = {
    total: readings.length,
    lidos: readings.filter((item) => item.status === 'Lido').length,
    lendo: readings.filter((item) => item.status === 'Lendo').length,
    quero_ler: readings.filter((item) => item.status === 'Quero ler').length,
    media_nota: 4.6,
  }
  return {
    handle,
    nome: mine ? account.nome : owner?.nome ?? handle,
    bio: mine ? account.bio : owner?.bio ?? '',
    avatar_url: mine ? account.avatar_url : owner?.avatar_url ?? '',
    is_demo: true,
    leituras: readings,
    textos: mine ? profileTexts : [],
    stats,
    lendo_agora: readings.filter((item) => item.status === 'Lendo'),
    ultimas_leituras: readings.slice(0, 4),
    criticas_publicas: readings.filter((item) => item.relato),
    favoritos: readings.filter((item) => (item.nota ?? 0) >= 4.5),
    followers_count: mine ? account.followers_count : 12,
    following_count: mine ? account.following_count : 8,
    edicoes_possui: mine ? account.edicoes_possui : 0,
    edicoes_desejadas: mine ? account.edicoes_desejadas : 0,
    is_following: people.find((person) => person.handle === handle)?.is_following ?? false,
    is_me: mine,
  }
}

export async function demoApiRequest<T>(path: string, init: RequestInit): Promise<T> {
  await delay()
  const url = new URL(path, 'https://demo.lombada')
  const { pathname, searchParams } = url
  const method = (init.method ?? 'GET').toUpperCase()
  const body = typeof init.body === 'string' ? JSON.parse(init.body) as Record<string, unknown> : {}

  const fail = (message: string): never => { throw new Error(message) }

  /* sessão e conta */
  if (pathname === '/api/eu' && method === 'GET') return account as T
  if (pathname === '/api/eu/status') {
    return { padrao: ['Lido', 'Lendo', 'Quero ler', 'Abandonado', 'Relendo'], custom: [{ id: 1, nome: 'Na fila' }] } as T
  }
  if (pathname === '/api/eu/perfil' && method === 'PATCH') {
    account.nome = String(body.nome ?? account.nome)
    account.bio = String(body.bio ?? account.bio)
    return { handle: account.handle, nome: account.nome, bio: account.bio, message: 'Perfil atualizado.' } as T
  }
  if (pathname === '/api/eu/avatar') {
    return { avatar_url: account.avatar_url, avatar_custom: account.avatar_custom } as T
  }

  /* estante */
  if (pathname === '/api/prateleira' && method === 'GET') return shelf as T
  if (pathname === '/api/prateleira' && method === 'POST') {
    const work = byKey(String(body.work_key ?? ''))
    const created: ShelfReading = {
      leitura_id: Math.max(0, ...shelf.map((item) => item.leitura_id)) + 1,
      status: String(body.status ?? 'Lendo'), nota: (body.nota as number | null) ?? null,
      relato: String(body.relato ?? ''), publico: Boolean(body.publico ?? true),
      spoiler: Boolean(body.spoiler ?? false), data: String(body.data ?? new Date().toISOString().slice(0, 10)),
      titulo: String(body.titulo ?? work?.titulo ?? ''), autor: String(body.autor ?? work?.autor ?? ''),
      work_key: String(body.work_key ?? ''), edicao_id: Number(body.edicao_id ?? work?.edicao_id ?? 0) || (work?.edicao_id ?? 0),
      ol_edition_key: null, editora: String(body.editora ?? work?.editora ?? ''),
      tradutor: String(body.tradutor ?? ''), ano: (body.ano_edicao as number | null) ?? work?.ano ?? null,
      isbn: String(body.isbn ?? ''), capa_url: String(body.capa_url ?? work?.capa_url ?? ''),
      paginas: (body.paginas as number | null) ?? null,
      tenho_edicao: Boolean(body.tenho_edicao), quero_edicao: Boolean(body.quero_edicao), li_edicao: false,
    }
    shelf = [created, ...shelf]
    return { leitura_id: created.leitura_id, obra_id: work?.obra_id ?? 0, edicao_id: created.edicao_id } as T
  }
  const readingMatch = pathname.match(/^\/api\/prateleira\/(\d+)$/)
  if (readingMatch) {
    const id = Number(readingMatch[1])
    if (method === 'PATCH') {
      shelf = shelf.map((item) => (item.leitura_id === id ? { ...item, ...body } as ShelfReading : item))
      const updated = shelf.find((item) => item.leitura_id === id)
      return { leitura_id: id, status: updated?.status, nota: updated?.nota ?? null, relato: updated?.relato ?? '', data: updated?.data, publico: updated?.publico ?? true, spoiler: updated?.spoiler ?? false } as T
    }
    if (method === 'DELETE') {
      shelf = shelf.filter((item) => item.leitura_id !== id)
      return { ok: true } as T
    }
  }

  /* diário */
  if (pathname === '/api/diario' && method === 'GET') return diary as T
  const diaryEntryMatch = pathname.match(/^\/api\/diario\/(\d+)$/)
  if (diaryEntryMatch) {
    const id = Number(diaryEntryMatch[1])
    if (method === 'PATCH') {
      diary = diary.map((entry) => (entry.id === id ? { ...entry, ...body, updated_at: new Date().toISOString() } as DiaryEntry : entry))
      return diary.find((entry) => entry.id === id) as T
    }
    if (method === 'DELETE') {
      diary = diary.filter((entry) => entry.id !== id)
      return { ok: true } as T
    }
  }
  const diaryCreateMatch = pathname.match(/^\/api\/leitura\/(\d+)\/diario$/)
  if (diaryCreateMatch && method === 'POST') {
    const reading = shelf.find((item) => item.leitura_id === Number(diaryCreateMatch[1]))
    const entry: DiaryEntry = {
      id: Math.max(0, ...diary.map((item) => item.id)) + 1,
      leitura_id: Number(diaryCreateMatch[1]),
      progresso_tipo: (body.progresso_tipo as DiaryEntry['progresso_tipo']) ?? 'livre',
      pagina: (body.pagina as number | null) ?? null,
      porcentagem: (body.porcentagem as number | null) ?? null,
      capitulo: String(body.capitulo ?? ''), capitulo_ordem: (body.capitulo_ordem as number | null) ?? null,
      pagina_estimada: null, origem: String(body.origem ?? 'diario'), paginas_delta: null,
      nota: String(body.nota ?? ''), publico: Boolean(body.publico ?? true),
      spoiler: Boolean(body.spoiler ?? false),
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      status: reading?.status, titulo: reading?.titulo, autor: reading?.autor, capa_url: reading?.capa_url,
    }
    diary = [entry, ...diary]
    return entry as T
  }
  const pagesMatch = pathname.match(/^\/api\/edicoes\/(\d+)\/paginas$/)
  if (pagesMatch) return { paginas: 592, fonte: 'demo' } as T
  const chaptersMatch = pathname.match(/^\/api\/edicoes\/(\d+)\/capitulos$/)
  if (chaptersMatch) {
    return [
      { titulo: 'Parte I — Capítulo 1', ordem: 1, fonte: 'demo' },
      { titulo: 'Parte I — Capítulo 2', ordem: 2, fonte: 'demo' },
    ] as T
  }

  /* catálogo */
  if (pathname === '/api/buscar') {
    const query = (searchParams.get('q') ?? '').toLowerCase().trim()
    if (!query) return works as T
    const found = works.filter((work) =>
      `${work.titulo} ${work.autor} ${work.editora ?? ''}`.toLowerCase().includes(query),
    )
    return found as T
  }
  if (pathname === '/api/buscas/populares') {
    return [
      { termo: 'Crime e castigo', total: 41 },
      { termo: 'Clarice Lispector', total: 38 },
      { termo: 'Machado de Assis', total: 35 },
      { termo: 'Grande sertão', total: 22 },
      { termo: 'Tecnofeudalismo', total: 12 },
      { termo: 'Virginia Woolf', total: 11 },
    ] as T
  }
  if (pathname === '/api/explore/populares') return works as T
  if (pathname === '/api/editoras') return publishers as T
  if (pathname === '/api/literaturas') return literatures as T
  if (pathname === '/api/obra/social') {
    const work = byKey(searchParams.get('work_key') ?? '')
    return {
      obra: { id: work?.obra_id, work_key: work?.work_key ?? '', titulo: work?.titulo ?? searchParams.get('titulo') ?? '', autor: work?.autor ?? searchParams.get('autor') ?? '', ano: work?.ano ?? null, idioma_original: work?.idioma_original ?? '', descricao: 'Uma das obras mais comentadas da comunidade Lombada nas últimas semanas.' },
      estatisticas: { leituras: work?.leituras_count ?? 0, criticas: work?.criticas_publicas ?? 0, media: work?.nota_media ?? null, lendo: work?.lendo_agora_count ?? 0, querem: 7 },
      edicoes: [],
      minha_leitura: null,
    } as T
  }
  if (pathname === '/api/edicoes') {
    const work = byKey(searchParams.get('work_key') ?? '')
    return [{
      edicao_id: work?.edicao_id ?? 0, ol_edition_key: null,
      titulo_edicao: work?.titulo ?? '', editora: work?.editora ?? '',
      tradutor: '', isbn: '', idioma: 'Português', ano: work?.ano ?? null,
      capa_url: work?.capa_url ?? '', paginas: 320,
      leituras_count: work?.leituras_count ?? 0, leituras: work?.leituras_count ?? 0,
      tem: 3, querem: 7, media: work?.nota_media ?? null,
      estado: { tenho: false, quero: false, li: false },
    }] as T
  }

  /* feed */
  if (pathname === '/api/feed') return { following_count: account.following_count, items: feedItems } as T
  if (pathname === '/api/feed/discover') return { reviews: feedItems, readers } as T
  if (pathname === '/api/feed/lendo') return { items: readingNow } as T

  const likeMatch = pathname.match(/^\/api\/reviews\/(\d+)\/like$/)
  if (likeMatch) {
    const id = Number(likeMatch[1])
    feedItems = feedItems.map((item) => {
      if (item.tipo === 'wrote_text' || item.leitura.leitura_id !== id) return item
      const liked = method === 'POST'
      return { ...item, leitura: { ...item.leitura, liked_by_me: liked, likes_count: item.leitura.likes_count + (liked ? 1 : -1) } }
    })
    const current = feedItems.find((item) => item.tipo !== 'wrote_text' && item.leitura.leitura_id === id)
    return { liked: method === 'POST', likes_count: current && current.tipo !== 'wrote_text' ? current.leitura.likes_count : 0 } as T
  }
  const saveMatch = pathname.match(/^\/api\/reviews\/(\d+)\/save$/)
  if (saveMatch) return { saved: method === 'POST' } as T
  const commentsMatch = pathname.match(/^\/api\/reviews\/(\d+)\/comments$/)
  if (commentsMatch) {
    if (method === 'GET') return comments as T
    if (method === 'POST') {
      const comment: ReviewComment = {
        id: Math.max(0, ...comments.map((item) => item.id)) + 1,
        texto: String(body.texto ?? ''), criado_em: new Date().toISOString(),
        usuario: { handle: account.handle, nome: account.nome, avatar_url: account.avatar_url, is_demo: true },
        is_me: true,
      }
      comments = [...comments, comment]
      return comment as T
    }
  }
  const commentDeleteMatch = pathname.match(/^\/api\/comments\/(\d+)$/)
  if (commentDeleteMatch && method === 'DELETE') {
    comments = comments.filter((item) => item.id !== Number(commentDeleteMatch[1]))
    return { ok: true } as T
  }

  /* pessoas e perfis */
  const followMatch = pathname.match(/^\/api\/u\/([^/]+)\/follow$/)
  if (followMatch) {
    const person = people.find((item) => item.handle === followMatch[1])
    if (person) person.is_following = method === 'POST'
    return { following: person?.is_following ?? false, followers_count: 12, following_count: account.following_count } as T
  }
  const personSubMatch = pathname.match(/^\/api\/u\/([^/]+)\/(followers|following)$/)
  if (personSubMatch) return people as T
  const personMatch = pathname.match(/^\/api\/u\/([^/]+)$/)
  if (personMatch) return publicProfile(decodeURIComponent(personMatch[1])) as T

  /* textos do perfil */
  if (pathname === '/api/eu/textos') {
    if (method === 'GET') return profileTexts as T
    if (method === 'POST') {
      const text: ProfileText = {
        texto_id: Math.max(0, ...profileTexts.map((item) => item.texto_id)) + 1,
        titulo: String(body.titulo ?? ''), conteudo: String(body.conteudo ?? ''),
        trecho: false, publico: Boolean(body.publico ?? true),
        criado_em: new Date().toISOString(),
        obra: body.work_key ? { titulo: byKey(String(body.work_key))?.titulo ?? '', autor: byKey(String(body.work_key))?.autor ?? '', work_key: String(body.work_key) } : null,
      }
      profileTexts = [text, ...profileTexts]
      return text as T
    }
  }
  const textMatch = pathname.match(/^\/api\/eu\/textos\/(\d+)$/)
  if (textMatch) {
    const id = Number(textMatch[1])
    if (method === 'PATCH') {
      profileTexts = profileTexts.map((item) => (item.texto_id === id ? { ...item, ...body } as ProfileText : item))
      return profileTexts.find((item) => item.texto_id === id) as T
    }
    if (method === 'DELETE') {
      profileTexts = profileTexts.filter((item) => item.texto_id !== id)
      return { ok: true } as T
    }
  }

  return fail(`Rota demo não implementada: ${method} ${pathname}`)
}

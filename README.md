# Lombada

App de catálogo e registro de leituras — descobrir edições, registrar o que leu
(status, nota, crítica) e montar uma estante. Catálogo próprio, alimentado por
raspagem de sites de editoras brasileiras.

- **Produção:** [lombada.onrender.com](https://lombada.onrender.com) — deploy
  automático no Render **a cada merge na `main`**.
- **Stack:** FastAPI + SQLModel, Postgres/Neon, frontend SPA sem build
  (`static/app.js` + `static/app.css` + `index.html`).

---

## Arquitetura

### App
- **`main.py`** — API FastAPI. Registro de leitura em `POST /api/prateleira`
  (`_criar_leitura`, `_validar_entrada_leitura`); busca do catálogo em
  `_buscar_catalogo_local` (o doc da obra devolvido inclui `titulo/autor/ano/
  descricao/edicoes`).
- **`models.py`** — tabelas SQLModel (`Obra`, `Edicao`, `Leitura`, `UserEdition`,
  `CatalogSuggestion`, …) e **`migrar()`**, que roda no **boot do app** e aplica
  migrações idempotentes (`_add_column_if_missing`, DDLs `IF NOT EXISTS`, reparo
  de sequence/identity dos `id`).
- **`auth.py`** — `usuario_sessao()` cria um usuário anônimo automático; **login
  não é obrigatório** para registrar leitura.
- **`static/app.js` / `static/app.css` / `index.html`** — SPA. `salvar()` envia
  `/api/prateleira`; o card "Edição escolhida" mostra título/autor/meta e a
  **sinopse** (`escolha.descricao`). CSS/JS têm cache-bust `?v=…` no
  `index.html` — **bump ao alterar** CSS/JS, senão o navegador serve o antigo.

### Modelo de dados do catálogo
- **`obra`** = obra (título, autor, ano, **descricao**).
- **`edicao`** = edição (editora, isbn, idioma, tradutor, capa, ano) → aponta pra `obra`.
- **`leitura`** = registro do usuário sobre uma edição.
- **`source_records`** = camada crua da ingestão (campos normalizados +
  `raw_json` JSONB com `description` etc.).

## Pipeline de catálogo (ingestão → busca)

```
scripts/sync_publishers.py         raspa sites das editoras → grava em source_records
scripts/promote_source_records.py  source_records → obra/edicao (catálogo que a busca lê)
main.py _buscar_catalogo_local     a busca do app lê obra/edicao
```

A ingestão é **incremental** (pula o que já viu). O **modo faixa**
(`PUBLISHER_OFFSET`) re-busca uma janela de IDs/URLs — usado para backfill
(re-preencher autor/descrição em registros antigos; o `promote` só preenche
campos vazios, nunca sobrescreve).

### Editoras (`SOURCES` em `scripts/sync_publishers.py`)

As fontes são divididas em **grupos** (campo `group` no `SOURCES`; sem campo =
`principal`), e cada grupo tem um workflow de sync próprio que roda **em
paralelo** aos outros (concurrency groups distintos no Actions):

| grupo | workflow | cron | fontes |
|---|---|---|---|
| `principal` | `sync-publishers.yml` | `:13` | Editora 34, Record, Intrínseca, Todavia, Sextante, Autêntica |
| `cia` | `sync-publishers-cia.yml` | `:51 a cada 2h` | Companhia das Letras (isolada: a coleta via `categoria_json` varre ~218 categorias × ~16 páginas e demora mais que as outras — ver abaixo) |
| `expansao` | `sync-publishers-expansao.yml` | `:29` | Rocco, Arqueiro, Aleph, DarkSide, Boitempo, Ubu, Antofágica, Carambaia, Alta Books, L&PM |
| `universitaria` | `sync-publishers-universitarias.yml` | `:43` | Edusp, Unesp, Unicamp, UFMG, EDUFBA, UFSC, EDIPUCRS, UnB |

O "1 sync por vez" vale **dentro de cada workflow** (grupo de concorrência
próprio), não entre workflows. O passo de promote de todos eles é serializado
por **advisory lock no Postgres** (`promote_source_records.py`) — sem isso,
dois promotes simultâneos duplicariam obras. `PUBLISHER_SLUGS` explícito vence
o filtro de grupo (dá pra testar qualquer editora a partir de qualquer
workflow). Fontes dos grupos novos entram com `platform=auto` até o
`diagnose=true` confirmar a plataforma real de cada site.

#### Grupos expansao/universitaria — diagnose de 05/07/2026 (todas as 18 respondem)

| slug | plataforma detectada | sinal |
|---|---|---|
| `rocco` | WordPress | `wp-sitemap.xml` 200; 127 links de livro (`/produto/…`) na home |
| `arqueiro` | sem sitemap | 35 links `/produto/…` na home → crawl HTML |
| `aleph` | **Shopify** | `products.json` 200 JSON |
| `darkside` | **VTEX** | `/api/catalog_system/...` 206 JSON (Shopify probe devolve HTML) |
| `boitempo` | sitemap próprio | `sitemap.xml` 200 XML (home sem links no HTML bruto) |
| `ubu` | Magento | paths `/pub/media/catalog/...`; 48 links de livro na home |
| `antofagica` | **anti-bot** | tudo responde 202 text/html (challenge) — pode nunca coletar |
| `carambaia` | custom | 20 links de livro na home (`/livros/…`) → crawl HTML |
| `altabooks` | WordPress | `wp-sitemap.xml` 200; 379 links de livro na home |
| `lpm` | ASP clássico (IIS) | soft-200 em tudo; 76 links `/livro/{id}/{slug}` na home → crawl HTML (candidata futura a `id_range`) |
| `edusp` | custom | 19 links `/livros/…` na home → crawl HTML |
| `editora_unesp` | IIS soft-200 | só 2 links de livro na home — cobertura deve sair fraca |
| `editora_unicamp` | custom | 0 links de livro na home — vai precisar de extrator dedicado |
| `editora_ufmg` | SPA (JS) | paths devolvem 500 JSON; home sem links no HTML bruto |
| `edufba` | custom | 12 links de livro na home → crawl HTML |
| `editora_ufsc` | WordPress (sem sitemap) | 17 links de livro na home → crawl HTML |
| `edipucrs` | ? | origem fora do ar no diagnose (Cloudflare 522) — re-testar |
| `editora_unb` | WordPress | `wp-sitemap.xml` 200 |

#### Grupo principal — status

| slug | método | observações |
|---|---|---|
| `editora_34` | `id_range` 1–3000 | ~800 livros. Sem JSON-LD/meta; autor e sinopse ficam no bloco do `<h1>` (extrator dedicado `autor_editora34()`). |
| `record`, `sextante` | `auto` → Shopify | **Resolvido:** ISBN vinha vazio (`record` só tinha 19/3920 promovidos; `sextante` 1/732). `collect_via_shopify` cai em cascata: `barcode` → `sku` da variante → varredura da descrição → endpoint de produto único (`/products/{handle}.json` — algumas lojas, ex. sextante, omitem `barcode` da listagem em lote mas incluem no produto único) → ISBN embutido na URL. |
| `todavia`, `autentica` | `auto` → sitemap | Boa cobertura, com ISBN. |
| `intrinseca` | `auto` | Boa cobertura (~1370 registros, ~98% com ISBN) — a nota antiga de "coleta 0" está desatualizada. |

#### Grupo cia — status

| slug | método | observações |
|---|---|---|
| `cia_das_letras` | `["sitemap","categoria_json","html"]` | Sem sitemap → categoria via API JSON (ver "Status atual"), com fallback pro crawl HTML. **Isolada** no `sync-publishers-cia.yml` (cron a cada 2h) porque a varredura de categorias é lenta e segurava o principal. |

## Workflows (aba Actions)

- **Sync publisher source records** (`.github/workflows/sync-publishers.yml`):
  raspa → `source_records` e promove. Inputs: `dry_run`, `diagnose`, `dump_url`,
  `max_urls`, `offset`, `slugs`, `sleep_seconds`. Tem **cron horário** e um
  **concurrency group `sync-publishers`**. Cobre só o grupo `principal`. Não
  instala Chromium (nenhuma fonte deste grupo usa Playwright).
- **Sync publishers (Companhia das Letras)** (`sync-publishers-cia.yml`): só a
  Cia das Letras (grupo `cia`). Foi separada do principal porque a coleta via
  `categoria_json` varre todo o menu de categorias a cada execução e demora bem
  mais que as demais — assim o principal termina rápido sem esperar por ela. Tem
  **cron a cada 2 horas** (`:51`, contra os horários dos outros) já que a
  ingestão é incremental e não compensa rodá-la de hora em hora. Mantém o passo
  de Chromium (só pro input `debug_categoria_paginacao`).
- **Sync publishers (expansão)** (`sync-publishers-expansao.yml`) e
  **Sync publishers (universitárias)** (`sync-publishers-universitarias.yml`):
  mesmos inputs e pipeline, cada um cobrindo seu grupo de fontes, com
  concurrency group e cron próprios — rodam em paralelo ao principal.
- **Promote source records to catalog** (`.github/workflows/promote-catalog.yml`):
  só promove (sem raspar). Inputs: `dry_run`, `min_confidence`, `limit`. Ideal
  para backfill de campos (autor/descrição) sem re-scrape.

### Receitas

```
# Sync incremental de uma editora (grava):
Sync publisher source records → dry_run=false, slugs=editora_34, max_urls=250

# Testar sem gravar:
dry_run=true

# Re-scrape de uma faixa (backfill):
dry_run=false, slugs=editora_34, offset=0,    max_urls=2000   # ids 1-2000
dry_run=false, slugs=editora_34, offset=2000, max_urls=2000   # ids 2001-3000

# Inspecionar a estrutura de uma página (diagnóstico):
dump_url=https://www.editora34.com.br/livro/1000   (dry_run=true)

# Só promover / backfill de autor+descrição sem re-scrape:
Promote source records to catalog → dry_run=false, limit=5000
```

## Desenvolvimento

- **Testes locais precisam de Python 3.12+** (`publica.py` usa f-string com `\`,
  só válido em 3.12+). Dependências: `fastapi sqlmodel psycopg2-binary
  beautifulsoup4 requests`. O runner do Actions usa 3.11, mas o app roda 3.12+.
- Sem `DATABASE_URL`, o app usa SQLite (`sqlite:///lombada.db`) — bom para testar
  modelo/migração/lógica local.
- Muita coisa da lógica de scraping/promote é testável offline com HTML fake e
  cursores fake (ver histórico de commits de `sync_publishers.py`/`promote_*`).

## Armadilhas operacionais (importante)

- **Concurrency do Actions:** cada workflow de sync tem seu grupo e mantém só
  **1 run pending**; disparar outro do MESMO workflow **cancela o pending
  anterior**. Dispare **um run por workflow** e espere terminar. Workflows
  diferentes (principal/cia/expansão/universitárias/promote) rodam em paralelo
  entre si numa boa — o promote é protegido por advisory lock no Postgres.
- **Timing de merge:** o merge de um PR é um snapshot; commits empurrados
  **depois** do merge ficam de fora. Após mergear, **confirme que entrou na
  `main`** antes de agir (`git fetch origin main && git grep …`).
- **Ordem migração × deploy:** colunas novas só existem **depois do deploy** (o
  `migrar()` roda no boot do app). Scripts fora do app (ex.: `promote`) devem
  **tolerar coluna ausente** (padrão `_tem_coluna`). Sequência ao adicionar
  coluna: merge → esperar deploy (~2-4 min) → rodar promote/backfill.
- **Robustez do sync:** cada editora é isolada (uma falha não derruba o run); a
  conexão Postgres é reaberta antes de cada operação de banco (o Neon derruba
  conexões ociosas durante os minutos de scraping); os steps usam `pipefail` para
  não mascarar erro.
- Rede do ambiente de dev pode **bloquear os sites das editoras** — inspecione
  páginas via `dump_url` no workflow, não localmente.

## Status atual (aprox.)

- Editora 34: ~800 livros, ~634 com autor.
- Descrições (sinopses): ~2.450 obras preenchidas (~87% do catálogo).
- Companhia das Letras: coleta migrada de `collect_via_categoria_playwright`
  (Chromium + scrape de cada página de livro, ~35% de falha por página) para
  `collect_via_categoria_json` — POST direto na API JSON por trás do grid de
  categoria (`action=buscar&categoria=...&pg=N`, ver diagnóstico abaixo), que
  já devolve título/autor(es)/link estruturados sem precisar de browser nem de
  uma segunda requisição por livro. Cobre as ~16 páginas × 218 categorias do
  catálogo (bem além do teto anterior de 1.366 candidatos via HTML).

## Próximos passos possíveis

- **Record/Sextante (Shopify):** achar o ISBN em outro campo (tags/metafields/
  página do produto) — hoje entram sem ISBN e o `promote` os ignora.
- **Intrínseca:** descobrir por que a coleta retorna 0.
- **Companhia das Letras — diagnóstico do platô (~255), feito via `dump_url`
  no workflow (rede aberta; o sandbox de dev bloqueia o site):**
  - "Communiplex" é só a agência que hospeda/desenvolve o site (aparece num
    comentário HTML em toda resposta) — **não é uma plataforma/API conhecida**.
    Shopify e VTEX voltam HTML puro (não JSON): não achamos API REST exposta.
  - A **home** (~210KB) tem o mega-menu "COMPRE POR CATEGORIAS" inteiro em
    HTML estático — 256 dos 433 links são `/Busca?categoria=...`. Testamos
    seguir esses links (ignorando de propósito o `Disallow: /Busca` do
    robots.txt) esperando estourar o platô — **piorou**: só 131 livros depois
    de visitar as 250 páginas de listagem permitidas por execução (contra o
    platô de ~255). Causa: a **página de resultado** de `/Busca?categoria=...`
    (diferente do menu) vem com template não renderizado no HTML bruto (ex.:
    literalmente `"{{ extras.anoMin }}"`, sintaxe Angular) — o grid de livros
    daquela página é montado via JS/AJAX depois do load, então `requests` só
    baixa a casca vazia. Ou seja: a intuição antiga de "catálogo carrega via
    JS" era certa, só errava o ONDE (não é a home, é o resultado da busca).
    **Revertido** (`harvest_links()` voltou a descartar `/busca` como antes).
  - Alternativa ainda não resolvida: páginas `/Selo/{nome}` (imprint),
    linkadas em "Navegue por selos" na home, já são reconhecidas como listagem
    pelo crawler (`selo` está em `LISTING_TERMS`), sem esbarrar no robots.txt.
    Mas uma requisição direta a `/Selo/Companhia+das+Letrinhas` devolve
    `"Erro: Selo inválido"` (19 bytes) mesmo com Referer e cookies de sessão
    persistidos (`requests.Session`, mantido em `fetch_url`/`SESSION` — ganho
    real independente do resto). Não decifrado: token/nonce por requisição?
    nome de selo diferente do esperado? Vale testar outro selo (`/Selo/
    Escarlate`) ou inspecionar a Network tab de uma navegação real.
  - **Primeira solução (superada):** `collect_via_categoria_playwright()`, com
    Chromium headless SÓ pra renderizar `/Busca?categoria=...` e extrair os
    links `/livro/{isbn}/...` do DOM, mais um `requests` por livro pra pegar
    título/autor/ISBN da página. Achou 1.366 candidatos (218 categorias), mas
    ~35% das páginas de livro falhavam no fetch e a cobertura de autor ficou
    baixíssima (1/171 na amostra) — a extração genérica não reconhece o
    padrão de autor do site.
  - **Resolvido de vez:** `diagnosticar_paginacao_categoria()` (captura de
    chamadas xhr/fetch via Playwright) revelou que o grid da página de
    categoria é alimentado por um POST pra ela mesma
    (`action=buscar&categoria=...&pg=N&anoMin=...&anoMax=...&idadeMax=18&
    ordem=cronologica`) que devolve `{total, pp, totalPages, livros: [...]}`
    com cada livro JÁ estruturado (`titulo`, `autores: [{nome}]`, `link` com o
    ISBN embutido, `selo`, `capa`). `collect_via_categoria_json()` substitui o
    Playwright por esse POST direto via `requests`/`SESSION` — sem Chromium,
    sem segunda requisição por livro, e com autor de verdade em praticamente
    100% dos casos (vem pronto no JSON). Isso também torna moot a
    investigação de `/Selo/{nome}` acima. Nota de codificação: os hrefs de
    categoria na home usam Latin-1 (`%E7`=ç, `%F3`=ó) mas o corpo do POST
    espera UTF-8 — `_categoria_valor()` decodifica a URL em Latin-1 antes de
    reenviar no POST (que o `requests` codifica em UTF-8 por padrão).
- **Sinopse da Editora 34:** se faltar cobertura, extrator dedicado (a sinopse
  está no `h1.parent`, depois dos metadados — mesma técnica do autor).

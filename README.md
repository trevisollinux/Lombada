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

| slug | método | observações |
|---|---|---|
| `cia_das_letras` | `["sitemap","categoria_js","html"]` | Sem sitemap → categoria via Playwright (resolve o platô de ~255, ver "Status atual"), com fallback pro crawl HTML. |
| `editora_34` | `id_range` 1–3000 | ~800 livros. Sem JSON-LD/meta; autor e sinopse ficam no bloco do `<h1>` (extrator dedicado `autor_editora34()`). |
| `record`, `sextante` | `auto` → Shopify | **Resolvido:** ISBN vinha vazio (`record` só tinha 19/3920 promovidos; `sextante` 1/732). `collect_via_shopify` cai em cascata: `barcode` → `sku` da variante → varredura da descrição → endpoint de produto único (`/products/{handle}.json` — algumas lojas, ex. sextante, omitem `barcode` da listagem em lote mas incluem no produto único) → ISBN embutido na URL. |
| `todavia`, `autentica` | `auto` → sitemap | Boa cobertura, com ISBN. |
| `intrinseca` | `auto` | Boa cobertura (~1370 registros, ~98% com ISBN) — a nota antiga de "coleta 0" está desatualizada. |

## Workflows (aba Actions)

- **Sync publisher source records** (`.github/workflows/sync-publishers.yml`):
  raspa → `source_records` e promove. Inputs: `dry_run`, `diagnose`, `dump_url`,
  `max_urls`, `offset`, `slugs`, `sleep_seconds`. Tem **cron horário** e um
  **concurrency group `sync-publishers`**.
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

- **Concurrency do Actions:** o grupo `sync-publishers` mantém só **1 run
  pending**; disparar outro **cancela o pending anterior**. Dispare **um sync por
  vez** e espere terminar. (`promote-catalog` é outro grupo, roda em paralelo.)
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
- Companhia das Letras: **1.366 livros candidatos** descobertos (era platô de
  ~255) — ver diagnóstico e solução abaixo (`collect_via_categoria_playwright`).
  Ainda por gravar de fato (rodado só em `dry_run`); e cobertura de autor nas
  páginas de livro dessa editora ficou baixa (1/171 na amostra) — não
  investigado ainda.

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
  - **Resolvido:** implementado `collect_via_categoria_playwright()`, isolado
    só pra essa editora (não afeta as outras). Usa Chromium headless
    (Playwright) SÓ pra renderizar as páginas `/Busca?categoria=...` e extrair
    os links `/livro/{isbn}/...` do DOM já processado pelo Angular; as páginas
    de livro em si continuam via `requests` normal (são estáticas). Registrado
    como plataforma `"categoria_js"` em `SOURCES`, com fallback pro crawl HTML
    antigo se o Playwright falhar. Testado ao vivo via `workflow_dispatch`
    (`dry_run=true`): **218 páginas de categoria visitadas, 1.366 livros
    candidatos únicos encontrados** — 5x+ o platô anterior. O workflow ganhou
    um passo `playwright install --with-deps chromium` (só usado por essa
    editora, mas roda toda vez que o job dispara).
  - Pendências: cobertura de autor ficou baixa nas páginas de livro dessa
    editora (1/171 na amostra) — não investigado, possivelmente a extração
    genérica de autor não reconhece o padrão específico do site. E `/Selo/
    {nome}` continua retornando `"Erro: Selo inválido"` sem explicação — não
    bloqueante, já que `categoria_js` resolveu o problema principal.
- **Sinopse da Editora 34:** se faltar cobertura, extrator dedicado (a sinopse
  está no `h1.parent`, depois dos metadados — mesma técnica do autor).

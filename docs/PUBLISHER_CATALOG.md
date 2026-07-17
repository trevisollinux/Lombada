# Cadastro de editoras e cobertura dos scrapers

O diretório `data/publishers/*.csv` é a lista operacional de editoras,
grupos, selos e espólios que o Lombada pretende reconhecer.

## O que foi normalizado

- categorias usam identificadores estáveis, sem misturar português europeu e brasileiro;
- o foco editorial foi reescrito em tom informativo;
- `status` separa editoras ativas, históricas e nomes ainda não confirmados;
- `entity_type` diferencia editora, grupo, selo, rede e editora universitária;
- aliases e nomes anteriores ajudam a casar edições antigas;
- os campos de scraping guardam a estratégia de cobertura sem confundir metadados
  editoriais com configuração do crawler.

Editoras históricas continuam no cadastro para classificação e busca, mas nunca
são enviadas ao scraper de sites oficiais.

## Campos principais

| Campo | Uso |
|---|---|
| `slug` | identificador estável da fonte |
| `name` | nome canônico mostrado pelo produto |
| `aliases` | grafias, marcas e nomes usados em edições |
| `previous_names` | nomes anteriores confirmados |
| `category` | categoria normalizada |
| `focus` | resumo editorial neutro |
| `status` | `active`, `historical` ou `unknown` |
| `entity_type` | tipo da organização editorial |
| `scrape_enabled` | permite transformar o registro em fonte do crawler |
| `base_url` | raiz candidata do site oficial |
| `url_status` | `candidate`, `missing` ou estado futuro validado |
| `group` | shard usado no GitHub Actions |
| `priority` | prioridade operacional de 1 a 3 |

## Como testar as novas fontes

O workflow **Diagnose publisher catalog** é manual e nasce em modo seguro:

- `diagnose=true` testa home, robots.txt, Shopify, VTEX e sitemaps;
- `dry_run=true` permite coletar amostras sem escrever no banco;
- `group=all` divide a lista em oito jobs paralelos;
- `slugs` testa uma ou mais editoras específicas e vence o filtro de grupo.

Fluxo recomendado para cada nova fonte:

1. executar `diagnose=true`;
2. corrigir URL ou plataforma quando necessário;
3. executar `diagnose=false` e `dry_run=true`;
4. conferir ISBN, autor, capa e quantidade de páginas;
5. somente então executar com `dry_run=false`;
6. mover fontes estáveis para um workflow agendado ou criar configuração
   especializada no `sync_publishers.py`.

## Relação com o scraper principal

`scripts/sync_publishers_catalog.py` carrega os arquivos CSV e acrescenta somente fontes
ativas e habilitadas a `sync_publishers.SOURCES`.

Quando um slug já existe no scraper principal, a configuração especializada
vence e não é duplicada. Isso preserva adaptações como `id_range`,
`categoria_json` e grupos já agendados.

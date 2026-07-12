# L2-020 — Sessões de progresso, sheet "Li mais" e leitura atual na home

Parent: #277 (EPIC 2 — Ritual de progresso; PRs 2–5 do primeiro pacote)

Esta branch implementa o ritual de progresso atrás das flags `progress_sessions`
e `home_ritual`, ambas desligadas por padrão.

## Entregas

- [x] Campos aditivos de sessão no diário: `origem` (`diario`/`li_mais`) e
  `paginas_delta` (nulo quando não dá pra estimar). Migração idempotente via
  `_add_column_if_missing`, compatível com SQLite e PostgreSQL.
- [x] Endpoint `GET /api/leitura/{id}/progresso` atrás de `progress_sessions`:
  página atual, porcentagem, restantes, sessões, delta da última sessão,
  páginas nos últimos 7 dias e previsão em dias. Flag desligada devolve 404.
- [x] Sheet "Li mais": um campo (página ou %, conforme o histórico da leitura),
  salva pelo endpoint de diário existente com `origem: li_mais`; o caminho
  antigo ("atualizar progresso" → diário completo) permanece acessível na
  própria sheet e no card.
- [x] Card "Continue sua leitura" na home atrás de `home_ritual`, com a linha
  de sessão ("+N páginas na última sessão · N nos últimos 7 dias") vinda do
  resumo.
- [x] `index.html` passa a carregar `feature-flags.js` e `product-analytics.js`
  antes do `app.js` (pré-requisito documentado da primeira experiência gated);
  os testes-guarda de L2-003/L2-010 foram atualizados para o novo contrato.
- [x] Evento `progress_logged` (`source: quick_action`) no salvar da sheet —
  só persiste com `product_analytics` ligada.
- [x] Strings em pt-BR/EN/ES; `prefers-reduced-motion` desliga a animação da
  sheet; estados de erro/validação com toast e foco de volta no campo.
- [x] Testes: flag desligada (endpoint 404, diário intacto), resumo com flag
  ligada, sanitização de origem, delta entre sessões, delta nulo, privacidade
  entre usuários e resumo sem entradas (`tests/test_progress_sessions.py`).

## Decisões

- `paginas_delta` é calculado só na criação (a página efetiva usa a mesma
  ordem de preferência do front: página explícita → capítulo→página do
  sumário → porcentagem sobre o total). Editar uma entrada antiga não recalcula
  deltas vizinhos nesta fase.
- O resumo calcula `delta_ultima` ao vivo (não depende da coluna preenchida),
  então funciona para entradas antigas sem backfill.
- Com `home_ritual` desligada a home fica exatamente como era — o container
  `#lendoAgora` existe no HTML mas só recebe conteúdo com a flag ligada.
- Sem push, sem streak: a única recompensa é o delta após o registro real.

## Rollback

Desligar `FF_PROGRESS_SESSIONS` e/ou `FF_HOME_RITUAL` no Railway restaura o
comportamento anterior na hora, sem deploy. As colunas novas são aditivas e
ignoradas pelo código anterior (rollback de código também é seguro).

## Critério de saída

Com as duas flags desligadas ou ausentes, o aplicativo mantém exatamente o
comportamento atual (verificado em navegador nos dois estados). Suíte local:
126 passed.

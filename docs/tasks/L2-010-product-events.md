# L2-010 — Eventos de produto e cliente de analytics

Issue: #289 · Parent: #277

Esta branch implementa uma camada mínima e privada de eventos de produto, protegida por `product_analytics`.

## Entregas

- [x] Modelo aditivo `ProductEvent`.
- [x] Endpoint de ingestão atrás de feature flag.
- [x] Allowlist de eventos e propriedades.
- [x] Rejeição de texto livre e dados privados.
- [x] Rate limit por sessão/IP sem persistir IP ou User-Agent.
- [x] Cliente frontend isolado e fail-safe.
- [x] Retenção de 90 dias documentada e script com dry-run.
- [x] Testes para flag ligada/desligada e contas anônimas/conectadas.
- [x] Usuários demo ignorados e reenvios idempotentes.
- [x] CI verde e revisão final.

## Decisões

- Nenhuma coleta foi ativada neste PR.
- `index.html` continua sem carregar os scripts de flags e analytics.
- O endpoint valida eventos mesmo quando a flag está desligada, mas não persiste.
- Falha de banco ou tabela ainda não criada resulta em descarte HTTP 202.
- Título, autor, ISBN, busca, crítica, diário, bio, comentário, email, handle e IP não fazem parte do schema.

## Critério de saída

Com `FF_PRODUCT_ANALYTICS` desligada ou ausente, nenhum evento é persistido e o aplicativo mantém exatamente o comportamento atual. A suíte completa passou no GitHub Actions.

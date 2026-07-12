# L2-010 — Eventos de produto e cliente de analytics

Issue: #289 · Parent: #277

Esta branch implementa uma camada mínima e privada de eventos de produto, protegida por `product_analytics`.

## Entregas

- [ ] Modelo aditivo `ProductEvent`.
- [ ] Endpoint de ingestão atrás de feature flag.
- [ ] Allowlist de eventos e propriedades.
- [ ] Rejeição de texto livre e dados privados.
- [ ] Rate limit por sessão/IP.
- [ ] Cliente frontend isolado e fail-safe.
- [ ] Retenção de 90 dias documentada.
- [ ] Testes para flag ligada/desligada e contas anônimas/conectadas.
- [ ] CI verde e revisão final.

## Critério de saída

Com `FF_PRODUCT_ANALYTICS` desligada ou ausente, nenhum evento é persistido e o aplicativo mantém exatamente o comportamento atual.

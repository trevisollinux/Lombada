# L2-003 — Feature flags para rollout reversível

Issue: #287 · Parent: #277

Esta branch implementa a fundação central de feature flags do Lombada 2.0.

## Entregas

- [ ] Registro central de flags públicas e internas.
- [ ] Valores por ambiente com defaults desligados.
- [ ] Endpoint público allowlisted.
- [ ] Helper de frontend resiliente a falhas.
- [ ] Testes de parsing, exposição e fallback.
- [ ] Documentação operacional no Railway.
- [ ] CI verde e revisão final.

## Critério de saída

Com todas as flags desligadas ou ausentes, o aplicativo deve manter exatamente o comportamento atual.

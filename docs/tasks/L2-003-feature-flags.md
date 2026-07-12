# L2-003 — Feature flags para rollout reversível

Issue: #287 · Parent: #277

Esta branch implementa a fundação central de feature flags do Lombada 2.0.

## Entregas

- [x] Registro central de flags públicas e internas.
- [x] Valores por ambiente com defaults desligados.
- [x] Endpoint público allowlisted.
- [x] Helper de frontend resiliente a falhas.
- [x] Testes de parsing, exposição e fallback.
- [x] Documentação operacional no Railway.
- [x] CI verde e revisão final.

## Decisões

- Nenhuma funcionalidade nova foi ativada.
- O helper de frontend existe como arquivo isolado, mas ainda não é carregado pelo HTML atual.
- A primeira experiência gated deverá incluir o helper antes do próprio código.
- Flags ausentes, inválidas ou indisponíveis permanecem desligadas.
- A flag interna de admin nunca aparece no endpoint público.

## Critério de saída

Com todas as flags desligadas ou ausentes, o aplicativo mantém exatamente o comportamento atual. A suíte completa passou no GitHub Actions.

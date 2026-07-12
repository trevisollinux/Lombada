# L2-001 — Segurança de entrega

Issue: #283 · Parent: #277

Esta branch implementa baseline documentado, regressão dos fluxos críticos, política de migrações aditivas e procedimento de rollback.

## Entregas

- [x] Política de migrações aditivas em `docs/MIGRATIONS.md`.
- [x] Procedimento de rollback em `docs/ROLLBACK.md`.
- [x] Checklist automatizado e manual em `docs/SMOKE_TESTS.md`.
- [x] Template obrigatório de PR com banco, privacidade, rollout e rollback.
- [x] Contratos automatizados em `tests/test_delivery_safety.py`.
- [x] Suíte do GitHub Actions concluída com sucesso: 143 testes.
- [x] Revisão final concluída e merge autorizado.

## Correções de regressão incluídas

- manifesto PWA voltou a declarar ícones PNG 192 × 192 e 512 × 512;
- CI alinhado ao Python 3.12 e passou a preservar relatório de falha;
- SQLite de testes deixou de estourar o parser no fold de acentos;
- filtro de gênero passou a excluir obras sem gênero confirmado, conforme contrato estrito.

## Critério de saída

- testes e documentação reproduzíveis;
- nenhuma operação destrutiva de banco;
- rollback por flag/revert documentado;
- smoke proporcional ao risco registrado em cada PR;
- comportamento de busca protegido por regressão automatizada.

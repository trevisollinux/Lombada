# L2-001 — Segurança de entrega

Issue: #283 · Parent: #277

Esta branch implementa baseline documentado, regressão dos fluxos críticos, política de migrações aditivas e procedimento de rollback.

## Entregas

- [x] Política de migrações aditivas em `docs/MIGRATIONS.md`.
- [x] Procedimento de rollback em `docs/ROLLBACK.md`.
- [x] Checklist automatizado e manual em `docs/SMOKE_TESTS.md`.
- [x] Template obrigatório de PR com banco, privacidade, rollout e rollback.
- [x] Contratos automatizados em `tests/test_delivery_safety.py`.
- [ ] Suíte do GitHub Actions concluída com sucesso.
- [ ] Revisão final e merge.

## Critério de saída

- testes e documentação reproduzíveis;
- nenhuma mudança funcional ou visual;
- nenhuma operação destrutiva de banco;
- rollback por flag/revert documentado;
- smoke proporcional ao risco registrado em cada PR.

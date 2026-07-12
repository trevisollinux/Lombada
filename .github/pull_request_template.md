## O que mudou

Descreva a entrega em linguagem objetiva.

## Por que

Explique o problema, a decisão e o impacto esperado.

## Escopo

- Issue/tarefa: #
- ID do backlog: `L2-XXX` ou `N/A`
- Fora de escopo:

## Validação

- [ ] Executei os testes automatizados relevantes.
- [ ] Testei o fluxo afetado em viewport móvel.
- [ ] Verifiquei loading, vazio e erro.
- [ ] Verifiquei tema claro/escuro quando há UI.
- [ ] Verifiquei PT/EN/ES ou documentei o fallback.
- [ ] Verifiquei `prefers-reduced-motion` quando há animação.
- [ ] Registrei evidências/resultados abaixo.

Comandos e resultados:

```text

```

## Banco de dados

- [ ] Este PR não altera banco.
- [ ] A migration é aditiva e idempotente.
- [ ] O código anterior funciona com o esquema novo.
- [ ] Testei banco vazio e banco existente.
- [ ] O backfill é separado, limitado e oferece `dry_run`.
- [ ] Não há `DROP`, `TRUNCATE` ou alteração destrutiva.

Descreva forward migration, backfill e impacto em registros existentes, ou escreva `N/A`:

## Privacidade e segurança

- [ ] Não exponho conteúdo privado em resposta, feed, logs ou analytics.
- [ ] Não adiciono segredo, token ou URL de banco ao repositório/logs.
- [ ] Validei autorização para dados pertencentes a usuário.
- [ ] Considerei rate limit/abuso quando há endpoint de escrita.

## Rollout

- Feature flag: `N/A` / nome da flag
- Default seguro:
- Sequência de ativação:
- Métricas/erros a observar:

## Rollback

Explique como desligar ou reverter esta mudança sem apagar dados:

## Smoke pós-deploy

Selecione os blocos de `docs/SMOKE_TESTS.md` que serão executados:

- [ ] saúde/versionamento
- [ ] app/navegação
- [ ] busca/catálogo
- [ ] leitura/estante
- [ ] diário/progresso
- [ ] conta/autenticação
- [ ] social
- [ ] cards/retrospectiva
- [ ] PWA

# Política de migrações do Lombada

Esta política vale para toda mudança de banco a partir do projeto Lombada 2.0.

## Objetivo

Permitir que código novo e antigo convivam com o mesmo banco durante deploy, rollback e restart, sem perda de dados nem indisponibilidade causada por DDL destrutivo.

## Regras obrigatórias

1. **Migrações são aditivas.** Nesta fase, é permitido criar tabela, coluna opcional, índice ou constraint que não invalide registros existentes.
2. **Não usar `DROP`, `TRUNCATE` ou mudança destrutiva de tipo** em deploy normal.
3. **Colunas novas devem aceitar `NULL` ou ter default compatível** até que todos os registros estejam preenchidos e o código antigo não dependa delas.
4. **Toda migration deve ser idempotente.** Reexecutar o boot ou o script não pode falhar nem duplicar estruturas.
5. **Backfill não roda implicitamente no caminho crítico.** Backfills grandes devem ter script separado, modo `dry_run`, limite/lote e logs de contagem.
6. **Código novo tolera esquema parcialmente migrado** quando scripts externos podem rodar antes do deploy completo.
7. **Código antigo precisa continuar funcionando com banco novo.** O rollback normal é de código, não de banco.
8. **Índices devem ser justificados por consulta real** e, quando o volume exigir, criados de forma que minimize bloqueio.
9. **Nenhuma migration pode apagar ou reescrever conteúdo do usuário** sem plano específico aprovado e backup restaurável.
10. **Toda mudança de banco exige teste em SQLite e PostgreSQL quando houver diferença de dialeto.**

## Padrão no repositório

O projeto usa `SQLModel.metadata.create_all(engine)` e `migrar()` em `models.py`, sem Alembic. Portanto:

- novas tabelas são declaradas como modelos SQLModel;
- colunas retroativas usam `_add_column_if_missing`;
- índices/constraints usam DDL com `IF NOT EXISTS` ou checagem equivalente;
- diferenças entre PostgreSQL e SQLite devem ser tratadas explicitamente;
- erros esperados de estrutura existente podem ser ignorados apenas quando identificados de forma restrita.

## Fluxo de uma alteração de banco

1. Criar backup ou confirmar ponto restaurável conforme `docs/ROLLBACK.md`.
2. Declarar no PR:
   - mudança forward;
   - impacto em registros existentes;
   - backfill, se houver;
   - compatibilidade do código anterior;
   - rollback de código;
   - métricas/consultas a observar.
3. Adicionar testes de criação em banco vazio e migração sobre banco existente.
4. Mesclar e aguardar o deploy concluir.
5. Verificar `/healthz`, `/readyz`, `/api/version` e o fluxo afetado.
6. Só depois executar backfill separado, se necessário.

## Backfill seguro

Todo script de backfill deve:

- exigir `DATABASE_URL` explícita;
- recusar execução acidental sem confirmação adequada;
- oferecer `--dry-run` por padrão ou equivalente;
- aceitar limite/lote;
- ser idempotente;
- registrar contagens, nunca segredos ou conteúdo privado;
- poder ser interrompido e retomado;
- não bloquear o boot da aplicação.

## Rollback

O rollback padrão é:

1. desligar a funcionalidade por feature flag, quando disponível;
2. reverter o PR ou redeployar o commit anterior;
3. manter colunas/tabelas aditivas no banco;
4. investigar e corrigir em uma nova branch.

Remover estrutura do banco é uma operação separada, posterior e deliberada — nunca requisito para restaurar o aplicativo.

## Checklist para revisão

- [ ] A migration é aditiva e idempotente.
- [ ] Não há `DROP`, `TRUNCATE` ou alteração destrutiva.
- [ ] O código anterior funciona com o novo esquema.
- [ ] Banco vazio e banco existente foram testados.
- [ ] Backfill é separado, controlado e reversível operacionalmente.
- [ ] O PR descreve rollback e verificação pós-deploy.
- [ ] Dados privados não aparecem em logs.

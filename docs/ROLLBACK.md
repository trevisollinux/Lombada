# Rollback e recuperação do Lombada

Este guia descreve como retornar o aplicativo a um estado funcional quando um deploy apresenta regressão.

## Referência preservada

O início do projeto Lombada 2.0 foi preservado em:

- baseline histórico: `da505b3df7ac530b0420998f43c8938f00f9f246`;
- branch de referência: `baseline/pre-retencao-v2-2026-07-11`.

Essa branch é uma referência histórica. O rollback normal deve usar o último commit comprovadamente saudável, que pode ser mais recente que esse baseline.

## Princípio

O deploy de produção acompanha merges na `main`. Portanto, toda mudança funcional deve entrar por PR pequeno, observável e reversível.

A ordem preferida de mitigação é:

1. **desligar a feature flag**, quando existir;
2. **reverter o PR problemático** na `main`;
3. **aguardar o redeploy automático**;
4. **executar smoke pós-deploy**;
5. somente em caso de corrupção confirmada, considerar restauração de banco.

## Quando fazer rollback imediato

- falha de login ou sessão;
- registro, edição ou exclusão de leitura bloqueados;
- diário/progresso perdendo ou duplicando registros;
- `readyz` retornando 503 depois da janela normal de deploy;
- erro 5xx recorrente em fluxo crítico;
- migration impedindo boot;
- aumento anormal de OOM/restarts;
- exposição de conteúdo privado;
- regressão severa em navegação mobile.

## Rollback de código por PR

1. Identificar o PR e o merge commit suspeitos.
2. Confirmar que não há outro PR dependente já mesclado.
3. Criar um PR de revert do merge commit.
4. Não editar a migration para remover colunas/tabelas aditivas.
5. Mesclar o revert.
6. Acompanhar o deploy.
7. Rodar o checklist em `docs/SMOKE_TESTS.md`.
8. Registrar causa, impacto e decisão na issue original.

## Rollback por feature flag

Quando a funcionalidade estiver protegida por flag:

1. alterar a variável correspondente no Railway;
2. manter o default seguro documentado;
3. verificar que o frontend voltou ao fluxo anterior;
4. confirmar que dados já gravados permanecem íntegros;
5. abrir correção em nova branch — não reaproveitar produção como ambiente de teste.

## Banco de dados

Migrações da fase Lombada 2.0 devem ser aditivas. Assim, o código anterior deve funcionar mesmo que tabelas ou colunas novas permaneçam no banco.

Não executar `DROP`, `TRUNCATE` ou restauração de banco apenas para reverter uma interface.

Restauração de banco só é apropriada quando há evidência de:

- perda ou corrupção de dados;
- alteração destrutiva executada por engano;
- backfill incorreto impossível de corrigir de forma idempotente.

Antes de restaurar:

- interromper escritas ou colocar o serviço em manutenção;
- preservar um dump do estado problemático para investigação;
- validar o backup em banco temporário;
- documentar o ponto no tempo escolhido;
- confirmar o impacto sobre registros criados após esse ponto.

## Verificação pós-rollback

Obrigatório:

```bash
curl -fsS https://SEU-DOMINIO/healthz
curl -fsS https://SEU-DOMINIO/readyz
curl -fsS https://SEU-DOMINIO/api/version
```

Depois, executar os fluxos críticos descritos em `docs/SMOKE_TESTS.md`.

## Registro do incidente

A issue deve conter:

- horário do primeiro sinal;
- versão/commit afetado;
- sintomas e usuários impactados;
- ação de mitigação;
- horário da recuperação;
- causa raiz, quando conhecida;
- teste adicionado para evitar recorrência.

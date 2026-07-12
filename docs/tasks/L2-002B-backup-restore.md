# L2-002B — Backup e restauração verificável do PostgreSQL

Issue: #300 · Parent: #277 · PR: #303

## Objetivo

Fornecer um procedimento operacional seguro para gerar um backup custom do PostgreSQL do Lombada, restaurá-lo somente em um banco temporário explicitamente autorizado e verificar a cópia por contagens agregadas.

A tarefa substitui a issue #285, que foi fechada sem implementação para manter apenas uma tarefa ativa por vez.

## Entregas técnicas

- [x] Utilitário único em `scripts/postgres_ops.py`.
- [x] Comando `backup` usando `pg_dump --format=custom`.
- [x] Validação do arquivo com `pg_restore --list`.
- [x] Permissão local `0600` no dump e `0700` na pasta quando suportado.
- [x] SHA-256, tamanho e duração na saída estruturada.
- [x] Credenciais apenas em variáveis `PG*` dos subprocessos.
- [x] Remoção de `DATABASE_URL` e `RESTORE_DATABASE_URL` do ambiente herdado.
- [x] Bloqueio quando origem e destino apontam para o mesmo banco.
- [x] Confirmação `RESTORE_CONFIRM=RESTORE_TEMP_DATABASE`.
- [x] Confirmação adicional pelo nome exato em `RESTORE_ALLOWED_DATABASE`.
- [x] Restore com `--clean --if-exists --no-owner --no-privileges --exit-on-error`.
- [x] Comparação de todas as tabelas públicas por `count(*)`.
- [x] Relatório somente com nomes de tabelas e números agregados.
- [x] Documentação operacional em `docs/BACKUP_RESTORE.md`.
- [x] Dumps ignorados pelo Git.
- [x] Testes unitários sem conexão com banco real.

## Guardrails

O utilitário não aceita URL por argumento. As conexões são lidas exclusivamente de:

- `DATABASE_URL`: origem;
- `RESTORE_DATABASE_URL`: destino temporário.

O restore somente prossegue quando:

1. origem e destino são diferentes;
2. `RESTORE_CONFIRM` possui o valor literal esperado;
3. `RESTORE_ALLOWED_DATABASE` corresponde exatamente ao banco da URL temporária;
4. o arquivo existe, não está vazio e é reconhecido por `pg_restore`.

Mensagens de erro não reproduzem automaticamente o `stderr` dos clientes PostgreSQL, reduzindo o risco de detalhes de conexão aparecerem em logs.

## Verificação automática

Os testes cobrem:

- parsing seguro da URL;
- remoção das URLs do ambiente dos subprocessos;
- ausência de senha e URL nos argumentos;
- bloqueio de origem e destino iguais;
- confirmação ausente ou incorreta;
- banco temporário não autorizado;
- permissões do arquivo de backup;
- comando de restore com destino correto;
- divergência de contagens;
- rejeição de identificador de tabela inesperado.

## Exercício operacional real

- [ ] Gerar um dump do Railway com credencial segura.
- [ ] Criar um PostgreSQL temporário e descartável.
- [ ] Restaurar o dump nesse banco.
- [ ] Confirmar `matching: true` nas contagens.
- [ ] Registrar duração real de backup e restore em local privado.
- [ ] Excluir o serviço temporário e o arquivo conforme a política de retenção.

Esses itens não são executados pelo CI e não podem ser marcados como concluídos sem acesso operacional às credenciais e ao banco temporário.

## Impacto no deploy

Nenhum. O script não é importado pela aplicação, não altera startup, rotas, schema ou dados. O deploy do código apenas disponibiliza os arquivos no repositório.

## Rollback

Remover:

- `scripts/postgres_ops.py`;
- `tests/test_postgres_ops.py`;
- `docs/BACKUP_RESTORE.md`;
- este documento;
- regras de dumps adicionadas ao `.gitignore`.

Não existe migration reversa nem ação de banco associada ao rollback.

## Critério de saída

O código pode ser mesclado quando a suíte estiver verde. A issue permanece aberta até o exercício real de restauração ser executado e registrado sem dados sensíveis.
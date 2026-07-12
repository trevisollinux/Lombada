# Backup e restauração do PostgreSQL

Este procedimento protege o banco do Lombada antes de mudanças de maior risco e permite verificar um backup em um PostgreSQL temporário sem expor conteúdo individual.

O utilitário oficial é:

```bash
python scripts/postgres_ops.py --help
```

Ele não roda no deploy, não altera o startup da aplicação e nunca é executado pelo CI contra um banco real.

## Princípios de segurança

- `DATABASE_URL` representa somente a origem.
- `RESTORE_DATABASE_URL` representa somente o banco temporário.
- URLs e senhas não entram nos argumentos de `pg_dump`, `pg_restore` ou `psql`.
- As ferramentas recebem `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` e `PGDATABASE` apenas no ambiente do subprocesso.
- A saída não imprime URL, host, usuário ou senha.
- O restore é recusado quando origem e destino apontam para o mesmo host, porta e banco.
- O restore exige duas confirmações independentes.
- A verificação lê somente nomes de tabelas e `count(*)`.
- O backup local recebe permissão `0600`; a pasta recebe `0700` quando o sistema permitir.

## Pré-requisitos

- Python 3.12 ou compatível.
- Cliente PostgreSQL contendo `pg_dump`, `pg_restore` e `psql`.
- A versão principal das ferramentas deve ser igual ou superior à versão do servidor PostgreSQL.
- Espaço em disco suficiente para o arquivo custom.
- Um PostgreSQL temporário vazio e descartável para o exercício de restauração.

Verifique as ferramentas:

```bash
pg_dump --version
pg_restore --version
psql --version
```

## 1. Gerar backup

Em um shell seguro onde `DATABASE_URL` já esteja disponível:

```bash
python scripts/postgres_ops.py backup
```

Por padrão, o arquivo é criado em:

```text
backups/lombada-AAAAMMDDTHHMMSSZ.dump
```

Outra pasta pode ser informada sem colocar a URL na linha de comando:

```bash
python scripts/postgres_ops.py backup --output-dir /caminho/seguro
```

A operação:

1. valida `DATABASE_URL`;
2. executa `pg_dump` em formato custom;
3. usa `--no-owner` e `--no-privileges` para facilitar restauração temporária;
4. valida o arquivo com `pg_restore --list`;
5. calcula SHA-256;
6. imprime somente caminho, tamanho, hash e duração.

Exemplo estrutural da resposta:

```json
{
  "operation": "backup",
  "file": "backups/lombada-20260712T190000Z.dump",
  "bytes": 123456,
  "sha256": "...",
  "duration_seconds": 4.2
}
```

Os valores reais variam e não devem ser copiados para tickets públicos quando revelarem caminhos internos.

### Usando a URL sem registrá-la no histórico do terminal

Quando a variável não estiver previamente disponível, use leitura silenciosa:

```bash
read -rsp 'DATABASE_URL: ' DATABASE_URL && echo
export DATABASE_URL
python scripts/postgres_ops.py backup
unset DATABASE_URL
```

Não execute `echo $DATABASE_URL`, `env`, `printenv` ou shell com tracing (`set -x`).

## 2. Preparar o banco temporário

Crie um serviço PostgreSQL separado e descartável. Ele não deve ser o serviço usado pelo aplicativo.

Antes de restaurar, confirme manualmente:

- o aplicativo não aponta para esse banco;
- a URL é diferente de `DATABASE_URL`;
- o banco pode ser apagado integralmente;
- não há dados que precisem ser preservados;
- conexões externas não autorizadas estão bloqueadas.

A URL temporária deve entrar em `RESTORE_DATABASE_URL`.

## 3. Configurar os guardrails do restore

O utilitário exige:

```text
RESTORE_CONFIRM=RESTORE_TEMP_DATABASE
RESTORE_ALLOWED_DATABASE=<nome exato do banco na RESTORE_DATABASE_URL>
```

Exemplo com leitura silenciosa das URLs:

```bash
read -rsp 'DATABASE_URL de origem: ' DATABASE_URL && echo
read -rsp 'RESTORE_DATABASE_URL temporária: ' RESTORE_DATABASE_URL && echo
export DATABASE_URL RESTORE_DATABASE_URL
export RESTORE_CONFIRM=RESTORE_TEMP_DATABASE
export RESTORE_ALLOWED_DATABASE=lombada_restore
```

`RESTORE_ALLOWED_DATABASE` precisa corresponder exatamente ao caminho da URL. Para uma URL terminada em `/lombada_restore`, o valor deve ser `lombada_restore`.

Essas confirmações não transformam um banco de produção em destino permitido. O utilitário continuará recusando origem e destino iguais.

## 4. Restaurar e verificar

```bash
python scripts/postgres_ops.py restore \
  --dump backups/lombada-AAAAMMDDTHHMMSSZ.dump
```

A operação:

1. valida o arquivo com `pg_restore --list`;
2. aplica os guardrails de destino;
3. restaura com `--clean --if-exists --no-owner --no-privileges --exit-on-error`;
4. lista as tabelas públicas na origem e no destino;
5. calcula `count(*)` para cada tabela;
6. falha quando uma tabela está ausente ou uma contagem diverge.

A resposta contém somente informações agregadas:

```json
{
  "operation": "restore",
  "tables_checked": 32,
  "matching": true,
  "mismatches": [],
  "duration_seconds": 8.4
}
```

Nenhuma linha de usuário, leitura, crítica ou diário é exibida.

## 5. Repetir somente a verificação

Depois do restore, a comparação pode ser repetida:

```bash
python scripts/postgres_ops.py verify
```

As mesmas confirmações de restore continuam obrigatórias. Isso evita apontar a verificação para um destino não autorizado por engano.

## 6. Evidência do exercício

Registre em local privado:

- data e operador;
- commit testado;
- tamanho e SHA-256 do arquivo;
- duração do backup;
- duração do restore/verificação;
- quantidade de tabelas verificadas;
- resultado `matching`;
- data de descarte do banco temporário e do arquivo local.

Não registre:

- URLs de conexão;
- senha;
- host interno;
- saída de `env`/`printenv`;
- amostras de dados;
- conteúdo de usuários.

## 7. Descarte seguro

Após validar a restauração:

1. remova o serviço PostgreSQL temporário;
2. confirme que nenhuma variável da aplicação aponta para ele;
3. apague a cópia local do dump quando não for necessária;
4. remova as variáveis do shell:

```bash
unset DATABASE_URL RESTORE_DATABASE_URL RESTORE_CONFIRM RESTORE_ALLOWED_DATABASE
```

Arquivos de backup não devem ser commitados, enviados a tickets ou armazenados em pastas sincronizadas sem criptografia e política de retenção.

## 8. Recuperação em incidente

A restauração em produção não deve usar diretamente este comando operacional sem decisão explícita de incidente.

Ordem recomendada:

1. interromper escritas ou colocar a aplicação em manutenção;
2. preservar o banco afetado;
3. selecionar e verificar o hash do backup;
4. restaurar primeiro em ambiente temporário;
5. comparar contagens e executar smoke tests;
6. definir novo banco de produção ou janela controlada de restauração;
7. atualizar `DATABASE_URL` somente após aprovação;
8. acompanhar `/healthz`, `/readyz`, login, busca, estante e diário;
9. documentar RPO e RTO reais do incidente.

Nunca use a existência do script como autorização automática para sobrescrever produção.

## 9. Falhas comuns

### Ferramenta não encontrada

Instale o cliente PostgreSQL apropriado e repita. O script informa apenas o nome da ferramenta ausente.

### Código de saída sem detalhe

Por segurança, o utilitário não reproduz automaticamente `stderr` das ferramentas PostgreSQL. Verifique conectividade e permissões sem habilitar `set -x` ou imprimir variáveis.

### Contagens divergentes

Não promova o banco restaurado. Preserve o temporário para análise, confira a versão das ferramentas, o momento do backup e tabelas criadas depois do dump.

### Origem e destino iguais

Interrompa a operação e crie outro serviço PostgreSQL. Não tente contornar o bloqueio.

## 10. Rollback desta funcionalidade

Os scripts e esta documentação são inteiramente operacionais. Removê-los não exige migration, alteração de schema, restart especial ou limpeza do banco do aplicativo.

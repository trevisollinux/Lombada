# Infra do Lombada (Terraform)

Infra como código do Lombada. Hoje cobre o **Render** (web service + env vars).
**Cloudflare** e **Render Postgres** estão escritos e **comentados** — habilite
quando o domínio próprio existir / se o banco for gerenciado pelo Render.

Os recursos **já existem** no Render, então o fluxo é **create + import**: a
config aqui adota o que já está lá, sem recriar nem sobrescrever segredos.

## Arquivos

| Arquivo | O quê |
|---|---|
| `versions.tf` | versão do TF e providers (cloudflare comentado) |
| `backend.tf` | state remoto no Cloudflare R2 |
| `providers.tf` | config dos providers |
| `variables.tf` | inputs (secrets marcados `sensitive`) |
| `render.tf` | web service + env vars (postgres/custom domain comentados) |
| `imports.tf` | blocos `import` dos recursos já existentes |
| `dns.tf` | Cloudflare — tudo comentado |
| `outputs.tf` | ids/urls úteis |
| `terraform.tfvars.example` | modelo; copie para `terraform.tfvars` (gitignored) |

## Primeira adoção (rodar uma vez, local)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # preencha os valores reais
# edite imports.tf: troque srv-REPLACE_ME pelo id real do serviço no Render

terraform init
terraform plan     # deve mostrar "1 to import" e nenhuma recriação
terraform apply    # adota o recurso no state
```

Se o plan quiser **recriar** algo em vez de importar, pare e ajuste a config
até bater. `terraform plan -generate-config-out=generated.tf` ajuda a comparar
com o estado real do Render.

Depois de importado, o CI cuida do resto.

## CI (`.github/workflows/terraform.yml`)

- **PR** que toca `infra/**` → `fmt` + `validate` + `plan` (comentado no PR).
- **push na main** → `apply`, protegido pelo environment `production`.

### Segredos do GitHub Actions

Repo → Settings → Secrets and variables → Actions:

**Secrets**
- `RENDER_API_KEY`, `RENDER_OWNER_ID`
- `TF_DATABASE_URL`, `TF_SECRET_KEY`
- opcionais: `TF_GOOGLE_CLIENT_ID`, `TF_GOOGLE_CLIENT_SECRET`,
  `TF_GOOGLE_BOOKS_API_KEY`, `TF_HARDCOVER_API_KEY`, `TF_PENGUIN_API_KEY`,
  `TF_ME_TOKEN`, `TF_RECON_TOKEN`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (token do R2, para o state)

**Variables**
- `TF_ADMIN_EMAILS`

Proteja o environment `production` (Settings → Environments) com required
reviewers se quiser aprovação manual antes de cada `apply`.

## Não quer segredos no Terraform?

Se preferir manter os valores dos segredos só no dashboard do Render, descomente
o bloco `lifecycle { ignore_changes = [env_vars] }` em `render.tf` e deixe as
variáveis secretas vazias. O Terraform passa a gerenciar só o serviço, não os
valores das env vars.

## State no R2

`backend.tf` aponta para um bucket R2. Antes do primeiro `init` remoto: crie o
bucket `lombada-tfstate`, gere um token R2 e troque `<R2_ACCOUNT_ID>`. O account
id não é segredo; as chaves de acesso vão nos secrets do Actions.

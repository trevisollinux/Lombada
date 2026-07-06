# Infra do Lombada (Terraform)

Infra como código do Lombada. Hoje cobre o **Render** (web service + env vars),
com **state e execução remota no Terraform Cloud**. **Cloudflare** e **Render
Postgres** estão escritos e **comentados** — habilite quando o domínio próprio
existir / se o banco for gerenciado pelo Render.

Os recursos **já existem** no Render, então o fluxo é **create + import**: a
config aqui adota o que já está lá, sem recriar nem sobrescrever segredos.

## Stack de tooling

- **Compute/DB**: Render (web service + Postgres).
- **State + runs**: Terraform Cloud (HCP Terraform) — bloco `cloud {}` em
  `versions.tf`. Não há `backend.tf`.
- **Segredos**: variáveis do workspace no TFC (sensitive), não no GitHub.

## Arquivos

| Arquivo | O quê |
|---|---|
| `versions.tf` | versão do TF, providers e bloco `cloud {}` (state/runs no TFC) |
| `providers.tf` | config dos providers |
| `variables.tf` | inputs (secrets marcados `sensitive`) |
| `render.tf` | web service + env vars (postgres/custom domain comentados) |
| `imports.tf` | blocos `import` dos recursos já existentes |
| `dns.tf` | Cloudflare — tudo comentado |
| `outputs.tf` | ids/urls úteis |
| `terraform.tfvars.example` | modelo; copie para `terraform.tfvars` (gitignored) |

## Setup do Terraform Cloud (uma vez)

1. Crie a organização no https://app.terraform.io e troque `SEU_ORG_TFC` em
   `versions.tf`.
2. O workspace `lombada-prod` é criado no primeiro `init` (execução remota).
3. No workspace, em **Variables**, cadastre as **Terraform variables** (não env):
   - `render_api_key` (sensitive), `render_owner_id`
   - `database_url` (sensitive), `secret_key` (sensitive)
   - opcionais: `google_client_id/secret`, `google_books_api_key`,
     `hardcover_api_key`, `penguin_api_key`, `me_token`, `recon_token`,
     `admin_emails`
4. Gere um **API token** (User/Team settings → Tokens) e guarde para o CI.

Assim os segredos vivem no TFC, com o run/plan executando remotamente — o
GitHub não guarda nenhum segredo da aplicação.

## Primeira adoção (rodar uma vez, local)

```bash
cd infra
# edite imports.tf: troque srv-REPLACE_ME pelo id real do serviço no Render
# faça login no TFC: terraform login

terraform init
terraform plan     # roda no TFC; deve mostrar "1 to import" e nenhuma recriação
terraform apply    # adota o recurso no state remoto
```

Se o plan quiser **recriar** algo em vez de importar, pare e ajuste a config
até bater. `terraform plan -generate-config-out=generated.tf` ajuda a comparar
com o estado real do Render.

Depois de importado, o CI cuida do resto.

> Execução local em vez de remota: se preferir rodar o Terraform na sua máquina
> (e usar o TFC só como storage de state), mude o workspace para *Local
> execution* na UI e use `terraform.tfvars` (veja `.example`). No modo remoto
> padrão, os valores vêm das variáveis do workspace, não do tfvars.

## CI (`.github/workflows/terraform.yml`)

- **PR** que toca `infra/**` → `fmt` + `validate` + `plan` remoto (comentado no PR).
- **push na main** → `apply` remoto, protegido pelo environment `production`.

O `fmt` é o gate que **sempre** roda. `plan`/`apply` só rodam quando o secret
`TF_API_TOKEN` existir — enquanto o Terraform Cloud não estiver configurado,
esses jobs são **pulados** (não falham), então a `main` fica verde. Assim que
você cadastrar o token e a organização real em `versions.tf`, o pipeline liga.

### Segredo do GitHub Actions

Repo → Settings → Secrets and variables → Actions → **Secrets**:

- `TF_API_TOKEN` — token da API do Terraform Cloud.

É o **único** segredo no GitHub: os segredos da aplicação ficam no workspace do
TFC. Proteja o environment `production` (Settings → Environments) com required
reviewers se quiser aprovação manual antes de cada `apply`.

## Não quer segredos no Terraform?

Se preferir manter os valores dos segredos só no dashboard do Render, descomente
o bloco `lifecycle { ignore_changes = [env_vars] }` em `render.tf` e deixe as
variáveis secretas vazias. O Terraform passa a gerenciar só o serviço, não os
valores das env vars.

# Infraestrutura, autenticação e entrega

## Visão geral

O Lombada é publicado em **https://lombada.app**. A aplicação FastAPI e o banco
PostgreSQL são executados no Railway, enquanto a zona DNS do domínio é mantida
na Cloudflare.

A arquitetura atual substitui a configuração anterior, na qual a aplicação era
hospedada no Render e o PostgreSQL ficava no Neon. A migração concentrou app e
banco no Railway, mantendo o domínio próprio, os caminhos existentes e o login
com Google.

```text
Usuário
  ↓ HTTPS
lombada.app
  ↓ DNS Cloudflare
Railway — serviço Lombada (FastAPI)
  ↓
Railway PostgreSQL
```

O domínio é atendido diretamente como `lombada.app`; não há redirecionamento
HTTP visível para um endereço `railway.app`. Rotas como `/sobre`, `/api-docs` e
`/api/auth/google/callback` permanecem no domínio público.

## Migração de Render e Neon para Railway

A migração envolveu duas partes:

- **Aplicação:** saiu do Render e passou a ser construída e executada pelo
  serviço `Lombada`, no projeto Railway `authentic-joy`.
- **Banco:** saiu do Neon e passou a usar PostgreSQL no próprio Railway, por
  meio da variável `DATABASE_URL` fornecida pelo ambiente.

As migrações de schema continuam sendo idempotentes e executadas no boot da
aplicação por `SQLModel.metadata.create_all()` e `migrar()`. Os scripts
operacionais também usam somente `DATABASE_URL`, sem dependência direta do
Neon.

O arquivo `railway.toml` versiona as configurações principais de build e deploy:

- instalação das dependências Python;
- inicialização com Uvicorn usando a porta fornecida pelo Railway;
- health check em `/healthz`;
- política de reinício em caso de falha.

## Infraestrutura como código

A infraestrutura é gerenciada com Terraform e estado remoto no HCP Terraform:

- **organização:** `lombada`;
- **workspace:** `lombada-prod`;
- **provider Railway:** projeto, serviço e domínio customizado;
- **provider Cloudflare:** registros DNS do domínio e registro de validação;
- **recursos existentes:** projeto e serviço Railway foram adotados por
  importação, sem recriação.

O Terraform administra atualmente:

1. o projeto Railway existente;
2. o serviço web existente;
3. o domínio customizado `lombada.app` no Railway;
4. o CNAME do domínio na Cloudflare;
5. o TXT usado pelo Railway para validar a propriedade do domínio.

O banco, os dados e as variáveis internas da aplicação não são recriados pelo
Terraform nesta etapa. Segredos também não são versionados no repositório.

### HTTPS e Cloudflare

A Cloudflare funciona atualmente como provedora de DNS, com o proxy desativado:

```hcl
cloudflare_proxy_enabled = false
```

Nesse modo, o fluxo é:

```text
Navegador → DNS Cloudflare → Railway
```

O certificado HTTPS apresentado ao usuário é emitido e servido automaticamente
pelo Railway depois da validação do CNAME e do TXT. O proxy laranja da
Cloudflare pode ser avaliado no futuro, mas não é necessário para o HTTPS atual.

## Google OAuth

O login com Google usa o callback canônico:

```text
https://lombada.app/api/auth/google/callback
```

Esse endereço deve existir em dois lugares:

- na lista de **URIs de redirecionamento autorizados** do cliente OAuth no
  Google Cloud;
- na variável `GOOGLE_REDIRECT_URI` do serviço Lombada no Railway.

Durante a migração, o callback antigo do domínio `railway.app` pode permanecer
cadastrado temporariamente no Google Cloud. Depois que o login pelo domínio
novo estiver validado, o callback antigo pode ser removido.

As credenciais `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` permanecem como
variáveis protegidas no Railway e nunca entram no Terraform ou no GitHub.

## CI/CD com GitHub Actions

O workflow `.github/workflows/terraform.yml` separa validação e aplicação:

### Pull requests

Alterações em `infra/**`, `railway.toml` ou no próprio workflow executam:

1. `terraform fmt -check`;
2. `terraform init` conectado ao HCP Terraform;
3. `terraform validate`;
4. `terraform plan` remoto;
5. publicação da saída do plan como artefato temporário.

Pull requests nunca executam `terraform apply`.

### Aplicação manual

O apply de infraestrutura só pode ser iniciado manualmente na aba Actions. O
workflow exige:

```text
operation: apply
confirmation: APPLY_LOMBADA_APP
```

Antes do apply, o workflow executa novamente um plan. Não existe apply
automático em push ou merge.

O deploy da aplicação continua integrado ao Railway: mudanças na branch `main`
acionam o deploy do serviço conectado ao repositório. Assim, o deploy do código
e a alteração da infraestrutura permanecem processos separados.

## Segredos e variáveis

### GitHub Actions

O único segredo necessário para o workflow de Terraform é:

```text
TF_API_TOKEN
```

Ele autentica o runner no HCP Terraform.

### HCP Terraform

Variáveis de ambiente sensíveis:

```text
RAILWAY_TOKEN
CLOUDFLARE_API_TOKEN
```

Terraform variables não sensíveis incluem os IDs do projeto, serviço e zona
Cloudflare, além de `cloudflare_proxy_enabled`.

### Railway

Os segredos e configurações da aplicação continuam no serviço Railway, entre
eles:

```text
DATABASE_URL
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
SECRET_KEY
```

Nenhum token, senha ou URL de banco real deve ser incluído no repositório.

## Verificação operacional

Após mudanças de infraestrutura ou deploy, valide:

```bash
curl -fsS https://lombada.app/healthz
curl -fsS https://lombada.app/api/version
curl -fsS https://lombada.app/api/editoras
```

Também devem ser testados manualmente:

- abertura da página inicial e de rotas como `/sobre`;
- login Google e retorno para o domínio `lombada.app`;
- leitura e escrita no PostgreSQL Railway;
- ausência de redirecionamento visível para o domínio do Railway.

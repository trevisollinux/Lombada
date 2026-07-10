provider "railway" {
  # O provider lê o token da variável de ambiente RAILWAY_TOKEN.
  # No HCP Terraform, crie RAILWAY_TOKEN como Environment variable e marque
  # como Sensitive. Use um Account/Workspace token para permitir imports.
}

# Habilite junto com o provider em versions.tf ao migrar o domínio.
# provider "cloudflare" {
#   api_token = var.cloudflare_api_token
# }

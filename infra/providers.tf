provider "railway" {
  # O provider lê o token da variável de ambiente RAILWAY_TOKEN.
  # No HCP Terraform, crie RAILWAY_TOKEN como Environment variable e marque
  # como Sensitive. Use um Account/Workspace token para permitir imports.
}

provider "cloudflare" {
  # O provider lê CLOUDFLARE_API_TOKEN do ambiente.
  # No HCP Terraform, crie essa Environment variable como Sensitive.
}

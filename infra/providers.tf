provider "render" {
  # Vêm de TF_VAR_render_api_key / TF_VAR_render_owner_id (GitHub secrets em CI).
  # owner_id é o id do time/usuário dono dos recursos (começa com "tea-" ou "usr-").
  api_key  = var.render_api_key
  owner_id = var.render_owner_id
}

# Habilite junto com o provider em versions.tf ao migrar o domínio.
# provider "cloudflare" {
#   api_token = var.cloudflare_api_token
# }

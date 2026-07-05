# NOTA: o provider render-oss/render é novo e o schema evolui. Antes do primeiro
# `apply`, confira os nomes de atributos de render_web_service em:
# https://registry.terraform.io/providers/render-oss/render/latest/docs

locals {
  # Env vars não-secretas: valores em texto, versionados aqui.
  render_env_public = {
    COOKIE_SECURE        = { value = "true" }
    SESSION_COOKIE_NAME  = { value = "lombada_session" }
    APP_VERSION          = { value = "prod" }
    DEMO_CONTENT_ENABLED = { value = "false" }
    CATALOG_SEED_ENABLED = { value = "false" }
    ADMIN_EMAILS         = { value = var.admin_emails }
    GOOGLE_REDIRECT_URI  = { value = "${var.app_base_url}/auth/google/callback" }
    PENGUIN_DOMAIN       = { value = "api.penguinrandomhouse.com" }
  }

  # Env vars secretas: valores vêm de variáveis sensíveis (CI / tfvars).
  # Chaves com valor vazio são omitidas para não sobrescrever segredos já no Render.
  render_env_secret = {
    for k, v in {
      DATABASE_URL         = var.database_url
      SECRET_KEY           = var.secret_key
      GOOGLE_CLIENT_ID     = var.google_client_id
      GOOGLE_CLIENT_SECRET = var.google_client_secret
      GOOGLE_BOOKS_API_KEY = var.google_books_api_key
      HARDCOVER_API_KEY    = var.hardcover_api_key
      PENGUIN_API_KEY      = var.penguin_api_key
      ME_TOKEN             = var.me_token
      RECON_TOKEN          = var.recon_token
    } : k => { value = v } if v != ""
  }
}

resource "render_web_service" "lombada" {
  name   = "lombada"
  plan   = var.render_plan
  region = var.render_region

  runtime_source = {
    native_runtime = {
      runtime       = "python"
      repo_url      = var.repo_url
      branch        = var.repo_branch
      build_command = "pip install -r requirements.txt"
      start_command = "uvicorn main:app --host 0.0.0.0 --port $PORT"
      auto_deploy   = true
    }
  }

  env_vars = merge(local.render_env_public, local.render_env_secret)

  # Se preferir NÃO gerenciar os valores dos segredos pelo Terraform (mantê-los
  # só no dashboard do Render), descomente e mantenha apenas as chaves públicas
  # em env_vars acima:
  # lifecycle {
  #   ignore_changes = [env_vars]
  # }
}

# ─── Custom domain (habilite ao migrar para Cloudflare) ───────────────────
# resource "render_custom_domain" "app" {
#   service_id = render_web_service.lombada.id
#   name       = var.app_domain
# }

# ─── Render Postgres (habilite só se o banco for gerenciado pelo Render) ───
# Se o DATABASE_URL aponta para Neon/Supabase/externo, NÃO use este bloco —
# mantenha DATABASE_URL como segredo (var.database_url) e pronto.
#
# resource "render_postgres" "db" {
#   name          = "lombada-db"
#   plan          = "basic_256mb"
#   region        = var.render_region
#   version       = "16"
#   database_name = "lombada"
#   database_user = "lombada"
# }
#
# Depois, referencie a conexão interna no env var em vez de var.database_url:
#   DATABASE_URL = { value = render_postgres.db.connection_info.internal_connection_string }

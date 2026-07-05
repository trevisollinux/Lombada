# ─── Credenciais de provider ──────────────────────────────────────────────
# Nunca commitadas. Em CI vêm como TF_VAR_* (GitHub Actions secrets);
# localmente, ponha em terraform.tfvars (gitignored).

variable "render_api_key" {
  type        = string
  sensitive   = true
  description = "API key do Render (https://dashboard.render.com/u/settings#api-keys)."
}

variable "render_owner_id" {
  type        = string
  description = "Owner id do Render (tea-... ou usr-...). Não é segredo, mas varia por conta."
}

# ─── Config operacional do serviço (não-secreto) ──────────────────────────

variable "render_region" {
  type        = string
  default     = "oregon"
  description = "Região do Render onde o serviço vive."
}

variable "render_plan" {
  type        = string
  default     = "starter"
  description = "Plano do web service. 'free' hiberna (cold start feio na TWA); 'starter' fica de pé."
}

variable "repo_url" {
  type        = string
  default     = "https://github.com/trevisollinux/lombada"
  description = "Repositório de deploy do Render."
}

variable "repo_branch" {
  type        = string
  default     = "main"
  description = "Branch que o Render faz deploy."
}

variable "app_base_url" {
  type        = string
  default     = "https://lombada.onrender.com"
  description = "URL pública base. Troque para o domínio próprio ao migrar para Cloudflare."
}

# ─── Segredos da aplicação ────────────────────────────────────────────────
# Já existem no Render. Só precisam de valor aqui se você quiser que o
# Terraform os gerencie. Veja o README (bloco 'import' + ignore_changes) para
# adotar sem reescrever os valores.

variable "database_url" {
  type        = string
  sensitive   = true
  description = "String de conexão Postgres (DATABASE_URL)."
}

variable "secret_key" {
  type        = string
  sensitive   = true
  description = "SECRET_KEY de sessão/cookies."
}

variable "google_client_id" {
  type        = string
  sensitive   = true
  default     = ""
  description = "OAuth Google (GOOGLE_CLIENT_ID)."
}

variable "google_client_secret" {
  type        = string
  sensitive   = true
  default     = ""
  description = "OAuth Google (GOOGLE_CLIENT_SECRET)."
}

variable "google_books_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "GOOGLE_BOOKS_API_KEY."
}

variable "hardcover_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "HARDCOVER_API_KEY."
}

variable "penguin_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "PENGUIN_API_KEY."
}

variable "me_token" {
  type        = string
  sensitive   = true
  default     = ""
  description = "ME_TOKEN (Mercado Livre)."
}

variable "recon_token" {
  type        = string
  sensitive   = true
  default     = ""
  description = "RECON_TOKEN (endpoint de diagnóstico)."
}

variable "admin_emails" {
  type        = string
  default     = ""
  description = "ADMIN_EMAILS (lista separada por vírgula)."
}

# ─── Cloudflare (comentado até o domínio existir) ─────────────────────────
# variable "cloudflare_api_token" {
#   type        = string
#   sensitive   = true
#   description = "Token da Cloudflare com permissão de editar DNS da zona."
# }
#
# variable "cloudflare_zone_id" {
#   type        = string
#   description = "Zone id do domínio na Cloudflare."
# }
#
# variable "app_domain" {
#   type        = string
#   default     = "lombada.app"
#   description = "Domínio próprio final do app."
# }

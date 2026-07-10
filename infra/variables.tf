# ─── Recursos existentes no Railway ───────────────────────────────────────
# Nesta primeira etapa o Terraform adota apenas o projeto e o serviço web.
# Banco e variáveis da aplicação continuam gerenciados pelo dashboard até o
# primeiro plan/import ficar completamente limpo.

variable "railway_project_id" {
  type        = string
  description = "ID do projeto Railway existente, usado pelo bloco import."
}

variable "railway_service_id" {
  type        = string
  description = "ID do serviço web Railway existente, usado pelo bloco import."
}

variable "railway_workspace_id" {
  type        = string
  default     = ""
  description = "ID do workspace Railway. Necessário quando o token acessa mais de um workspace."
}

variable "railway_project_name" {
  type        = string
  default     = "Lombada"
  description = "Nome do projeto existente no Railway."
}

variable "railway_service_name" {
  type        = string
  default     = "Lombada"
  description = "Nome do serviço web existente no Railway. Ajuste para o nome exibido no dashboard."
}

variable "repo_url" {
  type        = string
  default     = "https://github.com/trevisollinux/Lombada"
  description = "Repositório conectado ao serviço Railway."
}

variable "repo_branch" {
  type        = string
  default     = "main"
  description = "Branch usada para deploy no Railway."
}

variable "app_base_url" {
  type        = string
  default     = "https://lombada-production.up.railway.app"
  description = "URL pública atual da aplicação."
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

# ─── Recursos existentes no Railway ───────────────────────────────────────
# Nesta primeira etapa o Terraform adota o projeto e o serviço web existentes.
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
  default     = "authentic-joy"
  description = "Nome do projeto existente no Railway."
}

variable "railway_service_name" {
  type        = string
  default     = "Lombada"
  description = "Nome do serviço web existente no Railway. Ajuste para o nome exibido no dashboard."
}

variable "repo_url" {
  type        = string
  default     = "trevisollinux/Lombada"
  description = "Repositório conectado ao serviço Railway no formato owner/repo."
}

variable "repo_branch" {
  type        = string
  default     = "main"
  description = "Branch usada para deploy no Railway."
}

# ─── Domínio público / Cloudflare ─────────────────────────────────────────

variable "app_domain" {
  type        = string
  default     = "lombada.app"
  description = "Domínio canônico da aplicação."
}

variable "app_base_url" {
  type        = string
  default     = "https://lombada.app"
  description = "URL pública canônica da aplicação."
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Zone ID da zona lombada.app na Cloudflare."
}

variable "cloudflare_proxy_enabled" {
  type        = bool
  default     = false
  description = "Ativa o proxy laranja da Cloudflare. Mantenha false até o Railway validar DNS e emitir o certificado."
}

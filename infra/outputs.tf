output "web_service_id" {
  value       = render_web_service.lombada.id
  description = "ID do web service no Render."
}

output "web_service_url" {
  value       = try(render_web_service.lombada.url, var.app_base_url)
  description = "URL pública do serviço."
}

output "managed_env_var_keys" {
  value       = keys(merge(local.render_env_public, local.render_env_secret))
  description = "Env vars gerenciadas pelo Terraform (sem expor valores)."
}

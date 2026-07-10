output "railway_project_id" {
  value       = railway_project.lombada.id
  description = "ID do projeto no Railway."
}

output "railway_service_id" {
  value       = var.railway_service_id
  description = "ID do serviço web existente no Railway."
}

output "web_service_url" {
  value       = var.app_base_url
  description = "URL pública atual do serviço."
}

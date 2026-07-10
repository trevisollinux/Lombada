locals {
  railway_workspace_id = trimspace(var.railway_workspace_id)
}

resource "railway_project" "lombada" {
  name    = var.railway_project_name
  private = true

  workspace_id = local.railway_workspace_id != "" ? local.railway_workspace_id : null
}

resource "railway_service" "app" {
  name               = var.railway_service_name
  project_id         = railway_project.lombada.id
  source_repo        = var.repo_url
  source_repo_branch = var.repo_branch

  # Garante que o campo railwayConfigFile seja apagado diretamente pela API
  # antes de o provider reler e sincronizar o serviço.
  depends_on = [terraform_data.reset_railway_build_config]

  # Preserva a região e a quantidade de réplicas já existentes durante o import.
  regions = [
    {
      region       = "sfo"
      num_replicas = 1
    }
  ]

  # Build, start command e demais opções de deploy permanecem no painel do
  # Railway. Banco e env vars da aplicação também não são gerenciados aqui.
}

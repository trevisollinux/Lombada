locals {
  railway_workspace_id = trimspace(var.railway_workspace_id)
}

resource "railway_project" "lombada" {
  name        = var.railway_project_name
  description = "Lombada — rede social de livros e catálogo brasileiro"
  private     = true

  workspace_id = local.railway_workspace_id != "" ? local.railway_workspace_id : null
}

resource "railway_service" "app" {
  name               = var.railway_service_name
  project_id         = railway_project.lombada.id
  source_repo        = var.repo_url
  source_repo_branch = var.repo_branch
  config_path        = "railway.toml"

  # Demais opções de build/deploy ficam no railway.toml, como recomendado pelo
  # provider. Não gerenciamos banco nem env vars nesta primeira adoção.
}

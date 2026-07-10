locals {
  railway_workspace_id = trimspace(var.railway_workspace_id)
}

resource "railway_project" "lombada" {
  name    = var.railway_project_name
  private = true

  workspace_id = local.railway_workspace_id != "" ? local.railway_workspace_id : null
}

# O serviço web já existe e continua ativo no Railway, mas deixa de ser
# gerenciado pelo provider comunitário. O provider 0.6.x não consegue remover
# config_path e produz estado inconsistente. destroy = false apenas esquece o
# recurso no state; não exclui nem recria o serviço real.
removed {
  from = railway_service.app

  lifecycle {
    destroy = false
  }
}

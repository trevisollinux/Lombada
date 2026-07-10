# Limpeza final da configuração de build persistida no Railway.
#
# O railway.toml foi removido do repositório e o serviço deixou de ser gerenciado
# pelo provider comunitário. Esta execução limpa a instância production uma
# última vez sem que o provider tente reler config_path em seguida.

resource "terraform_data" "reset_railway_build_config" {
  triggers_replace = [
    var.railway_service_id,
    railway_project.lombada.default_environment.id,
    "2026-07-10-reset-build-v3-final",
  ]

  provisioner "local-exec" {
    command = "bash \"${path.module}/scripts/reset_railway_build_config.sh\""

    environment = {
      RAILWAY_SERVICE_ID     = var.railway_service_id
      RAILWAY_ENVIRONMENT_ID = railway_project.lombada.default_environment.id
    }
  }
}

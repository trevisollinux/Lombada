# Contorno temporário para um bug do provider Railway 0.6.x:
# ao remover config_path, o provider omite o campo em vez de enviar null.
# O Railway mantém railway.toml e o apply termina inconsistente.
#
# Este recurso executa uma única limpeza direta pela API antes da atualização
# do railway_service. Depois que o apply concluir, ele pode ser removido.

resource "terraform_data" "reset_railway_build_config" {
  triggers_replace = [
    var.railway_service_id,
    "2026-07-10-reset-build-v1",
  ]

  provisioner "local-exec" {
    command = "bash \"${path.module}/scripts/reset_railway_build_config.sh\""

    environment = {
      RAILWAY_SERVICE_ID = var.railway_service_id
    }
  }
}

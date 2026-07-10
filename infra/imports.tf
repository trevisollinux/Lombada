# ─── Adoção do projeto EXISTENTE no Railway ────────────────────────────────
#
# O ID entra como Terraform variable no workspace HCP Terraform. O serviço web
# deixa de ser gerenciado pelo provider comunitário por causa do bug ao remover
# config_path; seu ID continua sendo usado diretamente pelos demais recursos.

import {
  to = railway_project.lombada
  id = var.railway_project_id
}

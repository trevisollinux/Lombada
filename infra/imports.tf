# ─── Adoção dos recursos EXISTENTES no Railway ────────────────────────────
#
# Os IDs entram como Terraform variables no workspace HCP Terraform. O plan
# deve mostrar apenas import/adoption, nunca destruição ou recriação.

import {
  to = railway_project.lombada
  id = var.railway_project_id
}

import {
  to = railway_service.app
  id = var.railway_service_id
}

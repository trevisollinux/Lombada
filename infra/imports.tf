# ─── Adoção de recursos EXISTENTES no Render (create + import) ─────────────
#
# Os recursos e segredos já vivem no Render. Estes blocos `import` (Terraform
# 1.5+) fazem o Terraform ADOTAR o que existe em vez de tentar recriar.
#
# COMO USAR:
#   1. Pegue o service id no dashboard do Render (URL do serviço: srv-xxxxx...).
#   2. Cole abaixo em `id`.
#   3. Rode `terraform plan` — deve mostrar "1 to import" e, se os valores
#      baterem, nenhuma mudança destrutiva. Ajuste variables/env até o plan
#      ficar limpo, então `terraform apply`.
#   4. Depois de importado com sucesso, pode remover/comentar este bloco.
#
# Dica: `terraform plan -generate-config-out=generated.tf` gera um rascunho da
# config a partir do estado real — útil pra conferir se render.tf bate.

import {
  to = render_web_service.lombada
  id = "srv-REPLACE_ME" # id do web service no Render
}

# Se for adotar o Render Postgres (descomente também o resource em render.tf):
# import {
#   to = render_postgres.db
#   id = "dpg-REPLACE_ME" # id do banco no Render
# }

# ─── Cloudflare DNS — TUDO COMENTADO ──────────────────────────────────────
# A zona ainda não existe. Ao migrar o domínio, habilite:
#   - o provider cloudflare em versions.tf e providers.tf
#   - as variáveis cloudflare_* em variables.tf
#   - o render_custom_domain em render.tf
#   - este arquivo
#
# Ordem de dependência: render_custom_domain -> cloudflare_record.
# O cert do Render leva alguns minutos após o DNS propagar.

# resource "cloudflare_record" "app" {
#   zone_id = var.cloudflare_zone_id
#   name    = "@" # apex; a Cloudflare faz CNAME flattening
#   type    = "CNAME"
#   content = "lombada.onrender.com"
#   ttl     = 1
#
#   # GOTCHA: comece com proxied = false (DNS-only) até o Render validar o
#   # domínio e emitir o cert. Só depois ligue o proxy — e aí use
#   # SSL mode = Full (strict) na zona, senão dá loop de redirect / erro 525.
#   proxied = false
# }
#
# Lembretes ao trocar de domínio:
#   - atualizar GOOGLE_REDIRECT_URI (já derivado de app_base_url aqui) E a lista
#     de redirect URIs autorizados no Google Cloud Console (fora do TF).
#   - decidir o domínio ANTES de gerar o .aab: o assetlinks.json fica atrelado
#     ao domínio e o package name do app Android é imutável.

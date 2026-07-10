# O domínio customizado é criado no Railway. O provider devolve os valores de
# CNAME e TXT exigidos para validação; a Cloudflare publica ambos.
#
# Não há redirecionamento HTTP para o endereço railway.app: o navegador acessa
# diretamente https://lombada.app e todos os caminhos (/sobre, /api-docs etc.)
# são encaminhados ao mesmo serviço FastAPI.

resource "railway_custom_domain" "app" {
  domain         = var.app_domain
  environment_id = railway_project.lombada.default_environment.id
  service_id     = railway_service.app.id
}

resource "cloudflare_record" "app" {
  zone_id = var.cloudflare_zone_id
  name    = "@"
  type    = "CNAME"
  content = railway_custom_domain.app.dns_record_value
  ttl     = 1
  proxied = var.cloudflare_proxy_enabled
}

resource "cloudflare_record" "railway_verification" {
  zone_id = var.cloudflare_zone_id
  name    = railway_custom_domain.app.verification_host_label
  type    = "TXT"
  content = railway_custom_domain.app.verification_record_value
  ttl     = 1
  proxied = false
}

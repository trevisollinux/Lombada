# O domínio customizado é criado no Railway. O provider devolve os valores de
# CNAME e TXT exigidos para validação; a Cloudflare publica ambos.

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

# Compatibilidade para quem digitar www.lombada.app. O destino final continua
# sendo servido pelo mesmo app e preserva os caminhos.
resource "railway_custom_domain" "www" {
  domain         = "www.${var.app_domain}"
  environment_id = railway_project.lombada.default_environment.id
  service_id     = railway_service.app.id
}

resource "cloudflare_record" "www" {
  zone_id = var.cloudflare_zone_id
  name    = "www"
  type    = "CNAME"
  content = railway_custom_domain.www.dns_record_value
  ttl     = 1
  proxied = var.cloudflare_proxy_enabled
}

resource "cloudflare_record" "www_railway_verification" {
  zone_id = var.cloudflare_zone_id
  name    = railway_custom_domain.www.verification_host_label
  type    = "TXT"
  content = railway_custom_domain.www.verification_record_value
  ttl     = 1
  proxied = false
}

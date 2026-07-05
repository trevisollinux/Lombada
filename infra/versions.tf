terraform {
  required_version = ">= 1.7"

  required_providers {
    render = {
      source  = "render-oss/render"
      version = "~> 1.4"
    }

    # Cloudflare ainda não existe — habilite quando migrar o domínio.
    # A major v5 mudou o schema; pinar em ~> 4.40 mantém a sintaxe deste módulo.
    # cloudflare = {
    #   source  = "cloudflare/cloudflare"
    #   version = "~> 4.40"
    # }
  }
}

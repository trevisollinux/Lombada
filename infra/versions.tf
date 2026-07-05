terraform {
  required_version = ">= 1.7"

  # State + execução remota no Terraform Cloud (HCP Terraform).
  # Troque a organização pela sua. O workspace é criado no primeiro `init`
  # (ou via UI). Não pode coexistir com um bloco `backend` — por isso não há
  # mais backend.tf.
  cloud {
    organization = "SEU_ORG_TFC"

    workspaces {
      name = "lombada-prod"
    }
  }

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

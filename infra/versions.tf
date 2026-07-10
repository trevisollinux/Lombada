terraform {
  required_version = ">= 1.7"

  # State + execução remota no HCP Terraform.
  # Antes do primeiro init, troque SEU_ORG_TFC pelo nome da organização criada.
  cloud {
    organization = "SEU_ORG_TFC"

    workspaces {
      name = "lombada-prod"
    }
  }

  required_providers {
    railway = {
      source  = "terraform-community-providers/railway"
      version = "~> 0.6.2"
    }

    # Cloudflare ainda não existe — habilite quando migrar o domínio.
    # cloudflare = {
    #   source  = "cloudflare/cloudflare"
    #   version = "~> 4.40"
    # }
  }
}

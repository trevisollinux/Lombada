terraform {
  required_version = ">= 1.7"

  # State + execução remota no HCP Terraform.
  cloud {
    organization = "lombada"

    workspaces {
      name = "lombada-prod"
    }
  }

  required_providers {
    railway = {
      source  = "terraform-community-providers/railway"
      version = "~> 0.6.2"
    }

    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
  }
}

# State remoto no Cloudflare R2 (S3-compatible).
#
# Por que R2: você já vai usar Cloudflare, é barato e o state guarda segredos
# (DATABASE_URL, SECRET_KEY, OAuth) — nunca deixe local/commitado.
#
# Setup uma vez:
#   1. Crie o bucket "lombada-tfstate" no R2.
#   2. Gere um token R2 (Access Key ID / Secret) e exponha em CI como
#      AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.
#   3. Troque <R2_ACCOUNT_ID> abaixo (o account id não é segredo).
#
# Em CI, `validate`/`fmt` rodam com `-backend=false` (sem credenciais);
# só `plan`/`apply` fazem init real com backend.

terraform {
  backend "s3" {
    bucket = "lombada-tfstate"
    key    = "prod/terraform.tfstate"
    region = "auto"

    endpoints = {
      s3 = "https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com"
    }

    # R2 não implementa as validações/checksums da AWS.
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}

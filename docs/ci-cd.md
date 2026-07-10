# CI/CD

O Lombada usa GitHub Actions para validar código e infraestrutura.

## Infraestrutura

Em pull requests, o workflow de Terraform executa formatação, inicialização,
validação e plan remoto no HCP Terraform. O apply não ocorre automaticamente.

A aplicação da infraestrutura é manual e exige a confirmação explícita:

```text
operation: apply
confirmation: APPLY_LOMBADA_APP
```

## Aplicação

O serviço Railway permanece conectado à branch `main`. Depois do merge, o
Railway executa o build e o deploy da aplicação conforme `railway.toml`.

Essa separação evita que um merge de código aplique alterações de
infraestrutura sem revisão.

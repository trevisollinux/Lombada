# Migração de hospedagem

Resumo da mudança de infraestrutura realizada no Lombada:

- aplicação migrada do **Render** para o **Railway**;
- banco PostgreSQL migrado do **Neon** para o **Railway PostgreSQL**;
- infraestrutura adotada e gerenciada com **Terraform** e estado remoto no
  **HCP Terraform**;
- domínio **lombada.app** configurado na **Cloudflare**, com certificado HTTPS
  emitido pelo Railway;
- callback do **Google OAuth** atualizado para o domínio público;
- validação, plan e apply protegido implementados com **GitHub Actions**.

A documentação detalhada está em [infraestrutura.md](infraestrutura.md).

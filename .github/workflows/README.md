# Workflows ativos do Lombada

## Sync publisher source records
Workflow principal.
Use para raspar editoras e popular `source_records`.
- `dry_run=true`: testa sem gravar
- `dry_run=false`: grava e promove
- `slugs`: filtra editoras
- `max_urls`: lote por editora

## List catalog
Auditoria da base.
Use para ver totais por editora e livros já ingeridos.

## Promote source records to catalog
Promoção manual.
Use quando quiser promover pendências de `source_records` para `obra`/`edicao`.

## Seed demo users
Dados demo.
Use para limpar atividade do usuário alvo e criar usuários fake de teste.

## Render keep-alive
Workflow removido. O CI não executa mais ping periódico para manter o serviço do Render ativo.

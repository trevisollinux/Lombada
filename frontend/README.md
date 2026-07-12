# Frontend React do Lombada

Este diretório contém a migração incremental do frontend interativo para React, TypeScript e Vite.

## Estado atual

O frontend React é compilado durante o build do Docker e servido pelo entrypoint de produção em `/app-v2`.

O aplicativo legado continua responsável pela rota `/` e por todos os fluxos reais. A rota nova existe como ambiente seguro para a migração gradual, sem substituir a experiência atual.

Quando o diretório `frontend/dist` não existe, `/app-v2` responde com status 503 e informa que o frontend ainda não foi compilado. Isso permite importar e testar o backend sem exigir Node em todos os ambientes Python.

## Requisitos

- Node.js `^20.19.0` ou `>=22.12.0`
- npm

## Comandos

```bash
npm install
npm run dev
npm run typecheck
npm run build
npm run preview
```

Durante o desenvolvimento, chamadas para `/api` e `/auth` são encaminhadas pelo Vite para `http://localhost:8000`.

Para testar o build integrado localmente:

```bash
docker build -t lombada-app-v2 .
docker run --rm -p 8000:8000 lombada-app-v2
```

Depois, abra `/app-v2` no servidor local.

## Cache

- `index.html` e rotas da SPA: `no-cache`;
- assets versionados do Vite em `/app-v2/assets/`: cache longo e imutável;
- assets inexistentes: 404, sem fallback indevido para HTML.

## Regras da migração

- manter FastAPI, banco, autenticação e APIs atuais;
- preservar a identidade visual do Lombada;
- migrar por funcionalidades pequenas e reversíveis;
- não remover fluxos legados antes da paridade;
- não alterar a PWA nesta fase;
- adicionar o lockfile antes de ampliar significativamente as dependências.

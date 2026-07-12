# Frontend React do Lombada

Este diretório contém a migração incremental do frontend interativo para React, TypeScript e Vite.

## Estado atual

O frontend React é compilado durante o build do Docker e servido pelo entrypoint de produção em `/app-v2`.

O aplicativo legado continua responsável pela rota `/` e por todos os fluxos reais. A rota nova existe como ambiente seguro para a migração gradual, sem substituir a experiência atual.

O shell v2 já possui:

- React Router com `basename=/app-v2`;
- navegação responsiva para celular e desktop;
- tema claro/escuro compartilhado com o app legado;
- idioma português/inglês compartilhado com o app legado;
- sessão e conta carregadas por `/api/eu`;
- estados de loading, erro e retry;
- rotas estruturais para busca, feed, estante, diário e perfil;
- painel de configurações e ações rápidas.

Quando o diretório `frontend/dist` não existe, `/app-v2` responde com status 503 e informa que o frontend ainda não foi compilado. Isso permite importar e testar o backend sem exigir Node em todos os ambientes Python.

## Requisitos

- Node.js `^22.22.0` ou `>=24.0.0`
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

## Próximas funcionalidades

1. estante somente leitura consumindo `/api/prateleira`;
2. detalhes e mutações de leitura;
3. diário real;
4. busca, obra e edições;
5. feed, explorar e perfil completos.

## Regras da migração

- manter FastAPI, banco, autenticação e APIs atuais;
- preservar a identidade visual do Lombada;
- migrar por funcionalidades pequenas e reversíveis;
- não remover fluxos legados antes da paridade;
- não alterar a PWA nesta fase;
- adicionar o lockfile antes de ampliar significativamente as dependências.

# Frontend React do Lombada

Este diretório contém o frontend do Lombada em React, TypeScript e Vite.

## Estado atual

O frontend React é compilado durante o build do Docker e **serve a raiz `/`**.
Ele é o aplicativo do Lombada e a PWA instalável.

O aplicativo legado (`index.html` + `static/app.js`) continua inteiro em
**`/app-v1`**, como rota de escape para os fluxos que ainda não têm paridade
(quatro essenciais, reações literárias, gestão de status personalizados, visão
de lombadas, Amazon, busca avançada e espanhol). Ele não é mais instalável:
não declara manifest e não registra service worker.

O que o React responde:

- React Router com `basename=/` e rotas `/`, `/explorar`, `/explorar/editoras`,
  `/obra`, `/feed`, `/estante`, `/diario`, `/memorias`, `/perfil`;
- navegação responsiva para celular e desktop;
- tema claro/escuro e idioma PT/EN compartilhados com o app legado;
- sessão e conta carregadas por `/api/eu`;
- estados de loading, erro e retry;
- painel de configurações e ações rápidas.

Continuam renderizadas no servidor pelo FastAPI, fora do React: `/u/{handle}`,
`/editoras`, `/editora/{slug}`, `/blog`, `/sobre`, `/quem-somos`, `/contribua`,
`/privacidade`, `/api-docs` e `/admin`. São páginas públicas (busca,
compartilhamento) e telas administrativas.

Quando `frontend/dist` não existe — ambiente Python sem Node, build quebrado —
a raiz **cai para o app legado** em vez de derrubar o site. Isso permite
importar e testar o backend sem exigir Node em todos os ambientes.

## Rotas da SPA e o backend

`SPA_ROUTES`, em `frontend_app.py`, espelha o primeiro segmento de cada rota
declarada em `src/App.tsx`. O backend só devolve o `index.html` para elas;
qualquer outro caminho desconhecido continua sendo 404 do servidor.

**Ao adicionar uma rota nova no React Router**, inclua o primeiro segmento dela
em `SPA_ROUTES` e em `APP_ROUTES` (`public/sw.js`). Sem isso, o acesso direto e
o refresh na rota nova respondem 404 — a navegação interna do app esconde a
quebra. `tests/test_frontend_app.py` verifica as três listas.

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

Durante o desenvolvimento, chamadas para `/api` e `/auth` são encaminhadas pelo
Vite para `http://localhost:8000`.

Para testar o build integrado localmente:

```bash
docker build -t lombada .
docker run --rm -p 8000:8000 lombada
```

Depois, abra `/` no servidor local (e `/app-v1` para comparar com o legado).

## Cache e PWA

- `index.html` e rotas da SPA: `no-cache`;
- assets versionados do Vite em `/assets/`: cache longo e imutável;
- assets inexistentes: 404, sem fallback indevido para HTML;
- `/sw.js` (escopo `/`): nunca cacheado, servido a partir do build.

O service worker apaga no `activate` os caches `lombada-shell-*` do app legado,
que antes controlava o escopo `/`. Sem isso, quem já tinha o PWA instalado
continuaria recebendo o shell antigo depois do corte.

O worker só intercepta navegações das rotas do app: `/u/…`, `/blog`, `/admin` e
`/app-v1` são HTML do servidor e passam direto.

## Pendências de paridade

1. quatro essenciais, reações literárias e gestão de status personalizados;
2. visão de lombadas, Amazon, busca avançada e polimentos recentes do legado;
3. espanhol.

## Regras da migração

- manter FastAPI, banco, autenticação e APIs atuais;
- preservar a identidade visual do Lombada;
- migrar por funcionalidades pequenas e reversíveis;
- manter `/app-v1` disponível enquanto houver pendência de paridade;
- adicionar o lockfile antes de ampliar significativamente as dependências.

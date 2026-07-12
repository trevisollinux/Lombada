# Frontend React do Lombada

Este diretório contém a migração incremental do frontend interativo para React, TypeScript e Vite.

## Estado atual

A fundação compila de forma isolada e ainda não é servida pelo FastAPI nem incluída no Dockerfile de produção. O aplicativo legado continua responsável pela rota `/` e por todos os fluxos reais.

A base do Vite está configurada como `/app-v2/` para a próxima fase, em que o build será integrado ao FastAPI sem substituir a aplicação atual.

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

## Regras da migração

- manter FastAPI, banco, autenticação e APIs atuais;
- preservar a identidade visual do Lombada;
- migrar por funcionalidades pequenas e reversíveis;
- não remover fluxos legados antes da paridade;
- não alterar a PWA na fase de fundação;
- adicionar o lockfile assim que o primeiro ambiente com npm concluir a instalação.

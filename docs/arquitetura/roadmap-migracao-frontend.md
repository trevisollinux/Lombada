# Roadmap resumido da migração do frontend

Este arquivo acompanha a execução prática da decisão registrada em [migracao-frontend-react.md](./migracao-frontend-react.md).

## Fases

- [x] Adicionar smoke tests do frontend atual.
- [x] Criar `frontend/` com React, TypeScript e Vite.
- [x] Publicar o novo frontend inicialmente em `/app-v2`.
- [x] Migrar shell, tema, idioma e navegação.
- [x] Migrar estante somente leitura.
- [ ] Migrar detalhe e mutações de leitura.
- [ ] Migrar diário.
- [ ] Migrar busca, obra e edições.
- [ ] Migrar explorar, feed e perfil.
- [ ] Migrar cards, retrospectiva e compartilhamento.
- [ ] Adaptar service worker e PWA ao build versionado.
- [ ] Promover o frontend React para `/` após paridade e estabilização.

## Estado do shell v2

O shell React já possui roteamento, navegação responsiva, tema, idioma, sessão compartilhada com o aplicativo atual, estados de loading/erro e estrutura das rotas principais.

## Estado da estante v2

A estante consome `/api/prateleira` e oferece filtros por status, visualização em grade ou lista, capas com fallback editorial, estados de loading/erro/vazio e detalhe somente leitura. Edição e exclusão continuam no aplicativo legado até a próxima fase.

## Regra de execução

Cada fase deve ser entregue em PR pequeno, validável e reversível. O frontend atual permanece disponível até a conclusão da paridade funcional.

# Roadmap resumido da migração do frontend

Este arquivo acompanha a execução prática da decisão registrada em [migracao-frontend-react.md](./migracao-frontend-react.md).

## Fases

- [ ] Adicionar smoke tests do frontend atual.
- [ ] Criar `frontend/` com React, TypeScript e Vite.
- [ ] Publicar o novo frontend inicialmente em `/app-v2`.
- [ ] Migrar shell, tema, idioma e navegação.
- [ ] Migrar estante somente leitura.
- [ ] Migrar detalhe e mutações de leitura.
- [ ] Migrar diário.
- [ ] Migrar busca, obra e edições.
- [ ] Migrar explorar, feed e perfil.
- [ ] Migrar cards, retrospectiva e compartilhamento.
- [ ] Adaptar service worker e PWA ao build versionado.
- [ ] Promover o frontend React para `/` após paridade e estabilização.

## Regra de execução

Cada fase deve ser entregue em PR pequeno, validável e reversível. O frontend atual permanece disponível até a conclusão da paridade funcional.

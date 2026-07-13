# Roadmap resumido da migração do frontend

Este arquivo acompanha a execução prática da decisão registrada em [migracao-frontend-react.md](./migracao-frontend-react.md).

## Fases

- [x] Adicionar smoke tests do frontend atual.
- [x] Criar `frontend/` com React, TypeScript e Vite.
- [x] Publicar o novo frontend inicialmente em `/app-v2`.
- [x] Migrar shell, tema, idioma e navegação.
- [x] Migrar estante somente leitura.
- [x] Migrar detalhe e mutações de leitura.
- [x] Migrar diário.
- [x] Migrar busca, obra e edições.
- [x] Migrar explorar.
- [x] Migrar feed.
- [x] Migrar perfil.
- [ ] Migrar cards, retrospectiva e compartilhamento.
- [ ] Adaptar service worker e PWA ao build versionado.
- [ ] Promover o frontend React para `/` após paridade e estabilização.

## Estado do shell v2

O shell React já possui roteamento, navegação responsiva, tema, idioma, sessão compartilhada com o aplicativo atual, estados de loading/erro e estrutura das rotas principais.

## Estado da estante v2

A estante consome `/api/prateleira` e oferece filtros por status, visualização em grade ou lista, capas com fallback editorial, estados de loading/erro/vazio e detalhe completo da leitura.

## Estado das mutações de leitura

O detalhe permite editar status padrão ou personalizado, nota, data, relato, visibilidade e spoiler. A exclusão exige confirmação explícita, remove também as entradas vinculadas do diário pelo contrato atual do backend e atualiza a estante sem recarregar a página.

## Estado do diário v2

O diário lista a linha do tempo real do usuário, filtra por livro e permite criar, editar e excluir entradas. Os quatro modos atuais — página, porcentagem, capítulo e anotação livre — usam os contratos existentes, incluindo total de páginas, sumário colaborativo, página estimada, privacidade, spoiler e origem “Li mais”.

## Estado do catálogo v2

A busca consulta o catálogo real por título, autor ou ISBN, exibe buscas e obras populares e abre uma rota dedicada da obra. A página combina edições locais e externas, mostra estatísticas sociais e permite registrar uma leitura com status, nota, relato, privacidade, spoiler e relação de posse ou desejo da edição.

## Estado do explorar v2

A rota `/app-v2/explorar` oferece vitrines populares e caminhos por gênero, literatura e editora. Os filtros combinam origem, gênero, editora, ordenação, idioma, capa, ISBN, críticas públicas e leituras em andamento, mantendo o estado na URL e reutilizando a página de obra para aprofundamento e registro.

## Estado do feed v2

O feed possui abas Seguindo e Descobrir, carrossel de leitores que estão lendo agora, sugestões de perfis e uma linha do tempo que combina críticas, mudanças de status de leitura e textos públicos. Leitores com conta Google podem seguir perfis, curtir e salvar críticas, criar comentários e excluir os próprios comentários. Spoilers permanecem ocultos até uma ação explícita e todas as mutações aguardam confirmação do servidor antes de atualizar a interface.

## Estado do perfil v2

A rota `/app-v2/perfil` permite editar nome, usuário e bio, trocar ou remover o avatar e gerenciar textos públicos ou privados vinculados opcionalmente a uma obra da estante. Perfis públicos vivem em `/app-v2/perfil/{handle}` e exibem métricas, estante filtrável, favoritos, leituras em andamento, críticas com spoiler, textos e listas de seguidores e seguindo. O avatar é recortado e comprimido no navegador antes do envio, e mutações de identidade, relações sociais e textos só atualizam a interface após confirmação do servidor.

## Regra de execução

Cada fase deve ser entregue em PR pequeno, validável e reversível. O frontend atual permanece disponível até a conclusão da paridade funcional.

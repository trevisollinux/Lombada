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
- [x] Migrar cards, retrospectiva e compartilhamento.
- [x] Reintegrar feature flags, analytics, onboarding e ritual “Li mais”.
- [x] Adaptar service worker e PWA ao build versionado.
- [x] Promover o frontend React para `/`, com o app legado em `/app-v1`.
- [ ] Migrar quatro essenciais, reações literárias e gerenciamento de status.
- [ ] Migrar visão de lombadas, Amazon, busca avançada e polimentos recentes.
- [ ] Adicionar espanhol ao frontend React.
- [ ] Aposentar `/app-v1` quando as pendências acima fecharem.

## Estado do shell v2

O shell React possui roteamento, navegação responsiva, tema, idioma, sessão compartilhada com o aplicativo atual, estados de loading/erro e estrutura das rotas principais. Ele também consulta `/api/features` com comportamento fail-closed e só ativa experiências experimentais quando o mesmo sinal público usado pelo frontend legado estiver ligado.

## Estado do ritual e analytics v2

A home pode exibir o onboarding “Qual livro está com você agora?” apenas para estantes vazias e, para quem está lendo, o card “Continue sua leitura”. O detalhe da estante e a home abrem a ação rápida “Li mais”, que consulta `GET /api/leitura/{id}/progresso` e grava pelo contrato existente do diário com `origem=li_mais`. O frontend envia eventos estruturais allowlisted para `/api/events` somente quando `product_analytics` estiver ativa; falhas de flags ou analytics nunca bloqueiam busca, registro, edição ou progresso.

## Estado da estante v2

A estante consome `/api/prateleira` e oferece filtros por status, visualização em grade ou lista, capas com fallback editorial, estados de loading/erro/vazio e detalhe completo da leitura. A visão física de lombadas adicionada posteriormente ao frontend legado ainda está pendente.

## Estado das mutações de leitura

O detalhe permite editar status padrão ou personalizado, nota, data, relato, visibilidade e spoiler. A exclusão exige confirmação explícita, remove também as entradas vinculadas do diário pelo contrato atual do backend e atualiza a estante sem recarregar a página. Status personalizados podem ser usados, mas sua criação e exclusão ainda dependem do frontend legado.

## Estado do diário v2

O diário lista a linha do tempo real do usuário, filtra por livro e permite criar, editar e excluir entradas. Os quatro modos atuais — página, porcentagem, capítulo e anotação livre — usam os contratos existentes, incluindo total de páginas, sumário colaborativo, página estimada, privacidade, spoiler e origem “Li mais”.

## Estado do catálogo v2

A busca consulta o catálogo real por título, autor ou ISBN, exibe buscas e obras populares e abre uma rota dedicada da obra. A página combina edições locais e externas, mostra estatísticas sociais e permite registrar uma leitura com status, nota, relato, privacidade, spoiler e relação de posse ou desejo da edição. Paginação, filtro por estilo, cadastro manual e links da Amazon adicionados ao legado ainda estão pendentes.

## Estado do explorar v2

A rota `/explorar` oferece vitrines populares e caminhos por gênero, literatura e editora. Os filtros combinam origem, gênero, editora, ordenação, idioma, capa, ISBN, críticas públicas e leituras em andamento, mantendo o estado na URL e reutilizando a página de obra para aprofundamento e registro.

## Estado do feed v2

O feed possui abas Seguindo e Descobrir, carrossel de leitores que estão lendo agora, sugestões de perfis e uma linha do tempo que combina críticas, mudanças de status de leitura e textos públicos. Leitores com conta Google podem seguir perfis, curtir e salvar críticas, criar comentários e excluir os próprios comentários. Spoilers permanecem ocultos até uma ação explícita e todas as mutações aguardam confirmação do servidor antes de atualizar a interface. As três reações literárias adicionadas depois ao legado ainda estão pendentes.

## Estado do perfil v2

A rota `/perfil` permite editar nome, usuário e bio, trocar ou remover o avatar e gerenciar textos públicos ou privados vinculados opcionalmente a uma obra da estante. Perfis públicos vivem em `/perfil/{handle}` e exibem métricas, estante filtrável, favoritos, leituras em andamento, críticas com spoiler, textos e listas de seguidores e seguindo. O avatar é recortado e comprimido no navegador antes do envio, e mutações de identidade, relações sociais e textos só atualizam a interface após confirmação do servidor. A seleção deliberada dos quatro essenciais ainda está pendente.

## Estado das memórias v2

A rota `/memorias` reúne retrospectivas semanais e mensais baseadas no diário, com navegação pelos doze períodos anteriores, métricas, destaques e estados vazios. A mesma área calcula uma retrospectiva acumulada da estante a partir dos livros marcados como lidos. Um único renderer de canvas produz imagens verticais para leitura, crítica, entrada do diário e retrospectivas, com tema claro, escuro ou automático, capa original ou editorial, trecho opcional, proteção de spoiler, compartilhamento nativo e download como fallback. O detalhe da estante e cada entrada do diário abrem o mesmo editor de card.

## Corte para a raiz

O React responde `/` e as rotas `/explorar`, `/explorar/editoras`, `/obra`, `/feed`, `/estante`, `/diario`, `/memorias` e `/perfil`. `/app-v2` e `/v3-kimi` redirecionam com 308 para o caminho equivalente na raiz.

O app legado ficou inteiro em `/app-v1`, sem manifest e sem service worker: quem controla o escopo `/` passou a ser o worker do React, que apaga os caches `lombada-shell-*` do worker anterior — sem isso, quem já tinha o PWA instalado continuaria recebendo o shell antigo.

A lista de editoras dentro do app mudou de `/editoras` para `/explorar/editoras`, porque `/editoras` continua sendo a página pública renderizada no servidor. As demais páginas do FastAPI (`/u/{handle}`, `/editora/{slug}`, `/blog`, `/sobre`, `/quem-somos`, `/contribua`, `/privacidade`, `/api-docs`, `/admin`) seguem intactas.

O backend só devolve o `index.html` para as rotas declaradas em `SPA_ROUTES` (`frontend_app.py`); qualquer outro caminho desconhecido continua 404 do servidor. Uma rota nova no React Router precisa entrar nessa lista e em `APP_ROUTES` (`frontend/public/sw.js`), senão o acesso direto e o refresh nela respondem 404.

Sem `frontend/dist`, a raiz cai para o app legado em vez de derrubar o site.

## Regra de execução

Cada fase deve ser entregue em PR pequeno, validável e reversível. O app legado permanece disponível em `/app-v1` até a conclusão das pendências de paridade.

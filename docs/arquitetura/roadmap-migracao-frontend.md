# Roadmap resumido da migração do frontend

Este arquivo acompanha a execução prática da decisão registrada em [migracao-frontend-react.md](./migracao-frontend-react.md).

> **Auditoria de 26/07/2026.** As fases abaixo foram reconferidas contra o código
> em `frontend/src`. Vários itens estavam desmarcados mas já entregues nos PRs de
> "gaps" (#347–#354); a lista agora reflete o que existe no repositório, com a
> referência de arquivo de cada um. Onde a entrega é parcial, o texto diz o que
> falta em vez de marcar ou desmarcar o item inteiro.

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
- [x] Migrar quatro essenciais (`features/profile/EssentialBooks.tsx`).
- [x] Migrar reações literárias (`features/reactions/LiteraryReactions.tsx` e `ReactionInbox.tsx`).
- [x] Migrar visão de lombadas (`features/shelf/SpineShelf.tsx`, montado em `pages/ShelfPage.tsx`).
- [x] Migrar link da Amazon (`features/catalog/AmazonBuyLink.tsx`).
- [x] Migrar cadastro manual de livro (`features/catalog/ManualBookForm.tsx`).
- [x] Adicionar espanhol ao frontend React (`i18n.ts` aceita `pt-BR`, `en` e `es`).
- [x] Adaptar service worker e PWA ao build versionado (`main.tsx` registra o `sw.js` a partir do `BASE_URL`, só em produção).
- [ ] **Concluir a busca avançada** — o sheet de filtros existe; faltam paginação e filtro por estilo (ver “Estado do catálogo v2”).
- [ ] **Concluir o gerenciamento de status** — usar status personalizado já funciona; criar e excluir, não (ver “Estado das mutações de leitura”).
- [ ] **Promover o frontend React para `/`** após nova auditoria de paridade e estabilização.

## Estado do shell v2

O shell React possui roteamento, navegação responsiva, tema, idioma, sessão compartilhada com o aplicativo atual, estados de loading/erro e estrutura das rotas principais. Ele também consulta `/api/features` com comportamento fail-closed e só ativa experiências experimentais quando o mesmo sinal público usado pelo frontend legado estiver ligado.

As rotas registradas em `App.tsx` são: busca (índice), `explorar`, `editoras`, `obra`, `feed`, `estante`, `diario`, `memorias`, `perfil` e `perfil/:handle`, mais a rota de erro. O shell também carrega o aviso de nova versão (`components/VersionWatcher.tsx`, que consulta `/api/version`), o `ColdStartNotice` e a central de notificações (`features/notifications/`).

## Estado do ritual e analytics v2

A home pode exibir o onboarding “Qual livro está com você agora?” apenas para estantes vazias e, para quem está lendo, o card “Continue sua leitura”. O detalhe da estante e a home abrem a ação rápida “Li mais”, que consulta `GET /api/leitura/{id}/progresso` e grava pelo contrato existente do diário com `origem=li_mais`. O frontend envia eventos estruturais allowlisted para `/api/events` somente quando `product_analytics` estiver ativa; falhas de flags ou analytics nunca bloqueiam busca, registro, edição ou progresso.

A celebração pós-leitura com marco e confete (`features/catalog/PostReadCelebration.tsx`) também já está no React.

## Estado da estante v2

A estante consome `/api/prateleira` e oferece filtros por status, visualização em grade ou lista, capas com fallback editorial, estados de loading/erro/vazio e detalhe completo da leitura. **A visão física de lombadas foi migrada** (`features/shelf/SpineShelf.tsx`), incluindo abrir o card ao clicar numa lombada.

## Estado das mutações de leitura

O detalhe permite editar status padrão ou personalizado, nota, data, relato, visibilidade e spoiler. A nota usa a régua de estrelas com meia-estrela (`components/StarRating.tsx`) no lugar do `<select>`. A exclusão exige confirmação explícita, remove também as entradas vinculadas do diário pelo contrato atual do backend e atualiza a estante sem recarregar a página.

**Pendência real:** `ReadingEditorForm` lê a lista de status por `GET /api/eu/status` e permite *escolher* um status personalizado já existente, mas não há criação nem exclusão de status personalizados no React — isso segue apenas no frontend legado (`_status_customizados` em `main.py`).

## Estado do diário v2

O diário lista a linha do tempo real do usuário, filtra por livro e permite criar, editar e excluir entradas. Os quatro modos atuais — página, porcentagem, capítulo e anotação livre — usam os contratos existentes, incluindo total de páginas, sumário colaborativo, página estimada, privacidade, spoiler e origem “Li mais”.

## Estado do catálogo v2

A busca consulta o catálogo real por título, autor ou ISBN, exibe buscas e obras populares e abre uma rota dedicada da obra. A página combina edições locais e externas, mostra estatísticas sociais e permite registrar uma leitura com status, nota, relato, privacidade, spoiler e relação de posse ou desejo da edição. **Cadastro manual de livro e link da Amazon foram migrados.** O sheet de filtros (`features/catalog/SearchFilterSheet.tsx`) cobre editora, ordenação (relevância, mais lidos, melhor avaliados, recentes) e as alternâncias de com críticas, lendo agora, com capa, com ISBN e português.

Existe também uma rota dedicada de editoras em `/app-v2/editoras` (`pages/PublishersPage.tsx`), equivalente à `/editoras` do legado.

**Pendências reais:** a busca do React não tem paginação nem “carregar mais” — devolve só a primeira página de resultados; e o filtro por estilo presente no legado (`static/app.js`) não foi migrado.

## Estado do explorar v2

A rota `/app-v2/explorar` oferece vitrines populares e caminhos por gênero, literatura e editora. Os filtros combinam origem, gênero, editora, ordenação, idioma, capa, ISBN, críticas públicas e leituras em andamento, mantendo o estado na URL e reutilizando a página de obra para aprofundamento e registro.

## Estado do feed v2

O feed possui abas Seguindo e Descobrir, carrossel de leitores que estão lendo agora, sugestões de perfis e uma linha do tempo que combina críticas, mudanças de status de leitura e textos públicos. Leitores com conta Google podem seguir perfis, curtir e salvar críticas, criar comentários e excluir os próprios comentários. Spoilers permanecem ocultos até uma ação explícita e todas as mutações aguardam confirmação do servidor antes de atualizar a interface. **As reações literárias foram migradas**, tanto nas críticas do feed quanto no inbox de retorno social do perfil.

## Estado do perfil v2

A rota `/app-v2/perfil` permite editar nome, usuário e bio, trocar ou remover o avatar e gerenciar textos públicos ou privados vinculados opcionalmente a uma obra da estante. Perfis públicos vivem em `/app-v2/perfil/{handle}` e exibem métricas, estante filtrável, favoritos, leituras em andamento, críticas com spoiler, textos e listas de seguidores e seguindo. O avatar é recortado e comprimido no navegador antes do envio, e mutações de identidade, relações sociais e textos só atualizam a interface após confirmação do servidor. **A seleção deliberada dos quatro essenciais foi migrada** (`features/profile/EssentialBooks.tsx`).

## Estado das memórias v2

A rota `/app-v2/memorias` reúne retrospectivas semanais e mensais baseadas no diário, com navegação pelos doze períodos anteriores, métricas, destaques e estados vazios. A mesma área calcula uma retrospectiva acumulada da estante a partir dos livros marcados como lidos. Um único renderer de canvas produz imagens verticais para leitura, crítica, entrada do diário e retrospectivas, com tema claro, escuro ou automático, capa original ou editorial, trecho opcional, proteção de spoiler, compartilhamento nativo e download como fallback. O detalhe da estante e cada entrada do diário abrem o mesmo editor de card.

## O que falta para promover o React para `/`

Hoje o legado responde em `/` (rota raiz em `main.py`) e o React vive em
`/app-v2` (`frontend_v2.py`), com `/v3-kimi` redirecionando 308 para `/app-v2`.
Antes da promoção:

1. Fechar as três pendências acima: paginação da busca, filtro por estilo e
   criação/exclusão de status personalizados.
2. Rodar a auditoria de paridade legado × React e registrar o resultado aqui.
3. Definir o destino do legado — se vira fallback numa rota própria ou sai do ar
   — e o plano de rollback da troca de raiz.

## Regra de execução

Cada fase deve ser entregue em PR pequeno, validável e reversível. O frontend atual permanece disponível até a conclusão de uma nova auditoria de paridade.

Ao concluir uma fase, **atualize este arquivo no mesmo PR**. A auditoria de
26/07/2026 encontrou sete itens entregues mas ainda desmarcados aqui, o que fez
o roadmap descrever um estado do projeto que já não existia.

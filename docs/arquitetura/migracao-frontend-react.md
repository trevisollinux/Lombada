# Avaliação arquitetural e plano de migração do frontend para React

> Status: proposta aprovada para execução incremental  
> Data da avaliação: 12 de julho de 2026  
> Escopo: frontend interativo do Lombada  
> Backend: permanece em FastAPI + SQLModel + PostgreSQL

## 1. Resumo executivo

O Lombada já chegou ao ponto em que React faz sentido.

Isso não significa que o frontend atual seja ruim, nem que HTML, CSS e JavaScript puros sejam incapazes de produzir uma interface sofisticada. O problema é que o aplicativo cresceu além do tamanho em que uma SPA manual, concentrada em poucos arquivos globais, continua previsível e segura para evoluir.

A recomendação é:

> Migrar o frontend interativo para React + TypeScript + Vite, de forma gradual, mantendo o FastAPI, o banco, as APIs e o aplicativo atual funcionando durante a transição.

Não se recomenda:

- reescrever toda a aplicação de uma vez;
- migrar o backend para Node;
- introduzir Next.js neste momento;
- trocar simultaneamente framework, design, autenticação, banco e PWA;
- substituir a identidade visual atual por uma biblioteca genérica de componentes.

A migração deve acontecer em vários pull requests pequenos, com o frontend atual disponível como fallback até que o novo frontend alcance paridade funcional.

---

## 2. Contexto atual

O repositório descreve o Lombada como uma aplicação de catálogo e registro de leituras com:

- FastAPI;
- SQLModel/SQLAlchemy;
- PostgreSQL;
- deploy no Railway;
- frontend SPA sem etapa de build;
- `index.html`;
- `static/app.js`;
- `static/app.css`.

No momento desta avaliação, os principais arquivos do frontend possuem aproximadamente:

- `static/app.js`: 4.799 linhas;
- `static/app.css`: 2.265 linhas;
- `index.html`: estrutura central das telas, navegação, modais e folhas de ação.

O `app.js` concentra, no mesmo escopo:

- estado da conta;
- busca;
- filtros;
- obras e edições;
- estante;
- diário;
- feed;
- perfil;
- navegação;
- tema;
- idioma;
- PWA;
- service worker;
- retrospectiva;
- geração de cards em canvas;
- modais;
- interações sociais;
- chamadas à API.

Portanto, o problema atual não é falta de JavaScript. O Lombada já possui bastante JavaScript. O problema é que o código atual está desempenhando manualmente responsabilidades que, em um projeto maior, normalmente pertencem a uma arquitetura de componentes, roteamento, gerenciamento de dados e ciclo de vida de interface.

---

## 3. O código atual é ruim?

Não. Ele apenas ficou grande demais para o formato original.

Existem várias decisões boas no frontend atual:

- função central de escape de conteúdo antes de montar HTML;
- delegação de eventos;
- tratamento global de teclado;
- fechamento de modais com Escape;
- suporte a elementos acessíveis via teclado;
- fallback de capas;
- estados de carregamento e erro;
- internacionalização;
- tema claro e escuro;
- histórico de navegação;
- suporte a deep links;
- PWA;
- prevenção de cache antigo de assets críticos;
- compartilhamento nativo;
- geração de imagens via canvas;
- respeito a `prefers-reduced-motion`.

Esses pontos mostram que o aplicativo não foi construído de forma descuidada. O limite é arquitetural: cada nova funcionalidade precisa ser conectada manualmente a várias outras partes.

Um exemplo é a troca de idioma. Em vez de a interface reagir declarativamente a uma mudança de estado, o código precisa chamar explicitamente várias funções de renderização para chips, editoras, estante, diário, onboarding, filtros, edições, formulário, perfil, feed e detalhe do livro.

Isso é um sinal de que a aplicação perdeu uma fonte previsível de verdade: uma mudança de estado precisa conhecer manualmente todos os pedaços da tela que devem ser redesenhados.

---

## 4. Principais problemas da arquitetura atual

### 4.1. Estado global muito acoplado

O frontend mantém dezenas de variáveis globais, incluindo dados como:

- resultados da busca;
- obras agrupadas;
- edições atuais;
- obra social aberta;
- prateleira;
- entradas do diário;
- feed;
- leitores descobertos;
- filtros;
- paginação;
- estado de navegação;
- card atual;
- tema do card;
- visualizações em grade ou lista;
- estado de instalação da PWA.

Esse desenho gera riscos crescentes:

- uma tela pode alterar dados usados por outra;
- uma função pode depender de variáveis que não aparecem em seus argumentos;
- o comportamento pode depender da ordem em que funções anteriores foram executadas;
- fica difícil saber quais dados precisam existir antes de renderizar uma tela;
- uma alteração localizada pode quebrar uma área distante;
- mudanças feitas por ferramentas de IA ficam mais difíceis de revisar com segurança.

O aplicativo continua funcionando, mas a previsibilidade diminui à medida que novas funcionalidades são adicionadas.

### 4.2. Renderização manual extensa

Grande parte da interface é criada com templates de string e aplicada via `innerHTML`.

Isso aparece em:

- sugestões de busca;
- filtros;
- chips ativos;
- editoras;
- resultados;
- cards de livros;
- detalhes de leitura;
- formulários;
- feed;
- perfil;
- diário;
- retrospectiva;
- modais e sheets.

Essa abordagem pode ser segura quando todos os campos são escapados corretamente, mas estruturalmente traz dificuldades:

- HTML, comportamento e dados ficam misturados;
- é fácil esquecer de escapar um novo campo;
- componentes visuais são duplicados em diferentes renderizações;
- mudanças pequenas podem exigir substituir grandes blocos de HTML;
- elementos podem perder foco ou estado ao serem recriados;
- acessibilidade precisa ser controlada manualmente em cada template;
- testar uma unidade visual isolada é difícil.

React não elimina a necessidade de cuidado, mas transforma essas áreas em componentes com entradas, saídas e ciclo de vida mais claros.

### 4.3. Requisições distribuídas pelo arquivo

Há várias chamadas `fetch()` espalhadas pelo frontend para:

- conta;
- status personalizados;
- buscas populares;
- editoras;
- obras populares;
- feed;
- perfis;
- seguidores;
- denúncias;
- estante;
- diário;
- leituras;
- críticas;
- comentários;
- notificações.

Cada ponto precisa resolver individualmente:

- tratamento de `response.ok`;
- conversão para JSON;
- loading;
- erro de rede;
- erro de autenticação;
- mensagens ao usuário;
- atualização do estado local;
- atualização de outras telas relacionadas;
- concorrência entre requisições.

Não há uma camada única e tipada de acesso à API. Também não há uso consistente de cancelamento explícito de requisições anteriores com `AbortController`.

Em buscas rápidas, por exemplo, uma resposta mais antiga pode teoricamente chegar depois de uma resposta mais nova e sobrescrever o estado mais recente.

Um frontend reorganizado deve possuir um `apiClient` central, erros padronizados, tipos de retorno e cancelamento de requisições quando necessário.

### 4.4. Crescimento do CSS

O CSS atual possui uma identidade visual forte e vários pontos positivos:

- tokens de cor;
- tipografia editorial;
- sombras consistentes;
- temas;
- foco visível;
- comportamento responsivo;
- suporte a redução de movimento;
- linguagem visual própria.

O problema não é a qualidade visual. O problema é que todas as funcionalidades continuam sendo adicionadas ao mesmo arquivo, que já ultrapassa duas mil linhas.

React não exige trocar esse CSS.

A estratégia recomendada é:

- preservar a identidade visual;
- preservar os tokens e variáveis CSS;
- separar estilos por componente ou funcionalidade;
- evitar Tailwind, Material UI ou outro sistema visual durante a migração;
- alterar design e arquitetura em momentos diferentes.

### 4.5. Navegação artesanal

O aplicativo já implementa comportamento de SPA por conta própria:

- estado atual de aba e subtela;
- `history.pushState`;
- `history.replaceState`;
- deep links;
- recuperação de estado;
- botão voltar;
- telas ocultadas e exibidas manualmente.

Esse sistema funciona, mas tende a ficar mais complexo com novas rotas, filtros persistentes, perfis, obras, listas e compartilhamentos.

React Router permitiria representar a navegação como URLs explícitas e testáveis.

### 4.6. Testabilidade limitada

O frontend atual não possui uma estrutura clara de testes de componentes.

Como funções de renderização dependem de muitas variáveis globais e do DOM inteiro, fica difícil testar isoladamente:

- um card;
- um filtro;
- um formulário;
- um estado de erro;
- uma edição;
- uma entrada do diário.

Antes e durante a migração, devem ser adicionados testes de fluxo com Playwright e, no frontend novo, testes de componentes e funções puras.

---

## 5. React deixaria o aplicativo visualmente melhor?

Não automaticamente.

React melhora principalmente:

- organização do código;
- consistência dos estados;
- reutilização de componentes;
- previsibilidade de atualização da interface;
- testabilidade;
- segurança ao adicionar funcionalidades;
- velocidade de evolução;
- capacidade de dividir o trabalho em áreas independentes.

A qualidade visual continuará dependendo de:

- design;
- hierarquia;
- tipografia;
- espaçamento;
- animações;
- capas;
- estados de carregamento;
- qualidade da navegação;
- feedback das ações.

É possível fazer um site ruim em React e um site excelente em HTML puro.

No Lombada, React permitiria construir e manter com menor risco:

- transições entre busca, obra, edição e registro;
- filtros instantâneos;
- skeletons;
- feedback otimista ao seguir, curtir ou editar;
- modais e bottom sheets consistentes;
- preservação de posição de rolagem;
- estados vazios e de erro;
- paginação ou infinite scroll;
- uma experiência desktop mais rica sem duplicar lógica.

A conclusão correta é:

> React não torna o design bonito por si só. React torna mais seguro construir e manter um design mais sofisticado.

---

## 6. Por que React faz sentido agora

A interface já é naturalmente dividida em áreas de produto:

- busca;
- filtros;
- obra;
- edições;
- registro de leitura;
- estante;
- diário;
- explorar;
- feed;
- perfil;
- detalhe do livro;
- compartilhamento;
- retrospectiva;
- notificações.

Essas áreas podem ser transformadas em componentes e funcionalidades independentes sem reescrever o backend.

Avaliação resumida:

| Aspecto | Nota |
|---|---:|
| Qualidade atual como MVP funcional | 6/10 |
| Adequação da arquitetura atual para continuar crescendo | 3,5/10 |
| Necessidade de reorganização arquitetural | 8/10 |
| Adequação de React para o projeto | 8,5/10 |
| Risco de uma reescrita completa | 9/10 |
| Benefício de uma migração incremental | 9/10 |

---

## 7. Por que não apenas dividir o `app.js`

Dividir o arquivo atual em módulos ajudaria a localizar código.

Uma possível divisão seria:

```text
search.js
shelf.js
diary.js
feed.js
profile.js
navigation.js
api.js
share-card.js
```

Porém, isso resolveria apenas parte do problema. Continuariam existindo:

- estado global compartilhado;
- renderizações manuais;
- dependências ocultas entre módulos;
- necessidade de disparar renderizações manualmente;
- sincronização artesanal entre URL, tela e dados;
- templates HTML dentro de strings;
- dificuldade de testar componentes.

Uma modularização prévia pequena ainda pode ser útil para extrair funções puras, mas não se recomenda investir em transformar o frontend vanilla atual em um framework artesanal.

As melhores extrações prévias são:

- cliente de API;
- tipos e contratos de dados;
- funções de formatação;
- internacionalização;
- geração de cards em canvas;
- utilitários de capa;
- funções puras de filtros.

---

## 8. Arquitetura recomendada

### 8.1. Manter

- FastAPI;
- SQLModel/SQLAlchemy;
- PostgreSQL;
- autenticação e sessões atuais;
- cookies atuais;
- rotas `/api/*`;
- Railway;
- catálogo;
- raspadores;
- páginas públicas renderizadas pelo backend;
- identidade visual;
- CSS base;
- PWA, até sua migração controlada.

O backend já possui uma separação parcial em módulos como:

- `models`;
- `auth`;
- `api_publica`;
- `busca`;
- `fontes`;
- `publica`;
- `editoras`;
- `landing`;
- `blog`.

Não há justificativa para reescrever o backend como parte desta migração.

### 8.2. Adicionar

- React;
- TypeScript;
- Vite;
- React Router;
- cliente de API tipado;
- testes de componentes;
- testes de fluxo com Playwright;
- opcionalmente TanStack Query para dados vindos do servidor.

Estrutura sugerida:

```text
frontend/
  src/
    app/
      App.tsx
      router.tsx

    components/
      BookCover/
      BookCard/
      BottomNav/
      Dialog/
      EmptyState/
      LoadingState/

    features/
      search/
      editions/
      readings/
      shelf/
      diary/
      feed/
      profile/
      share-card/

    services/
      api.ts

    types/
      book.ts
      reading.ts
      user.ts
      feed.ts

    styles/
      tokens.css
      global.css
```

---

## 9. Componentes naturais do Lombada

Estrutura de alto nível:

```tsx
<AppShell>
  <TopBar />
  <CurrentRoute />
  <BottomNavigation />
</AppShell>
```

Busca:

```tsx
<SearchPage>
  <SearchInput />
  <SearchFiltersSheet />
  <SearchResults />
</SearchPage>
```

Obra e edições:

```tsx
<WorkPage>
  <WorkHeader />
  <EditionList />
  <CommunityReviews />
</WorkPage>
```

Estante:

```tsx
<ShelfPage>
  <ShelfFilters />
  <ShelfGrid />
</ShelfPage>
```

Diário:

```tsx
<DiaryPage>
  <DiaryEntryForm />
  <DiaryTimeline />
</DiaryPage>
```

Detalhe e compartilhamento:

```tsx
<BookDetailDialog>
  <BookMetadata />
  <Rating />
  <Review />
  <ShareCardEditor />
</BookDetailDialog>
```

Cada parte deve ter:

- propriedades explícitas;
- estado local quando apropriado;
- ações declaradas;
- loading próprio;
- estado de erro próprio;
- estado vazio próprio;
- testes independentes.

---

## 10. TypeScript é tão importante quanto React

A migração não deve usar React com JavaScript puro.

O domínio possui objetos semelhantes, mas diferentes:

```ts
type Obra = {
  id: number;
  titulo: string;
  autor?: string;
  ano?: number;
  descricao?: string;
};

type Edicao = {
  id: number;
  obraId: number;
  editora?: string;
  tradutor?: string;
  isbn?: string;
  capaUrl?: string;
  idioma?: string;
};

type Leitura = {
  id: number;
  edicaoId: number;
  status: string;
  nota?: number;
  relato?: string;
  publico: boolean;
  spoiler: boolean;
};
```

TypeScript ajuda a detectar antes do deploy diferenças como:

- `ano` versus `ano_edicao`;
- `capa` versus `capa_url`;
- `usuario` como objeto versus handle;
- `nota` como string versus número;
- campos opcionais ausentes;
- respostas diferentes entre feed e estante.

Isso é especialmente importante quando uma parte relevante das alterações é realizada com Codex ou outras ferramentas de IA.

---

## 11. Estratégia de estado

Não se recomenda substituir dezenas de variáveis globais por um único React Context gigante.

### 11.1. Estado da URL

Deve incluir:

- rota atual;
- termo de busca quando compartilhável;
- obra aberta;
- perfil aberto;
- filtros que devam sobreviver ao botão voltar;
- paginação relevante.

Gerenciado pelo React Router.

### 11.2. Estado vindo do servidor

Inclui:

- estante;
- feed;
- perfil;
- editoras;
- resultados de busca;
- diário;
- notificações;
- detalhes de obra.

Gerenciado por uma camada de consulta e cache. TanStack Query é uma opção adequada, mas pode entrar somente quando necessário.

### 11.3. Estado local da interface

Inclui:

- modal aberto;
- sheet de filtros;
- tema selecionado;
- texto sendo digitado;
- capa selecionada no card;
- slide atual da retrospectiva;
- estados temporários de formulário.

Gerenciado dentro dos componentes.

### 11.4. Redux

Não há necessidade de Redux neste momento.

---

## 12. Por que não usar Next.js agora

Next.js faria mais sentido se o objetivo fosse:

- substituir o backend;
- mover autenticação e APIs para Node;
- renderizar toda a aplicação com o mesmo framework JavaScript;
- abandonar a estrutura pública existente em FastAPI.

Esse não é o caso.

O Lombada já possui:

- backend funcional;
- banco conectado;
- sessões e autenticação;
- APIs;
- páginas públicas;
- blog;
- páginas de editoras;
- perfis públicos;
- deploy configurado.

Adicionar Next.js criaria duas camadas de backend e aumentaria:

- complexidade de deploy;
- configuração de cookies;
- regras de autenticação;
- roteamento;
- consumo de recursos;
- risco de CORS;
- manutenção.

A combinação recomendada é:

```text
FastAPI
├── /api/*
├── /u/*
├── /editora/*
├── /blog/*
├── páginas públicas
└── frontend React compilado
```

---

## 13. Páginas públicas não precisam migrar inicialmente

Devem permanecer em Python/HTML nesta fase:

- landing page;
- quem somos;
- blog;
- privacidade;
- índice de editoras;
- página pública da editora;
- perfil público compartilhável;
- textos públicos.

Essas páginas se beneficiam de HTML pronto para:

- mecanismos de busca;
- prévias de compartilhamento;
- WhatsApp;
- robôs;
- carregamento inicial simples.

O primeiro alvo deve ser somente o aplicativo interativo.

---

## 14. Atenção especial à PWA

A PWA é uma das áreas de maior risco da migração.

O service worker atual mantém uma lista fixa de arquivos do app shell e utiliza estratégias `network-first` para navegação e assets críticos. Entre os arquivos conhecidos estão:

```text
/static/app.js
/static/app.css
/static/i18n.js
/static/ux-fixes.js
```

O Vite gera normalmente arquivos versionados:

```text
assets/index-D8aZ31.js
assets/index-Ba72f.css
```

Se o frontend for substituído sem adaptar o service worker, podem ocorrer:

- aplicativo instalado preso em versão antiga;
- HTML novo carregando JavaScript antigo;
- tela branca após deploy;
- atualização em loop;
- cache quebrado;
- referências a assets inexistentes.

A PWA deve ser migrada apenas depois que o frontend React estiver estável.

Até esse ponto, o React pode funcionar em uma rota separada, como `/app-v2`, sem assumir imediatamente a raiz da aplicação.

---

## 15. Migração incremental proposta

### Etapa 0 — rede de segurança

Antes de trocar a arquitetura, criar testes de fluxo para:

- abertura anônima;
- login quando aplicável;
- busca;
- abertura de obra;
- seleção de edição;
- registro de leitura;
- edição de leitura;
- exclusão de leitura;
- estante;
- diário;
- troca de idioma;
- troca de tema;
- botão voltar;
- abertura e fechamento de modais;
- geração de card;
- PWA básica.

Esses testes devem rodar no GitHub Actions.

### Etapa 1 — fundação React

Criar `frontend/` com:

- React;
- TypeScript;
- Vite;
- configuração de lint;
- configuração de testes;
- router;
- CSS base importado;
- cliente para `/api`;
- tipos básicos;
- build integrado ao FastAPI ou Railway.

FastAPI deve servir o build inicialmente em:

```text
/app-v2
```

O aplicativo atual permanece em `/`.

### Etapa 2 — shell do aplicativo

Migrar:

- cabeçalho;
- navegação inferior;
- tema;
- idioma;
- loading global;
- boundary de erro;
- roteamento.

Nenhuma funcionalidade crítica deve ser removida do app antigo.

### Etapa 3 — estante somente leitura

Migrar primeiro:

- grade e lista;
- filtros;
- card do livro;
- detalhe da leitura em modo leitura;
- estados de loading, vazio e erro.

A estante é um bom primeiro fluxo porque consome uma API conhecida e produz componentes reutilizáveis.

### Etapa 4 — mutações de leitura

Adicionar:

- alteração de nota;
- alteração de status;
- edição de crítica;
- exclusão de leitura;
- diário;
- status personalizados.

### Etapa 5 — busca e edições

Migrar o fluxo:

```text
busca
→ obra
→ edições
→ escolha da edição
→ registro
```

Nessa etapa devem entrar:

- debounce;
- cancelamento da busca anterior;
- loading consistente;
- erros padronizados;
- filtros persistidos na URL quando apropriado.

### Etapa 6 — social e perfil

Migrar:

- explorar;
- feed;
- seguir;
- curtir;
- comentários;
- perfil;
- atividade e notificações.

### Etapa 7 — cards, canvas e PWA

Migrar por último:

- canvas de compartilhamento;
- retrospectiva;
- download;
- compartilhamento nativo;
- service worker;
- instalação;
- atualização da PWA.

O renderizador de canvas não precisa ser convertido para JSX. Ele pode continuar como módulo imperativo:

```text
features/share-card/renderer.ts
```

React controla os dados, as opções e a referência ao elemento `<canvas>`.

### Etapa 8 — troca definitiva

Quando houver paridade:

1. React assume `/`;
2. o aplicativo antigo permanece temporariamente em uma rota de fallback;
3. erros e métricas são monitorados;
4. o código antigo é removido somente depois da estabilização.

---

## 16. Sequência sugerida de pull requests

A migração deve ser dividida em aproximadamente 8 a 12 PRs.

Sugestão inicial:

1. `docs: registra plano de migração do frontend para React`
2. `test: adiciona smoke tests do frontend atual`
3. `build: cria frontend React com TypeScript e Vite`
4. `feat: adiciona shell e navegação do app-v2`
5. `feat: migra estante somente leitura para React`
6. `feat: migra detalhe e mutações de leitura`
7. `feat: migra diário de leitura`
8. `feat: migra busca, obra e edições`
9. `feat: migra feed, explorar e perfil`
10. `feat: migra cards e retrospectiva`
11. `build: integra service worker ao build do Vite`
12. `refactor: promove frontend React e remove legado`

Cada PR deve ser pequeno o suficiente para:

- revisão visual no celular ou tablet;
- rollback isolado;
- validação por testes;
- comparação com o comportamento legado;
- continuidade em sessões diferentes.

---

## 17. Trabalho usando apenas celular ou tablet

A introdução de Vite exige uma etapa de build com Node, mas não exige um computador pessoal.

O fluxo pode permanecer totalmente remoto:

```text
pedido de alteração
→ Codex trabalha no repositório
→ branch e pull request
→ GitHub Actions valida
→ Railway compila
→ preview é revisado no celular ou tablet
```

O build ocorre no GitHub Actions e/ou no Railway.

A mudança prática é que o frontend deixa de ser um arquivo alterável diretamente sem compilação. Em troca, as mudanças passam a ser:

- tipadas;
- testadas;
- revisáveis;
- reproduzíveis;
- mais seguras para um projeto grande.

---

## 18. Comparação das opções

| Opção | Benefício imediato | Manutenção futura | Risco |
|---|---:|---:|---:|
| Continuar exatamente como está | Alto | Baixa | Crescente |
| Apenas dividir o JavaScript atual | Médio | Média-baixa | Baixo |
| Reescrever tudo em React | Baixo no começo | Alta depois | Muito alto |
| Migrar gradualmente para React | Médio | Alta | Controlável |

A melhor relação entre esforço, segurança e capacidade de crescimento é a migração gradual.

---

## 19. O que não deve acontecer durante a migração

Evitar simultaneamente:

- trocar React e backend;
- trocar FastAPI por Node;
- introduzir Next.js;
- introduzir Redux sem necessidade;
- introduzir Tailwind;
- introduzir Material UI;
- refazer toda a identidade visual;
- alterar banco;
- alterar autenticação;
- mudar domínio;
- substituir a PWA no primeiro PR;
- reescrever tudo em uma única entrega.

Cada uma dessas decisões pode ser avaliada separadamente no futuro.

---

## 20. Critérios para considerar a migração bem-sucedida

A migração é concluída quando:

- todos os fluxos críticos do frontend antigo existem no React;
- testes de fluxo cobrem busca, estante, registro, diário e perfil;
- URLs e botão voltar funcionam de forma previsível;
- não há regressão no modo anônimo;
- tema e idiomas continuam funcionando;
- PWA atualiza sem tela branca ou cache preso;
- cards e retrospectiva mantêm qualidade visual;
- páginas públicas continuam indexáveis;
- o build ocorre automaticamente no deploy;
- existe uma rota de rollback durante a estabilização;
- métricas e erros não mostram regressões relevantes.

---

## 21. Decisão final

A decisão técnica é iniciar a migração agora.

O caminho aprovado é:

> React + TypeScript + Vite no frontend interativo, FastAPI preservado, CSS e identidade mantidos, migração por funcionalidades e aplicativo antigo disponível como fallback até a paridade.

O código atual ainda pode receber correções pequenas durante a transição. Porém, grandes funcionalidades novas devem, sempre que possível, ser planejadas já considerando o frontend React.

Continuar adicionando recursos complexos diretamente ao `app.js` aumentaria progressivamente o custo e o risco de cada mudança.

O próximo passo recomendado é um PR de fundação que adicione testes de fumaça do frontend atual e prepare o diretório `frontend/`, sem alterar a experiência existente em produção.

---

## 22. Referências técnicas

- React — Add React to an Existing Project: https://react.dev/learn/add-react-to-an-existing-project
- React — Thinking in React: https://react.dev/learn/thinking-in-react
- Vite — Getting Started: https://vite.dev/guide/
- TypeScript: https://www.typescriptlang.org/docs/
- React Router: https://reactrouter.com/
- Playwright: https://playwright.dev/

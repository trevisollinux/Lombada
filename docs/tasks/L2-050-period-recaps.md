# L2-050 — Retrospectivas semanais e mensais

Issue: #314 · Parent: #277

## Relação com retenção

A retrospectiva devolve significado ao histórico já registrado. O leitor não precisa passar mais tempo no app; ele percebe o que construiu e encontra um motivo natural para voltar no período seguinte.

O ciclo pretendido é:

```text
ler fora do app
→ registrar sessões com Li mais
→ acumular memória no diário
→ receber síntese semanal ou mensal
→ compartilhar ou revisitar
→ continuar lendo e registrar novamente
```

## Estado inicial

A experiência permanece desligada por padrão:

```text
FF_PERIOD_RECAPS=false
```

Com a flag desligada:

- o módulo visual não é carregado;
- o endpoint responde como inexistente;
- o perfil mantém o comportamento anterior;
- nenhuma consulta adicional é executada.

## Janelas de período

Todas as janelas são definidas em:

```text
America/Sao_Paulo
```

### Semana

- começa na segunda-feira às 00:00;
- termina na segunda-feira seguinte às 00:00;
- início inclusivo e fim exclusivo.

### Mês

- começa no primeiro dia às 00:00;
- termina no primeiro dia do mês seguinte às 00:00;
- início inclusivo e fim exclusivo.

O cálculo é feito no fuso brasileiro e convertido explicitamente para UTC naive antes da consulta, compatível com os timestamps atuais do banco.

O endpoint aceita o período atual e até 12 períodos anteriores.

## Endpoint

```text
GET /api/eu/retrospectiva?period=week&offset=0
GET /api/eu/retrospectiva?period=month&offset=1
```

Parâmetros:

- `period`: `week` ou `month`;
- `offset`: `0` para o período atual, `1` para o anterior, até `12`.

A resposta usa `Cache-Control: no-store` e pertence somente à sessão atual.

## Métricas

### Sessões

Quantidade de entradas novas do diário criadas dentro da janela.

### Dias ativos

Quantidade de datas locais distintas com pelo menos uma sessão registrada.

### Livros tocados

Quantidade de leituras distintas com sessão no período.

### Páginas avançadas

A soma considera somente deltas positivos confiáveis:

1. usa `paginas_delta` persistido quando existe;
2. para registros antigos sem delta, compara a página atual com a última página conhecida da leitura;
3. uma correção para trás conta como sessão, mas soma zero páginas;
4. a primeira página sem base anterior não é tratada como páginas lidas no período.

Porcentagem e capítulo nunca são convertidos em páginas.

A resposta informa também quantas sessões de página tiveram delta calculável. A interface só destaca páginas quando existe pelo menos uma sessão calculável; caso contrário, destaca atualizações de progresso.

## Destaques por livro

Até quatro livros são apresentados, ordenados por:

1. quantidade de sessões;
2. páginas positivas avançadas;
3. atualização mais recente;
4. título como desempate estável.

Cada destaque privado pode incluir:

- título;
- autor;
- capa;
- sessões;
- páginas positivas calculadas;
- último progresso estrutural: página, porcentagem, capítulo ou sessão livre.

Notas, spoilers, críticas e conteúdo textual do diário não entram na resposta.

## Estado vazio

Períodos vazios não geram culpa, streak perdido ou alerta.

- período atual: informa que a memória começa quando houver um novo `Li mais`;
- período passado: informa apenas que não houve sessão e que isso é normal.

## Interface

O módulo `static/period-recaps.js` é carregado dinamicamente somente quando `period_recaps` está ativa.

No perfil próprio, apresenta:

- alternância entre semana e mês;
- período atual e até 12 anteriores;
- estado de carregamento, vazio e erro;
- quatro métricas agregadas;
- livros de destaque;
- ação para abrir o diário;
- card compartilhável.

O módulo envolve o `renderPerfil` existente de forma encadeável, preservando outros módulos opcionais como os Quatro Essenciais.

## Card compartilhável

O card é gerado localmente em canvas e não envia a composição para serviço externo.

Inclui:

- marca Lombada;
- período e intervalo de datas;
- métricas agregadas;
- até quatro livros de destaque;
- handle público quando disponível.

Pode ser compartilhado por `navigator.share` ou baixado como PNG.

Não inclui:

- email;
- ID Google;
- nota de diário;
- crítica;
- spoiler;
- texto privado.

## Analytics privado

O evento `period_recap` aceita somente:

- `period=week|month`;
- `action=viewed|shared|navigate`;
- `state=empty|active`.

Não envia:

- título;
- autor;
- capa;
- página;
- porcentagem;
- capítulo;
- número de sessões;
- número de páginas;
- quantidade de livros;
- conteúdo do diário.

## Acessibilidade e apresentação

- abas com `role=tablist`, `role=tab` e `aria-selected`;
- botões de navegação com rótulos;
- loading textual e retry;
- card não bloqueante dentro do perfil;
- mobile e desktop;
- temas claro e escuro;
- `prefers-reduced-motion`;
- PT/EN/ES.

## Rollout

1. Mesclar com `FF_PERIOD_RECAPS=false`.
2. Confirmar deploy sem mudança visual.
3. Ativar em ambiente controlado.
4. Testar semana e mês atuais vazios.
5. Testar período com página calculável e primeira página sem base.
6. Testar porcentagem, capítulo e sessão livre.
7. Testar correção de página para trás.
8. Navegar até períodos anteriores e voltar ao atual.
9. Gerar e compartilhar o card.
10. Confirmar analytics sem conteúdo literário ou números pessoais.
11. Acompanhar compartilhamento e retorno D7/D30 antes de ampliar rollout.

## Rollback

Definir:

```text
FF_PERIOD_RECAPS=false
```

O módulo deixa de ser carregado e o endpoint volta a responder 404. Não há migration, snapshot ou dado a remover.

## Testes cobertos

- [x] semana começa na segunda-feira em São Paulo;
- [x] mês atravessa mudança de ano;
- [x] início inclusivo e fim exclusivo;
- [x] offset inválido rejeitado;
- [x] base anterior usada para primeiro delta do período;
- [x] correção para trás não reduz nem aumenta páginas;
- [x] `paginas_delta` persistido é fonte de verdade;
- [x] primeira página sem base não inventa páginas;
- [x] porcentagem e capítulo não viram páginas;
- [x] estado vazio;
- [x] notas e spoilers ausentes da resposta;
- [x] analytics somente estrutural;
- [x] carregamento por flag;
- [x] navegação, card e três idiomas;
- [x] sintaxe do JavaScript validada no CI.

## Critério de saída

Com a flag desligada, não há mudança visual nem consulta adicional. Com a flag ligada, o perfil mostra retrospectivas semanais e mensais verdadeiras, navegáveis e compartilháveis, sem transformar dados não comparáveis em páginas e sem expor conteúdo privado.
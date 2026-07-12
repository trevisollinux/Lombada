# L2-012 — Funil de ativação, WAU e retenção por coorte

Issue: #291 · Parent: #277 · PR: #297

## 1. Contexto

O Lombada já possui testes, rollback, feature flags desligadas por padrão e uma camada privada de eventos de produto. Esta tarefa conecta essas peças para responder, por meio de totais agregados:

- as pessoas encontram livros?
- depois de encontrar, registram uma leitura?
- quem registra volta para atualizar o progresso?
- quantas pessoas usam o Lombada em uma semana?
- quantas voltam depois de 1, 7 e 30 dias?
- uma mudança futura na home melhora ou piora esses números?

O objetivo não é reconstruir a navegação de uma pessoa. O painel nunca mostra eventos individuais, IDs de usuário, email, handle, nome ou conteúdo literário.

## 2. Resultado prático

Com a coleta e o painel ativados, uma conta administrativa pode acessar:

```text
/admin/retention
```

A tela apresenta uma visão como:

```text
Últimos 7 dias

Usuários ativos: 120
WAU: 120
Buscaram um livro: 84
Abriram um livro: 61
Registraram uma leitura: 28
Atualizaram o progresso: 14
Ativação em 24h: 23,3%
Ativação em 7 dias: 31,7%
Retenção D1: 18,2%
Retenção D7: 9,4%
Retenção D30: 4,1%
```

Os valores acima são exemplos. O painel real calcula os números a partir dos eventos permitidos quando a coleta estiver ligada.

## 3. Estado inicial e segurança

Tudo permanece desligado por padrão:

- `FF_PRODUCT_ANALYTICS=false`: os eventos enviados pelo navegador são descartados e não persistidos;
- `FF_ADMIN_RETENTION_DASHBOARD=false`: o painel responde como inexistente;
- somente uma conta Google cujo email esteja em `ADMIN_EMAILS` pode acessar o painel;
- uma pessoa não autorizada recebe `404`, evitando revelar a existência da área;
- falhas de analytics não interrompem busca, leitura, diário, compartilhamento ou login;
- não existe migration destrutiva.

O deploy deste PR não inicia coleta sozinho.

## 4. Definições oficiais

### 4.1 Usuário observado

Pessoa representada por `ProductEvent.user_id`.

Eventos sem `user_id` podem servir a diagnóstico operacional, mas não entram em métricas de ativação ou retenção, porque não é possível reconhecer a mesma pessoa em dias diferentes com segurança.

Usuários com `Usuario.is_demo = true` são sempre excluídos.

### 4.2 Usuário ativo

Usuário com pelo menos um evento significativo no período:

- `search_submitted`;
- `book_opened`;
- `reading_created`;
- `reading_updated`;
- `progress_logged`;
- `share_started`;
- `profile_connected`.

`app_opened` sozinho não define uso ativo: representa abertura, não valor recebido.

### 4.3 WAU

`Weekly Active Users` é a quantidade de usuários distintos com pelo menos um evento significativo nos sete dias anteriores ao instante da consulta.

```text
WAU = usuários distintos ativos entre agora - 7 dias e agora
```

### 4.4 Ativação

Um usuário é considerado ativado quando realiza:

- `reading_created`; ou
- `progress_logged`.

A ativação representa que a pessoa saiu da exploração e começou a construir sua vida de leitura dentro do Lombada.

Janelas:

```text
ativação_24h = ativados no intervalo [primeiro evento, primeiro evento + 24h)
ativação_7d  = ativados no intervalo [primeiro evento, primeiro evento + 7 dias)
```

### 4.5 Coorte

A coorte de um usuário é definida pelo instante UTC de seu primeiro `app_opened`.

Na ausência desse evento, usa-se o primeiro evento conhecido. Esse fallback mantém os dados mensuráveis durante rollouts graduais.

### 4.6 Retenção D1, D7 e D30

Um usuário é retido quando possui pelo menos um evento significativo na janela-alvo contada a partir do instante de entrada na coorte:

- D1: de 24h, inclusive, até antes de 48h;
- D7: de 168h, inclusive, até antes de 192h;
- D30: de 720h, inclusive, até antes de 744h.

```text
retenção_Dn = usuários da coorte ativos na janela Dn / usuários elegíveis
```

Uma coorte que ainda não completou toda a janela não entra no denominador.

## 5. Funil de produto

O painel conta usuários distintos em cada capacidade:

1. `app_opened` — abriu o aplicativo;
2. `search_submitted` — enviou uma busca;
3. `book_opened` — abriu um livro;
4. `reading_created` — adicionou uma leitura à estante;
5. `progress_logged` — registrou progresso;
6. `share_started` — iniciou um compartilhamento;
7. `profile_connected` — confirmou conexão com Google.

As etapas não precisam ocorrer em ordem estrita. O objetivo é medir adoção de capacidades, não reconstruir a jornada individual.

O cadastro manual enviado para moderação **não** conta como `reading_created`, pois ainda não criou uma leitura na estante.

## 6. Instrumentação do navegador

Os scripts são carregados nesta ordem:

```html
<script src="/static/feature-flags.js?v={{APP_VERSION}}"></script>
<script src="/static/product-analytics.js?v={{APP_VERSION}}"></script>
<script src="/static/activation-events.js?v={{APP_VERSION}}"></script>
```

Com `product_analytics` desligada, eles permanecem inertes.

A instrumentação acompanha somente marcos estruturais:

- abertura do app;
- envio de busca, sem enviar a consulta;
- abertura de livro, sem enviar título, autor ou ISBN;
- criação e atualização de leitura, enviando apenas status, presença de nota e visibilidade;
- registro de progresso, enviando apenas tipo e visibilidade;
- início de compartilhamento, enviando apenas origem e tipo;
- conexão de perfil confirmada pelo retorno do login.

Eventos pequenos são enviados após um atraso curto; lotes maiores saem imediatamente. Ao esconder ou fechar a página, a fila restante tenta ser descarregada com `keepalive`. Qualquer falha é ignorada pelo fluxo principal e não gera retry infinito.

## 7. Painel administrativo

### 7.1 Acesso

O painel possui duas camadas:

1. `FF_ADMIN_RETENTION_DASHBOARD=true`;
2. sessão Google com email incluído em `ADMIN_EMAILS`.

Rotas:

```text
/admin/retention?days=30
/api/admin/retention?days=30
```

Sem qualquer uma das camadas, a resposta é `404`.

### 7.2 Conteúdo permitido

- totais por etapa;
- conversão entre etapas;
- usuários ativos;
- WAU;
- ativação em 24h e 7 dias;
- retenção D1, D7 e D30;
- tamanho das coortes;
- período, timezone e horário da geração;
- aviso se o limite de linhas for atingido.

### 7.3 Conteúdo proibido

- email, handle ou nome;
- IDs individuais de usuário;
- `client_event_id`;
- eventos individuais;
- propriedades de uma pessoa específica;
- IP, User-Agent ou conteúdo privado.

## 8. Datas e fusos

Persistência e fórmulas usam UTC.

O painel declara:

- timestamp UTC de geração;
- timezone de apresentação `America/Sao_Paulo`;
- datas das coortes apresentadas no fuso brasileiro sem alterar as janelas matemáticas em UTC.

## 9. Períodos e performance

Períodos permitidos:

- 7 dias;
- 30 dias, padrão;
- 90 dias.

Valores fora dessa allowlist são rejeitados.

A consulta:

- usa os índices de evento, usuário e timestamp;
- exclui eventos sem identidade e usuários demo no banco;
- lê no máximo `RETENTION_DASHBOARD_MAX_ROWS`, padrão 50.000 e teto 200.000;
- avisa quando o resultado foi truncado;
- não participa do carregamento normal da aplicação.

A retenção dos eventos continua limitada a 90 dias, portanto métricas além de D30 não fazem parte desta versão.

## 10. Privacidade

Continuam válidas as regras de `docs/PRODUCT_ANALYTICS.md`:

- nenhum texto livre;
- nenhum título, autor, ISBN ou consulta digitada;
- nenhum dado pessoal copiado para `ProductEvent`;
- IP e User-Agent não persistidos;
- usuários demo excluídos;
- eventos mantidos por até 90 dias;
- painel somente agregado.

## 11. Rollout

1. Mesclar o PR com ambas as flags desligadas.
2. Confirmar saúde do deploy e ausência de mudança visual.
3. Confirmar que o email administrativo correto está em `ADMIN_EMAILS`.
4. Ativar `FF_ADMIN_RETENTION_DASHBOARD=true` mantendo analytics desligado.
5. Validar `/admin/retention` vazio e o bloqueio para contas não autorizadas.
6. Ativar `FF_PRODUCT_ANALYTICS=true`.
7. Confirmar ingestão somente dos eventos allowlisted.
8. Acompanhar os primeiros dados agregados.
9. Revisar a tabela para confirmar ausência de propriedades privadas.
10. Manter a coleta ativa apenas após validação.

## 12. Rollback

1. `FF_PRODUCT_ANALYTICS=false` interrompe novas persistências;
2. `FF_ADMIN_RETENTION_DASHBOARD=false` oculta o painel;
3. revert do PR, caso o problema esteja no código;
4. a tabela aditiva permanece e segue a retenção normal.

Não é necessário apagar dados nem executar migration reversa.

## 13. Testes cobertos

- [x] painel inexistente com flag interna desligada;
- [x] painel inexistente para conta não administrativa;
- [x] resposta agregada para conta autorizada;
- [x] ausência de IDs e dados pessoais na resposta;
- [x] exclusão de usuários demo;
- [x] eventos sem `user_id` fora das métricas de pessoa;
- [x] usuário ativo contado uma vez por período;
- [x] ativação dentro e fora das janelas;
- [x] D1, D7 e D30 nos limites das janelas;
- [x] coortes imaturas fora do denominador;
- [x] períodos permitidos e rejeição de valores inválidos;
- [x] scripts carregados na ordem segura;
- [x] analytics falhando sem interromper o aplicativo;
- [x] suíte completa verde.

## 14. Entregas

- [x] Definições formais implementadas e documentadas.
- [x] Scripts de flags e analytics carregados sem bloquear o app.
- [x] Instrumentação alinhada às rotas reais de leitura e diário.
- [x] Serviço agregado de funil.
- [x] Cálculo de WAU.
- [x] Cálculo de ativação 24h e 7d.
- [x] Cálculo de D1, D7 e D30.
- [x] Exclusão de usuários demo e eventos sem identidade.
- [x] Painel protegido por flag interna e `ADMIN_EMAILS`.
- [x] Resposta sem dados individuais.
- [x] Testes completos.
- [x] Primeira execução de CI verde.

## 15. Critério de saída

Com as flags desligadas, o aplicativo mantém o comportamento atual e não persiste eventos. Com as flags ligadas e uma conta autorizada, o administrador recebe somente métricas agregadas e reproduzíveis de ativação, WAU e retenção.
# L2-012 — Funil de ativação, WAU e retenção por coorte

Issue: #291 · Parent: #277 · PR: #297

## 1. Contexto

O Lombada já possui a infraestrutura técnica necessária para evoluir com segurança:

- testes e política de rollback;
- feature flags desligadas por padrão;
- modelo privado de eventos de produto;
- endpoint de ingestão com allowlist, rate limit e retenção de 90 dias;
- cliente de analytics isolado e ainda não carregado pela interface.

Esta tarefa conecta essas peças para responder, de forma prática, às perguntas:

- as pessoas encontram livros?
- depois de encontrar, registram uma leitura?
- quem registra volta para atualizar o progresso?
- quantas pessoas usam o Lombada em uma semana?
- quantas voltam após 1, 7 e 30 dias?
- uma mudança futura na home melhora ou piora esses números?

O objetivo não é criar vigilância sobre usuários. O painel deve mostrar somente totais agregados e nunca expor uma linha de evento individual.

## 2. Resultado esperado na prática

Ao final desta tarefa, o administrador poderá consultar uma visão como:

```text
Últimos 7 dias

Usuários ativos: 120
Abriram o app: 120
Buscaram um livro: 84
Abriram um livro: 61
Registraram uma leitura: 28
Atualizaram o progresso: 14

Ativação em até 24h: 23,3%
Ativação em até 7 dias: 31,7%
Retenção D1: 18,2%
Retenção D7: 9,4%
Retenção D30: 4,1%
```

Esses valores são exemplos. O painel real calculará os números a partir dos eventos armazenados quando a coleta for ativada.

## 3. Estado inicial e segurança

Tudo permanece desligado por padrão:

- `FF_PRODUCT_ANALYTICS=false`: eventos não são persistidos;
- `FF_ADMIN_RETENTION_DASHBOARD=false`: painel não fica acessível;
- ausência de token administrativo: painel não fica acessível;
- falha de analytics nunca impede busca, leitura, diário ou login;
- não existe migration destrutiva.

O deploy deste PR não deve, sozinho, iniciar coleta em produção.

## 4. Definições oficiais

### 4.1 Usuário observado

Pessoa representada por `ProductEvent.user_id`.

Eventos sem `user_id` podem ajudar no diagnóstico operacional, mas não entram em métricas de retenção, porque não é possível reconhecer a mesma pessoa em dias diferentes com segurança.

Usuários com `Usuario.is_demo = true` são sempre excluídos.

### 4.2 Usuário ativo

Usuário com pelo menos um evento significativo no período analisado.

Eventos significativos:

- `search_submitted`;
- `book_opened`;
- `reading_created`;
- `reading_updated`;
- `progress_logged`;
- `share_started`;
- `profile_connected`.

`app_opened` sozinho não define uso ativo; ele representa abertura, não valor recebido.

### 4.3 WAU

`Weekly Active Users`: quantidade de usuários distintos com evento significativo nos últimos 7 dias completos até o instante da consulta.

Fórmula:

```text
WAU = usuários distintos com evento significativo entre agora - 7 dias e agora
```

### 4.4 Ativação principal

Um usuário é considerado ativado quando realiza pelo menos um destes eventos:

- `reading_created`;
- `progress_logged`.

A ativação representa que a pessoa saiu da exploração e começou a construir sua vida de leitura dentro do Lombada.

### 4.5 Ativação em 24 horas

Percentual de usuários da coorte que atingiram a ativação até 24 horas após seu primeiro evento observado.

```text
ativação_24h = usuários ativados em até 24h / usuários elegíveis da coorte
```

### 4.6 Ativação em 7 dias

Percentual de usuários da coorte que atingiram a ativação até 7 dias após seu primeiro evento observado.

```text
ativação_7d = usuários ativados em até 7d / usuários elegíveis da coorte
```

### 4.7 Coorte

A coorte de um usuário é a data UTC do primeiro `app_opened` registrado.

Quando não houver `app_opened`, usa-se a data UTC do primeiro evento conhecido. Esse fallback permite que dados válidos continuem mensuráveis durante implantações graduais.

### 4.8 Retenção D1, D7 e D30

Um usuário é retido quando possui pelo menos um evento significativo no dia-alvo contado a partir da data da coorte.

Janelas adotadas:

- D1: entre 24h e menos de 48h após o primeiro evento;
- D7: entre 7×24h e menos de 8×24h;
- D30: entre 30×24h e menos de 31×24h.

Fórmula:

```text
retenção_Dn = usuários da coorte ativos na janela Dn / usuários elegíveis da coorte
```

Coortes que ainda não tiveram tempo suficiente para chegar ao dia-alvo não entram no denominador dessa métrica.

## 5. Funil de produto

O funil agregado segue esta sequência:

1. `app_opened` — abriu o aplicativo;
2. `search_submitted` — procurou um livro;
3. `book_opened` — abriu o detalhe de uma obra/edição;
4. `reading_created` — adicionou uma leitura;
5. `progress_logged` — voltou para registrar progresso;
6. `share_started` — tentou compartilhar algo do Lombada;
7. `profile_connected` — conectou a conta Google.

Cada etapa contará usuários distintos, não número bruto de cliques.

As etapas não precisam acontecer em ordem estrita para aparecerem no painel. O objetivo é medir adoção de capacidades, não reconstruir a navegação individual de cada pessoa.

## 6. Instrumentação desta tarefa

Os dois scripts existentes serão carregados de forma não bloqueante:

```html
<script src="/static/feature-flags.js?v={{APP_VERSION}}"></script>
<script src="/static/product-analytics.js?v={{APP_VERSION}}"></script>
```

Com a flag desligada, eles não enviam eventos.

Marcos mínimos a instrumentar:

- abertura da aplicação;
- envio de busca;
- abertura de livro;
- criação de leitura;
- atualização de leitura;
- registro de progresso;
- início de compartilhamento;
- conexão de perfil quando houver retorno confirmado do login.

A instrumentação deve enviar somente propriedades estruturais já allowlisted, sem título, autor, ISBN, consulta digitada ou texto do usuário.

## 7. Painel administrativo

### 7.1 Acesso

O painel será protegido por duas camadas:

1. flag interna `FF_ADMIN_RETENTION_DASHBOARD=true`;
2. token administrativo comparado de forma segura.

Sem qualquer uma delas, a resposta deve ser `404`, evitando revelar que o painel existe.

### 7.2 Conteúdo permitido

O painel pode mostrar:

- totais por etapa;
- conversão percentual entre etapas;
- WAU;
- ativação 24h e 7d;
- retenção D1, D7 e D30;
- tamanho das coortes;
- período e horário de geração;
- aviso quando não houver dados suficientes.

### 7.3 Conteúdo proibido

O painel não pode mostrar:

- email, handle ou nome;
- IDs individuais de usuário;
- `client_event_id`;
- eventos individuais;
- propriedades de um usuário específico;
- IP, User-Agent ou qualquer texto privado.

## 8. Datas e fusos

Persistência e fórmulas usam UTC.

A resposta administrativa deve declarar explicitamente:

- timestamp UTC de geração;
- timezone de apresentação: `America/Sao_Paulo`;
- datas das coortes formatadas para leitura no Brasil sem alterar as janelas matemáticas em UTC.

## 9. Períodos consultáveis

O painel aceitará somente períodos controlados:

- 7 dias;
- 30 dias;
- 90 dias.

O padrão será 30 dias. Valores fora da allowlist serão rejeitados para impedir consultas caras ou inesperadas.

## 10. Performance

- consultas agregadas e limitadas;
- nenhum carregamento da tabela inteira em produção;
- índices existentes em `event_name`, `user_id` e `created_at` devem ser aproveitados;
- resultados podem usar cache curto em memória, sem cache compartilhado com rotas públicas;
- o painel não participa do carregamento normal da aplicação.

## 11. Privacidade e retenção

Continuam valendo as regras de `docs/PRODUCT_ANALYTICS.md`:

- nenhum texto livre;
- nenhum identificador de livro;
- nenhum dado pessoal copiado para `ProductEvent`;
- eventos retidos por até 90 dias;
- limpeza por script com dry-run;
- usuários demo excluídos;
- apenas agregados administrativos.

Como a retenção é de 90 dias, D30 é suportado; métricas além de 90 dias não fazem parte desta versão.

## 12. Rollout

1. Mesclar o PR com ambas as flags desligadas.
2. Confirmar saúde do deploy e ausência de mudança visual.
3. Ativar `FF_ADMIN_RETENTION_DASHBOARD=true` com analytics ainda desligado.
4. Validar painel vazio e proteção do token.
5. Ativar `FF_PRODUCT_ANALYTICS=true`.
6. Confirmar ingestão somente dos eventos allowlisted.
7. Acompanhar os primeiros dados agregados.
8. Verificar manualmente que nenhuma propriedade privada entrou na tabela.
9. Manter a coleta ativa apenas após validação.

## 13. Rollback

Ordem preferida:

1. `FF_PRODUCT_ANALYTICS=false` para interromper persistência;
2. `FF_ADMIN_RETENTION_DASHBOARD=false` para ocultar painel;
3. revert do PR, caso o problema esteja no código;
4. manter a tabela aditiva e aplicar retenção normalmente.

Não é necessário apagar dados ou executar migration reversa.

## 14. Testes obrigatórios

- painel inexistente com flag interna desligada;
- painel inexistente com token ausente/incorreto;
- resposta agregada com token correto;
- nenhum ID ou dado pessoal na resposta;
- exclusão de usuários demo;
- usuários sem `user_id` fora de ativação e retenção;
- usuário ativo contado uma vez por período;
- ativação dentro e fora das janelas de 24h/7d;
- D1/D7/D30 nos limites exatos das janelas;
- coortes imaturas fora do denominador;
- períodos permitidos e rejeição de valores inválidos;
- flags desligadas preservando comportamento atual;
- scripts de analytics falhando de forma segura;
- suíte completa verde.

## 15. Entregas marcáveis

- [ ] Definições formais implementadas e documentadas.
- [ ] Scripts de flags e analytics carregados sem bloquear o app.
- [ ] Instrumentação dos marcos essenciais.
- [ ] Serviço de agregação de funil.
- [ ] Cálculo de WAU.
- [ ] Cálculo de ativação 24h e 7d.
- [ ] Cálculo de D1, D7 e D30.
- [ ] Exclusão de usuários demo e eventos sem identidade nas métricas de pessoa.
- [ ] Endpoint administrativo protegido por flag e token.
- [ ] Resposta sem dados individuais.
- [ ] Documentação operacional atualizada.
- [ ] Testes completos.
- [ ] CI verde e revisão final.

## 16. Critério de saída

Com as flags desligadas, o aplicativo mantém o comportamento atual e não persiste eventos. Com as flags ligadas e o token correto, o administrador recebe somente métricas agregadas e reproduzíveis de ativação, WAU e retenção.
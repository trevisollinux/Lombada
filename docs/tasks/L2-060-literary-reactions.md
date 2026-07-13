# L2-060 — Reações literárias em críticas públicas

Issue: #330 · Parent: #277

## Relação com retenção

O recurso cria reciprocidade sem exigir um comentário. Uma crítica pública pode receber uma resposta curta e contextual, mostrando ao autor que sua leitura foi percebida.

```text
publicar crítica
→ outro leitor encontra a crítica no feed finito
→ escolhe uma reação literária
→ autor vê um agrupamento por livro
→ retorna ao perfil e à conversa literária
```

Não existe recompensa por abrir o app, ranking ou urgência.

## Feature flag

A experiência nasce desligada:

```text
FF_LITERARY_REACTIONS=false
```

Com a flag desligada:

- o módulo visual não é carregado;
- as rotas respondem 404;
- curtidas, comentários, salvamentos e feed atuais permanecem intactos;
- as tabelas aditivas podem existir sem efeito no produto.

## Reações iniciais

| Chave | Português | Inglês | Espanhol |
|---|---|---|---|
| `want_to_read` | Quero ler também | I want to read it too | Quiero leerlo también |
| `moved_me` | Esse me marcou | This one stayed with me | Este me marcó |
| `good_reading` | Boa leitura | Good reading | Buena lectura |

São respostas fechadas, sem texto livre.

## Modelo

### `literary_reaction`

- crítica (`leitura_id`);
- pessoa que reagiu (`usuario_id`);
- tipo;
- criação e atualização.

Restrições:

- par crítica/pessoa único;
- tipo limitado às três chaves permitidas;
- trocar de reação atualiza a mesma linha;
- remover apaga a linha.

### `literary_reaction_inbox_state`

Guarda somente o último momento em que o dono viu o agrupamento. Não existe uma linha de notificação para cada reação.

As duas tabelas são registradas antes do startup e criadas por `SQLModel.metadata.create_all`, sem migration destrutiva.

## Regras

Uma crítica recebe reações somente quando:

- é pública;
- possui relato não vazio;
- pertence a uma pessoa real, não a perfil demo.

Para reagir, a pessoa precisa:

- estar conectada ao Google;
- não ser perfil demo;
- não ser dona da crítica.

Críticas privadas ou sem relato retornam 404 para não revelar sua existência.

## API

### Consulta agregada em lote

```text
GET /api/reviews/reactions?ids=12,15,18
```

Retorna no máximo 50 críticas e somente:

- totais por tipo;
- total agregado;
- reação da própria pessoa;
- se é dona;
- se pode reagir.

Não retorna a lista de pessoas que reagiram.

### Consulta unitária

```text
GET /api/reviews/{leitura_id}/reactions
```

### Definir ou trocar

```text
PUT /api/reviews/{leitura_id}/reaction
Content-Type: application/json

{"reaction_type":"want_to_read"}
```

### Remover

```text
DELETE /api/reviews/{leitura_id}/reaction
```

A remoção é idempotente: remover novamente responde com `removed=false`.

### Agrupamento do autor

```text
GET /api/eu/reacoes-literarias?limit=20
POST /api/eu/reacoes-literarias/vistas
```

O agrupamento é por crítica/livro e contém:

- título, autor e capa do livro;
- totais por reação;
- total agregado;
- momento da reação mais recente;
- indicador de grupo ainda não visto.

Não contém:

- texto da crítica;
- nomes, handles ou emails de quem reagiu;
- uma notificação por clique;
- conteúdo do diário.

## Interface no app atual

`static/literary-reactions.js` é carregado dinamicamente apenas com a flag ativa.

Ele:

- encontra críticas existentes pelo `data-like-btn`;
- consulta os totais em lote;
- insere três chips abaixo das ações atuais;
- permite trocar ou remover a própria reação;
- mantém o fluxo de curtidas/comentários como fallback;
- insere no perfil do autor um bloco agregado por livro;
- marca os grupos como vistos somente quando o bloco está visível.

A integração não altera o renderer principal nem os componentes React. O contrato HTTP pode ser consumido pelo frontend React em um passo posterior do fluxo paralelo.

## Feed finito

Este pacote não cria paginação infinita, observador de interseção, listener de scroll ou botão de carregamento contínuo. Ele apenas enriquece os cards já entregues pelo feed atual.

## Analytics privado

Evento: `literary_reaction`.

Propriedades permitidas:

- `source=feed|work|profile`;
- `action=set|changed|removed|viewed`;
- `reaction_type=want_to_read|moved_me|good_reading|none`.

Não envia:

- título;
- autor;
- ISBN;
- ID da leitura;
- texto da crítica;
- pessoa reagente;
- contagens pessoais.

## Acessibilidade e apresentação

- botões reais com `aria-pressed`;
- estado ocupado com `aria-busy`;
- dono vê agregados sem controles acionáveis;
- mobile em uma coluna;
- claro/escuro;
- PT/EN/ES;
- `prefers-reduced-motion`.

## Rollout

1. Mesclar com `FF_LITERARY_REACTIONS=false`.
2. Confirmar deploy sem mudança visual.
3. Adicionar `FF_LITERARY_REACTIONS=true` no Railway.
4. Testar pessoa conectada reagindo a crítica de outra pessoa.
5. Trocar de tipo e confirmar que o total não duplica.
6. Remover e confirmar atualização.
7. Testar conta anônima, crítica própria, privada e demo.
8. Abrir o perfil do autor e confirmar um agrupamento por livro.
9. Confirmar que nenhuma lista de pessoas reagentes é exposta.
10. Confirmar que o feed termina no mesmo ponto de antes.

## Rollback

```text
FF_LITERARY_REACTIONS=false
```

O módulo deixa de ser carregado e as rotas retornam 404. As tabelas aditivas permanecem sem impacto.

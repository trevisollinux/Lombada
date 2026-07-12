# L2-040 — Quatro essenciais no perfil literário

Issue: #312 · Parent: #277

## Relação com retenção

O recurso cria investimento pessoal no perfil. Em vez de favoritos automáticos por nota, o leitor escolhe deliberadamente até quatro obras que o representam.

O ciclo pretendido é:

```text
construir estante
→ escolher quatro essenciais
→ organizar a própria identidade literária
→ compartilhar o card ou perfil
→ receber visitas e conexões
→ revisar a seleção ao longo do tempo
```

O objetivo não é aumentar tempo de tela, mas criar vínculo, expressão e motivo para voltar ao perfil.

## Estado inicial

A experiência permanece desligada por padrão:

```text
FF_FAVORITE_BOOKS=false
```

Com a flag desligada:

- o módulo visual não é carregado;
- as rotas respondem como inexistentes;
- o perfil público continua com o comportamento anterior;
- a tabela aditiva pode existir sem efeito visual.

## Modelo

A tabela `user_essential_book` armazena:

- usuário;
- obra;
- edição usada como referência de capa;
- posição de 1 a 4;
- timestamps.

Restrições:

- posição entre 1 e 4;
- uma posição por usuário;
- uma obra por usuário;
- nenhuma migration destrutiva.

A tabela é registrada antes do lifespan executar `SQLModel.metadata.create_all`.

## Regras de seleção

- no máximo quatro obras;
- ordem preservada;
- sem duplicatas;
- somente obras presentes na própria estante;
- usuário pode salvar uma seleção incompleta;
- usuário pode limpar tudo;
- conta Google conectada é obrigatória para persistir a seleção.

A exigência de conta conectada evita que uma identidade pública importante fique presa a uma sessão anônima descartável.

## API

### Própria seleção

```text
GET /api/eu/essenciais
PUT /api/eu/essenciais
```

Payload de gravação:

```json
{
  "work_keys": ["/works/OL1W", "/works/OL2W"]
}
```

A API valida a presença de cada obra na estante do usuário e responde com os livros já ordenados.

### Seleção pública

```text
GET /api/u/{handle}/essenciais
```

Retorna somente:

- posição;
- chave pública da obra;
- título;
- autor;
- capa;
- edição de referência.

Não retorna email, identificador Google, conteúdo privado ou estado da conta.

## Editor visual

O módulo `static/essential-books.js` é carregado dinamicamente somente quando `favorite_books` está ativa.

No perfil próprio, o leitor encontra:

- quatro posições visuais;
- botão de edição;
- lista deduplicada da própria estante;
- adicionar, remover e mover para esquerda/direita;
- estado parcial e vazio;
- salvamento explícito;
- opção de compartilhar o card.

O editor não cria busca, catálogo ou formulário paralelo.

## Perfil público

O entrypoint instala um patch idempotente no renderer já usado em `/u/{handle}`.

Quando a flag está ligada e há seleção:

- a seção “Quatro essenciais” aparece antes de “Lendo agora”;
- a ordem escolhida é preservada;
- cada capa abre a obra existente;
- seleções vazias não criam seção vazia.

Quando a consulta falha ou a tabela ainda não está pronta durante o setup assíncrono do banco, o perfil original é retornado sem interromper a página.

## Card compartilhável

O card é gerado localmente em canvas, sem enviar a composição a serviço externo.

Inclui:

- marca Lombada;
- título “Meus quatro essenciais”;
- até quatro capas;
- títulos e autores escolhidos;
- handle público.

Não inclui:

- email;
- ID interno;
- Google ID;
- críticas;
- diário;
- notas privadas.

Quando `navigator.share` aceita arquivos, usa compartilhamento nativo. Caso contrário, baixa o PNG.

## Analytics privado

O evento estrutural `essential_books` aceita somente:

- `source=profile`;
- `action=saved|cleared|shared`;
- `completion=empty|partial|complete`.

Não envia:

- título;
- autor;
- ISBN;
- `work_key`;
- posição;
- quantidade exata quando parcial;
- email.

## Acessibilidade e apresentação

- editor com `role=dialog` e `aria-modal=true`;
- fechamento por botão, fundo e tecla Escape;
- controles de ordenação com rótulos;
- estado de salvamento e mensagens em `aria-live`;
- mobile e desktop;
- temas claro e escuro;
- `prefers-reduced-motion`;
- PT/EN/ES.

## Rollout

1. Mesclar com `FF_FAVORITE_BOOKS=false`.
2. Confirmar deploy sem mudança visual.
3. Ativar em ambiente controlado.
4. Testar conta sem Google e conta conectada.
5. Testar seleção com 1, 2, 3 e 4 obras.
6. Testar remoção, reordenação e limpeza.
7. Confirmar que uma quinta obra é bloqueada.
8. Confirmar perfil público e card.
9. Confirmar ausência de dados literários nos eventos.
10. Acompanhar conclusão, compartilhamento e retorno D7.

## Rollback

Definir:

```text
FF_FAVORITE_BOOKS=false
```

O módulo deixa de ser carregado e o perfil público volta ao renderer anterior. A tabela aditiva permanece sem impacto.

## Testes cobertos

- [x] flag pública desligada por padrão;
- [x] ordem persistida;
- [x] substituição e limpeza;
- [x] limite de quatro;
- [x] duplicidade rejeitada;
- [x] livro fora da estante rejeitado;
- [x] conta Google obrigatória para salvar;
- [x] perfil público ordenado e sem seção vazia;
- [x] carregamento dinâmico por flag;
- [x] editor reutiliza a estante;
- [x] card compartilhável;
- [x] analytics estrutural sem conteúdo literário;
- [x] sintaxe do JavaScript validada no CI.

## Critério de saída

Com a flag desligada, não há mudança visual. Com a flag ligada, uma conta conectada pode escolher, ordenar, salvar e compartilhar até quatro obras da própria estante; o perfil público exibe a seleção sem expor dados privados.
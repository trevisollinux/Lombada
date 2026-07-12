# L2-024 — Feedback verdadeiro após “Li mais”

Issue: #307 · Parent: #277

## Relação com retenção

O principal ritual recorrente do Lombada é:

```text
ler fora do app
→ tocar em Li mais
→ registrar o avanço
→ perceber o progresso
→ voltar depois da próxima sessão
```

Antes desta tarefa, o salvamento terminava principalmente com uma confirmação genérica. O registro funcionava, mas o leitor precisava interpretar sozinho o que aquele número significava.

O feedback pós-sessão transforma o dado já salvo em uma resposta curta e verdadeira. Ele não recompensa abertura do app e não cria pressão; recompensa somente uma ação real de leitura registrada.

## Escopo implementado

A experiência fica atrás da flag pública:

```text
FF_PROGRESS_FEEDBACK=true
```

Com a flag desligada, o toast anterior continua intacto.

Com a flag ligada, um novo `POST /api/leitura/{id}/diario` pode gerar uma faixa editorial não bloqueante acima da navegação.

Edições de entradas antigas por `PATCH /api/diario/{id}` não geram uma segunda recompensa. O toast tradicional continua sendo usado nesses casos.

## Insights

A lógica usa somente dados já presentes no navegador antes do salvamento.

### Página

Quando existe uma página anterior confiável:

- calcula `página nova - página anterior`;
- mostra o avanço da sessão;
- reconhece maior sessão apenas quando há histórico comparável;
- trata valor igual ou menor como correção, não como avanço.

Quando não existe página anterior:

- usa o total da edição para calcular percentual, quando disponível;
- caso contrário, confirma apenas a página alcançada.

Ao alcançar ou ultrapassar o total conhecido, informa que o leitor chegou a 100%, sem marcar automaticamente como lido.

### Porcentagem

- calcula diferença em pontos percentuais quando existe valor anterior;
- reconhece maior sessão somente com histórico comparável;
- confirma o percentual atual na primeira atualização;
- trata regressão como correção.

### Capítulo e sessão livre

Não inventam páginas, minutos ou percentuais. A resposta apenas confirma que o capítulo ou a sessão foi registrado.

## Apresentação

O componente:

- usa `role=status` e `aria-live=polite`;
- não captura foco;
- não bloqueia navegação;
- oferece ação para abrir o diário;
- possui botão de fechar;
- fecha automaticamente após alguns segundos;
- respeita tema escuro, telas pequenas e `prefers-reduced-motion`;
- usa vibração curta quando suportada e quando movimento reduzido não está ativo;
- não usa confete.

## Idiomas

A cópia está disponível em:

- português do Brasil;
- inglês;
- espanhol.

## Instrumentação privada

O evento `progress_feedback` aceita apenas:

- `source`: `diary`, `quick_action`, `onboarding` ou `unknown`;
- `insight_type`: categoria estrutural do insight;
- `action`: `viewed`, `closed`, `open_diary` ou `auto_closed`.

Não são enviados:

- título;
- autor;
- ISBN;
- página atual;
- percentual atual;
- quantidade avançada;
- capítulo;
- anotação;
- consulta de busca.

Os números aparecem somente no navegador do próprio leitor.

## Métricas

A hipótese deve ser avaliada por:

- proporção de progressos que recebem feedback;
- distribuição de categorias de insight;
- abertura do diário a partir da faixa;
- segundo progresso em até sete dias;
- retenção D1 e D7 após o primeiro progresso.

Visualização da faixa isoladamente não é sucesso. O resultado esperado é repetição do ritual em outro momento de leitura.

## Guardrails

- no máximo um insight por registro;
- nenhuma mensagem sem base nos dados;
- nenhuma comparação com outros leitores;
- nenhum streak;
- nenhuma punição por ritmo;
- nenhuma conclusão automática do livro;
- nenhuma migration;
- nenhuma alteração dos dados salvos.

## Rollout

1. Mesclar com `FF_PROGRESS_FEEDBACK=false`.
2. Confirmar deploy e toast anterior.
3. Ativar `FF_PRODUCT_ANALYTICS=true` conforme a política de analytics já existente.
4. Ativar `FF_PROGRESS_FEEDBACK=true`.
5. Testar primeira atualização por página com e sem total da edição.
6. Testar segunda e terceira atualização para delta e maior sessão.
7. Testar porcentagem, capítulo e anotação sem progresso numérico.
8. Testar regressão consciente e edição de entrada antiga.
9. Testar PT/EN/ES, claro/escuro, mobile e reduced motion.
10. Acompanhar segundo progresso e retorno antes de ampliar o rollout.

## Rollback

Definir:

```text
FF_PROGRESS_FEEDBACK=false
```

A interface volta ao toast anterior. Não há migration, backfill ou dado a desfazer.

## Critério de saída

- novo registro recebe uma confirmação verdadeira quando calculável;
- correções não são celebradas como avanço;
- capítulo e sessão livre não recebem números inventados;
- edição antiga não recebe recompensa duplicada;
- com a flag desligada, o fluxo anterior permanece;
- suíte completa verde.
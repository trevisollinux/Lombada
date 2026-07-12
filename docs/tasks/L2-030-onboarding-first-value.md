# L2-030 — Onboarding orientado ao primeiro valor

Issue: #305 · Parent: #277

## Relação com retenção

O onboarding não tenta aumentar tempo de tela. Ele reduz o intervalo entre abrir o Lombada e construir algo pessoal dentro dele.

O ciclo pretendido é:

```text
escolher livro atual
→ adicionar como Lendo
→ ver o livro na home
→ avançar na leitura fora do app
→ tocar em Li mais
→ formar histórico e memória
→ ter motivo para voltar
```

Sem uma leitura pessoal, a home é principalmente descoberta. Com uma leitura atual, o Lombada passa a funcionar como acompanhamento contínuo.

## Hipótese

Usuários novos expostos a uma pergunta direta — “Qual livro está com você agora?” — terão maior taxa de primeira leitura criada e, consequentemente, maior ativação em 24 horas e retorno D1.

## Experiência

A experiência é exibida somente quando:

1. `FF_ONBOARDING_VALUE=true`;
2. o onboarding atual ainda está ativo;
3. o usuário ainda não registrou nenhuma leitura real.

O bloco apresenta:

- uma pergunta sobre o livro atual;
- explicação curta sobre home, progresso e histórico;
- CTA principal que abre e focaliza a busca existente;
- alternativa secundária para sugerir um livro ausente do catálogo;
- opção de fechar sem bloquear a navegação.

Depois que uma leitura é criada, `carregarPrateleira()` atualiza o estado e o onboarding volta automaticamente ao checklist existente, cujo próximo passo é registrar progresso por “Li mais”.

## O que não muda

- catálogo e endpoint de busca;
- formulário de leitura;
- estante e diário;
- experiência de usuários que já possuem leituras;
- comportamento com a flag desligada;
- possibilidade de ignorar ou fechar o onboarding.

## Idiomas e apresentação

A cópia está disponível em:

- português do Brasil;
- inglês;
- espanhol.

O bloco possui regras para:

- mobile e desktop;
- temas claro e escuro;
- `prefers-reduced-motion`.

## Instrumentação privada

Uma marca efêmera em `sessionStorage` identifica somente que a navegação começou pelo CTA do onboarding.

Os eventos estruturais podem receber `source=onboarding`:

- `search_submitted`;
- `book_opened`;
- `reading_created`.

A marca é removida depois que a leitura é criada. Não são enviados:

- consulta digitada;
- título;
- autor;
- ISBN;
- crítica;
- nota de diário;
- conteúdo pessoal.

## Métricas

Comparar coortes com e sem a flag:

- buscas iniciadas pelo onboarding;
- livros abertos;
- primeiras leituras criadas;
- ativação em 24 horas;
- ativação em sete dias;
- retenção D1;
- primeiro progresso registrado.

A análise deve considerar tamanho e maturidade das coortes. Abertura do app, isoladamente, não é sucesso.

## Guardrails éticos

- nenhum modal obrigatório;
- nenhum streak;
- nenhuma urgência artificial;
- nenhuma notificação;
- nenhuma recompensa por apenas abrir o app;
- nenhuma perda ou punição ao fechar;
- nenhuma alteração para leitores existentes;
- nenhuma coleta de conteúdo literário ou pessoal.

## Rollout

1. Mesclar com `FF_ONBOARDING_VALUE=false`.
2. Confirmar deploy e fluxo antigo.
3. Ativar `FF_PRODUCT_ANALYTICS=true` somente conforme o rollout já aprovado.
4. Ativar `FF_ONBOARDING_VALUE=true`.
5. Testar conta vazia em mobile e desktop.
6. Confirmar que CTA abre e focaliza a busca.
7. Criar primeira leitura como `Lendo`.
8. Confirmar remoção do bloco inicial e continuidade pelo checklist.
9. Confirmar que usuários com leituras não veem a experiência.
10. Acompanhar ativação e D1 antes de ampliar exposição.

## Rollback

Definir:

```text
FF_ONBOARDING_VALUE=false
```

O frontend volta imediatamente ao checklist existente. Não há migration, backfill ou remoção de dados.

## Testes

- [x] flag pública desligada por padrão;
- [x] fallback para checklist anterior;
- [x] exibição somente antes da primeira leitura;
- [x] CTA reutiliza busca existente;
- [x] alternativa reutiliza cadastro manual;
- [x] PT/EN/ES;
- [x] claro/escuro, mobile e reduced motion;
- [x] origem `onboarding` aceita pela allowlist de analytics;
- [x] marca removida após criação da leitura;
- [x] ausência de título, autor, ISBN e consulta nos eventos.

## Critério de saída

Com a flag desligada, não existe mudança visual. Com a flag ligada e uma estante vazia, a primeira ação é clara e leva ao fluxo existente de criação de leitura; depois do primeiro livro, a experiência desaparece e o ritual de progresso assume.
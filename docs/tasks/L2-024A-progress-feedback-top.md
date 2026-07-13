# L2-024A — Feedback de progresso no topo

Issue: #326 · Follow-up de #307

## Motivo

No uso real em celular, o retorno pós-`Li mais` aparecia junto à navegação inferior e visualmente se confundia com um bloco da própria página.

## Ajuste

Com `FF_PROGRESS_FEEDBACK=true`, o módulo `static/progress-feedback-top.js` aplica:

- posição fixa no topo da viewport;
- margem de 12 px no desktop e 10 px no mobile;
- respeito a `env(safe-area-inset-top)`;
- entrada curta de cima para baixo;
- ausência de deslocamento com `prefers-reduced-motion`.

Conteúdo, duração, botão “Ver diário”, fechamento manual, auto-close, analytics e vibração permanecem iguais.

O override usa `!important` porque os estilos-base do componente são injetados apenas quando o primeiro feedback é exibido e podem entrar no DOM depois do módulo de posição.

## Rollback

Definir:

```text
FF_PROGRESS_FEEDBACK=false
```

A flag já existente continua sendo o único controle da experiência.

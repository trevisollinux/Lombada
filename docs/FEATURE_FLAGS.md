# Feature flags do Lombada

As feature flags permitem publicar código novo desligado e ativá-lo de forma gradual sem nova migration, novo commit ou perda de dados.

## Princípios

- Toda flag nova nasce **desligada por padrão**.
- Valores ausentes ou inválidos são tratados como `false`.
- Flags não substituem autorização, validação ou controle de acesso.
- O endpoint público expõe somente nomes allowlisted e booleanos.
- Variáveis internas nunca são enviadas ao navegador.
- Desligar uma flag deve ocultar o comportamento novo sem apagar dados já criados.

## Valores aceitos

Ligado:

- `1`
- `true`
- `yes`
- `on`
- `enabled`

Desligado:

- `0`
- `false`
- `no`
- `off`
- `disabled`
- vazio ou variável ausente

A leitura ignora maiúsculas/minúsculas e espaços laterais. Qualquer outro valor usa o default seguro da flag.

## Registro inicial

| Flag pública | Variável no Railway | Default |
|---|---|---|
| `home_ritual` | `FF_HOME_RITUAL` | `false` |
| `product_analytics` | `FF_PRODUCT_ANALYTICS` | `false` |
| `progress_sessions` | `FF_PROGRESS_SESSIONS` | `false` |
| `favorite_books` | `FF_FAVORITE_BOOKS` | `false` |
| `period_recaps` | `FF_PERIOD_RECAPS` | `false` |
| `literary_reactions` | `FF_LITERARY_REACTIONS` | `false` |
| `progress_comments` | `FF_PROGRESS_COMMENTS` | `false` |
| `weekly_rhythm` | `FF_WEEKLY_RHYTHM` | `false` |
| `editorial_achievements` | `FF_EDITORIAL_ACHIEVEMENTS` | `false` |
| `reading_twin` | `FF_READING_TWIN` | `false` |
| `push_notifications` | `FF_PUSH_NOTIFICATIONS` | `false` |

Flag interna:

| Flag interna | Variável no Railway | Exposta ao navegador |
|---|---|---|
| `admin_retention_dashboard` | `FF_ADMIN_RETENTION_DASHBOARD` | não |

## Backend

```python
from feature_flags import feature_enabled

if feature_enabled("home_ritual"):
    # comportamento novo
    ...
```

Nomes desconhecidos levantam `KeyError`, evitando que um erro de digitação ative ou desative comportamento silenciosamente.

O snapshot público está disponível em:

```text
GET /api/features
```

Formato:

```json
{
  "version": 1,
  "features": {
    "home_ritual": false
  }
}
```

A resposta usa `Cache-Control: no-store`.

## Frontend

O helper está em `/static/feature-flags.js`. Ele não é carregado pela interface atual porque nenhuma experiência nova foi ativada ainda.

A primeira funcionalidade gated deve carregar o helper antes do seu código:

```html
<script src="/static/feature-flags.js?v={{APP_VERSION}}"></script>
```

Uso:

```javascript
await window.LombadaFeatures.ready;

if (window.LombadaFeatures.isEnabled('home_ritual')) {
  // renderizar experiência nova
}
```

Em falha de rede, resposta inválida ou erro HTTP, todas as flags permanecem `false`. O carregamento principal do aplicativo não depende desse request.

## Ativação no Railway

1. Confirmar que o PR da funcionalidade foi mesclado e o deploy está saudável.
2. Manter a flag ausente ou `false` durante o smoke inicial.
3. Abrir o serviço do Lombada no Railway.
4. Acessar **Variables**.
5. Criar ou editar a variável da flag, por exemplo:

```text
FF_HOME_RITUAL=true
```

6. Aplicar a alteração e aguardar o redeploy/restart.
7. Verificar `/healthz`, `/readyz`, `/api/version` e `/api/features`.
8. Executar o bloco relevante de `docs/SMOKE_TESTS.md`.
9. Observar erros e métricas definidos no PR da funcionalidade.

## Desativação e rollback

Mitigação preferida:

1. alterar a variável para `false`;
2. aguardar restart/deploy;
3. confirmar que o fluxo anterior reapareceu;
4. verificar que dados já gravados continuam íntegros;
5. corrigir em nova branch.

Caso o próprio mecanismo de flags apresente problema, reverter o PR. Esta fundação não possui migration.

## Inclusão de uma nova flag

Uma nova flag só pode ser adicionada quando:

- existe uma funcionalidade concreta associada;
- o nome descreve uma capacidade, não uma implementação temporária;
- há owner e plano de remoção;
- o PR define default, exposição pública/interna, rollout e rollback;
- existem testes de estado ligado e desligado;
- a documentação desta página foi atualizada.

Flags antigas devem ser removidas depois que o rollout estiver estável e o caminho anterior não for mais necessário. Evite flags permanentes sem propósito operacional claro.

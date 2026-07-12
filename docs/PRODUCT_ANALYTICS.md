# Eventos de produto do Lombada

Esta camada existe para medir ativação e uso real do produto sem transformar conteúdo literário ou dados pessoais em telemetria.

## Estado inicial

A coleta fica desligada enquanto `FF_PRODUCT_ANALYTICS` estiver ausente ou `false`.

Mesmo com o código publicado:

- o HTML atual não carrega `/static/product-analytics.js`;
- nenhum evento é disparado automaticamente;
- `POST /api/events` valida o lote, mas não persiste quando a flag está desligada;
- nenhuma mudança visual ou de navegação é aplicada.

## Eventos permitidos

- `app_opened`
- `search_submitted`
- `book_opened`
- `reading_created`
- `reading_updated`
- `progress_logged`
- `share_started`
- `profile_connected`

Cada evento possui uma lista própria de propriedades permitidas e valores enumerados em `product_analytics.py`.

## Dados que não podem ser coletados

O contrato não aceita:

- título ou autor;
- ISBN, ID de obra ou ID de edição;
- consulta de busca;
- crítica, nota de diário ou comentário;
- bio, nome, handle ou email;
- URL visitada completa;
- endereço IP armazenado;
- texto livre de qualquer tipo.

O IP e o User-Agent são usados somente em memória para gerar uma chave hash temporária de rate limit. O valor bruto e o hash não são persistidos.

## Identidade

Quando a sessão já possui um usuário válido:

- `user_id` referencia a conta anônima ou conectada já existente;
- `actor_type` recebe `anonymous` ou `connected`;
- email, handle e Google sub não entram na tabela;
- usuários demo são ignorados.

Quando não existe usuário na sessão, o evento pode ser armazenado com `user_id = NULL` e `actor_type = anonymous`. O endpoint não cria uma conta somente para analytics.

## Modelo

`ProductEvent` contém apenas:

- ID interno;
- `client_event_id` idempotente;
- nome do evento;
- `user_id` opcional;
- tipo de ator;
- JSON de propriedades allowlisted;
- versão do schema;
- timestamp do servidor.

A tabela é aditiva e criada por `SQLModel.metadata.create_all` após `analytics_models.py` ser importado pelo entrypoint.

## Endpoint

```text
POST /api/events
```

Exemplo válido:

```json
{
  "events": [
    {
      "event": "progress_logged",
      "client_event_id": "6bb63bb6-92d1-4ad3-9654-e792a753b9d8",
      "properties": {
        "source": "diary",
        "progress_type": "page",
        "public": false
      }
    }
  ]
}
```

Limites:

- até 10 eventos por lote;
- até 6 propriedades por evento;
- 60 eventos por minuto por sessão/IP por padrão;
- `ANALYTICS_RATE_LIMIT_PER_MINUTE` permite ajuste entre 1 e 600.

Respostas de sucesso usam HTTP 202 e `Cache-Control: no-store`.

Quando a flag está desligada:

```json
{
  "accepted": 0,
  "dropped": 1,
  "disabled": true
}
```

Indisponibilidade da tabela ou do banco resulta em descarte com HTTP 202. Analytics nunca deve quebrar a ação principal do usuário.

## Cliente frontend

`/static/product-analytics.js` mantém uma fila em memória e envia lotes de até 10 eventos usando `fetch` com `keepalive`.

O arquivo:

- só aceita nomes de evento conhecidos;
- remove propriedades não allowlisted;
- depende de `LombadaFeatures.isEnabled('product_analytics')`;
- não faz retry infinito;
- nunca lança erro para o fluxo chamador;
- ainda não é incluído em `index.html`.

Uma funcionalidade futura deverá carregar os arquivos nesta ordem:

```html
<script src="/static/feature-flags.js?v={{APP_VERSION}}"></script>
<script src="/static/product-analytics.js?v={{APP_VERSION}}"></script>
```

E disparar eventos somente após ações reais:

```javascript
LombadaAnalytics.track('progress_logged', {
  source: 'diary',
  progress_type: 'page',
  public: false
});
```

## Retenção

A retenção inicial é de **90 dias**.

Dry-run:

```bash
python scripts/purge_product_events.py --days 90
```

Aplicação em lote:

```bash
python scripts/purge_product_events.py --days 90 --limit 5000 --apply
```

O script não imprime URL de banco, propriedades ou IDs de usuário. Pode ser repetido até retornar `matched=0`.

Antes de automatizar a limpeza, executar manualmente em ambiente seguro e registrar as contagens esperadas.

## Ativação gradual

1. Mesclar e validar o deploy com `FF_PRODUCT_ANALYTICS=false`.
2. Confirmar que `/api/features` mostra `product_analytics: false`.
3. Instrumentar uma única ação em PR separado.
4. Testar o evento com a flag ligada somente em ambiente seguro.
5. Revisar a tabela procurando chaves ou valores não previstos.
6. Ativar em produção.
7. Observar 422, 429 e descartes por storage.
8. Adicionar novos eventos somente com atualização da allowlist, testes e documentação.

## Rollback

1. Definir `FF_PRODUCT_ANALYTICS=false` no Railway.
2. Confirmar que o endpoint deixa de persistir.
3. Remover a inclusão dos scripts ou reverter o PR de instrumentação, se necessário.
4. Manter a tabela aditiva até uma limpeza deliberada futura.

Desligar a flag não apaga eventos já armazenados; a retenção continua sendo aplicada pelo script.

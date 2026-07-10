#!/usr/bin/env bash
set -euo pipefail

: "${RAILWAY_TOKEN:?RAILWAY_TOKEN não está definido no ambiente do HCP Terraform}"
: "${RAILWAY_SERVICE_ID:?RAILWAY_SERVICE_ID não foi informado}"

payload="$(cat <<JSON
{"query":"mutation ResetRailwayBuild(\$serviceId: String!, \$input: ServiceInstanceUpdateInput!) { serviceInstanceUpdate(environmentId: null, serviceId: \$serviceId, input: \$input) }","variables":{"serviceId":"${RAILWAY_SERVICE_ID}","input":{"railwayConfigFile":null,"builder":"RAILPACK","buildCommand":null,"dockerfilePath":null,"startCommand":"uvicorn main:app --host 0.0.0.0 --port \$PORT"}}}
JSON
)"

response="$(curl --silent --show-error --fail \
  --request POST \
  --url "https://backboard.railway.app/graphql/v2?source=lombada_terraform_recovery" \
  --header "Authorization: Bearer ${RAILWAY_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "${payload}")"

if ! printf '%s' "${response}" | grep -Eq '"serviceInstanceUpdate"[[:space:]]*:[[:space:]]*true'; then
  echo "A API do Railway não confirmou a limpeza da configuração." >&2
  printf '%s\n' "${response}" >&2
  exit 1
fi

echo "Configuração de build do Railway limpa e redefinida para Railpack."

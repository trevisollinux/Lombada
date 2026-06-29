#!/usr/bin/env python3
"""Troca authorization code do Mercado Livre por tokens OAuth.

Configuração por variáveis de ambiente:
- MELI_APP_ID: client_id da aplicação Mercado Livre.
- MELI_CLIENT_SECRET: client_secret da aplicação Mercado Livre.
- MELI_REDIRECT_URI: redirect_uri cadastrada na aplicação.
- MELI_AUTH_CODE: authorization code recebido no fluxo OAuth.

O script imprime os campos retornados pela API para uso operacional e não
persiste tokens em disco ou no repositório.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import requests

MELI_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
REQUEST_TIMEOUT_SECONDS = 20

REQUIRED_ENV_VARS = (
    "MELI_APP_ID",
    "MELI_CLIENT_SECRET",
    "MELI_REDIRECT_URI",
    "MELI_AUTH_CODE",
)


def getenv_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Variável de ambiente obrigatória não configurada: {name}")
    return value


def exchange_code() -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "client_id": getenv_required("MELI_APP_ID"),
        "client_secret": getenv_required("MELI_CLIENT_SECRET"),
        "code": getenv_required("MELI_AUTH_CODE"),
        "redirect_uri": getenv_required("MELI_REDIRECT_URI"),
    }
    response = requests.post(MELI_TOKEN_URL, data=data, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def main() -> int:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError("Variáveis de ambiente obrigatórias não configuradas: " + ", ".join(missing))

    payload = exchange_code()
    for key in ("access_token", "refresh_token", "expires_in", "user_id"):
        print(f"{key}: {payload.get(key, '')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        response_text = exc.response.text if exc.response is not None else ""
        print(f"Erro HTTP ao trocar authorization code no Mercado Livre: {exc}", file=sys.stderr)
        if response_text:
            print(response_text, file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"Erro ao trocar authorization code no Mercado Livre: {exc}", file=sys.stderr)
        raise SystemExit(1)

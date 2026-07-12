"""Feature flags do Lombada 2.0.

As flags são lidas de variáveis de ambiente e ficam desligadas por padrão.
O registro central separa explicitamente flags públicas (seguras para o browser)
de flags internas, que nunca aparecem no endpoint público.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from fastapi import APIRouter
from fastapi.responses import JSONResponse


_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "enabled"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "disabled", ""})


@dataclass(frozen=True, slots=True)
class FeatureFlag:
    name: str
    env_var: str
    public: bool = True
    default: bool = False


_FLAG_SPECS = (
    FeatureFlag("home_ritual", "FF_HOME_RITUAL"),
    FeatureFlag("product_analytics", "FF_PRODUCT_ANALYTICS"),
    FeatureFlag("progress_sessions", "FF_PROGRESS_SESSIONS"),
    FeatureFlag("onboarding_value", "FF_ONBOARDING_VALUE"),
    FeatureFlag("favorite_books", "FF_FAVORITE_BOOKS"),
    FeatureFlag("period_recaps", "FF_PERIOD_RECAPS"),
    FeatureFlag("literary_reactions", "FF_LITERARY_REACTIONS"),
    FeatureFlag("progress_comments", "FF_PROGRESS_COMMENTS"),
    FeatureFlag("weekly_rhythm", "FF_WEEKLY_RHYTHM"),
    FeatureFlag("editorial_achievements", "FF_EDITORIAL_ACHIEVEMENTS"),
    FeatureFlag("reading_twin", "FF_READING_TWIN"),
    FeatureFlag("push_notifications", "FF_PUSH_NOTIFICATIONS"),
    # Controle operacional interno. Nunca deve ser enviado ao navegador.
    FeatureFlag("admin_retention_dashboard", "FF_ADMIN_RETENTION_DASHBOARD", public=False),
)

FEATURE_FLAGS = {spec.name: spec for spec in _FLAG_SPECS}
PUBLIC_FEATURE_NAMES = tuple(spec.name for spec in _FLAG_SPECS if spec.public)
INTERNAL_FEATURE_NAMES = tuple(spec.name for spec in _FLAG_SPECS if not spec.public)


def parse_flag_value(value: object, *, default: bool = False) -> bool:
    """Converte valores comuns de ambiente; valor inválido usa o default seguro."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def feature_enabled(name: str, env: Mapping[str, str] | None = None) -> bool:
    """Retorna o estado de uma flag registrada.

    Nomes desconhecidos levantam ``KeyError`` para que erros de digitação no
    backend sejam encontrados cedo. Valores inválidos continuam seguros porque
    são tratados como o default da flag — atualmente, sempre ``False``.
    """
    try:
        spec = FEATURE_FLAGS[name]
    except KeyError as exc:
        raise KeyError(f"feature flag desconhecida: {name}") from exc

    source = os.environ if env is None else env
    return parse_flag_value(source.get(spec.env_var), default=spec.default)


def public_feature_flags(env: Mapping[str, str] | None = None) -> dict[str, bool]:
    """Snapshot allowlisted que pode ser enviado ao frontend."""
    return {name: feature_enabled(name, env) for name in PUBLIC_FEATURE_NAMES}


def all_feature_flags(env: Mapping[str, str] | None = None) -> dict[str, bool]:
    """Snapshot completo para uso interno no backend/admin."""
    return {name: feature_enabled(name, env) for name in FEATURE_FLAGS}


router = APIRouter()


@router.get("/api/features", include_in_schema=False)
def api_public_features():
    return JSONResponse(
        {"version": 1, "features": public_feature_flags()},
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )

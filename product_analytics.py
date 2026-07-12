"""Ingestão mínima e privada de eventos de produto.

O endpoint é protegido pela flag ``product_analytics``. Mesmo habilitado, aceita
somente eventos e propriedades enumerados; texto livre, identificadores de livros
e dados pessoais não fazem parte do contrato.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from analytics_models import ProductEvent
from feature_flags import feature_enabled
from models import Usuario, get_session


logger = logging.getLogger(__name__)
router = APIRouter()

MAX_BATCH_SIZE = 10
MAX_PROPERTIES = 6
CLIENT_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")

_BOOL = object()

EVENT_PROPERTY_SCHEMAS: dict[str, dict[str, object]] = {
    "app_opened": {
        "source": frozenset({"web", "pwa", "twa", "unknown"}),
        "locale": frozenset({"pt-BR", "en", "es"}),
        "standalone": _BOOL,
    },
    "search_submitted": {
        "source": frozenset({"home", "explore", "onboarding", "unknown"}),
        "has_filters": _BOOL,
        "result_state": frozenset({"submitted", "empty", "error"}),
    },
    "book_opened": {
        "source": frozenset({"search", "explore", "shelf", "profile", "onboarding", "unknown"}),
        "has_cover": _BOOL,
    },
    "reading_created": {
        "source": frozenset({"search", "manual", "quick_action", "onboarding", "unknown"}),
        "status": frozenset({"Lido", "Lendo", "Quero ler", "custom"}),
        "has_rating": _BOOL,
        "public": _BOOL,
    },
    "reading_updated": {
        "source": frozenset({"detail", "quick_action", "unknown"}),
        "status": frozenset({"Lido", "Lendo", "Quero ler", "custom"}),
        "has_rating": _BOOL,
        "public": _BOOL,
    },
    "progress_logged": {
        "source": frozenset({"diary", "onboarding", "quick_action", "unknown"}),
        "progress_type": frozenset({"page", "percentage", "chapter", "free"}),
        "public": _BOOL,
    },
    "share_started": {
        "source": frozenset({"reading", "review", "diary", "shelf", "recap", "profile", "unknown"}),
        "share_type": frozenset({"native", "download", "copy_link"}),
        "success": _BOOL,
    },
    "profile_connected": {
        "provider": frozenset({"google"}),
        "source": frozenset({"profile", "onboarding", "unknown"}),
        "success": _BOOL,
    },
}

ALLOWED_EVENT_NAMES = frozenset(EVENT_PROPERTY_SCHEMAS)


class ProductEventInput(BaseModel):
    event: str
    properties: dict[str, object] = PydanticField(default_factory=dict)
    client_event_id: str | None = None


class ProductEventBatch(BaseModel):
    events: list[ProductEventInput]


def _accepted_response(payload: dict[str, object]) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=202,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def _normalize_client_event_id(value: str | None) -> str:
    candidate = (value or "").strip() or str(uuid4())
    if not CLIENT_EVENT_ID_RE.fullmatch(candidate):
        raise HTTPException(422, "client_event_id inválido")
    return candidate


def validate_product_event(item: ProductEventInput) -> tuple[str, dict[str, object], str]:
    event_name = (item.event or "").strip()
    schema = EVENT_PROPERTY_SCHEMAS.get(event_name)
    if schema is None:
        raise HTTPException(422, "evento não permitido")

    properties = item.properties or {}
    if len(properties) > MAX_PROPERTIES:
        raise HTTPException(422, "propriedades demais")

    normalized: dict[str, object] = {}
    for key, value in properties.items():
        rule = schema.get(key)
        if rule is None:
            raise HTTPException(422, f"propriedade não permitida: {key}")
        if rule is _BOOL:
            if type(value) is not bool:
                raise HTTPException(422, f"propriedade booleana inválida: {key}")
            normalized[key] = value
            continue
        if not isinstance(value, str) or value not in rule:
            raise HTTPException(422, f"valor não permitido: {key}")
        normalized[key] = value

    return event_name, normalized, _normalize_client_event_id(item.client_event_id)


def _rate_limit_per_minute() -> int:
    try:
        return min(600, max(1, int(os.getenv("ANALYTICS_RATE_LIMIT_PER_MINUTE", "60"))))
    except ValueError:
        return 60


_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: dict[str, deque[float]] = {}


def _request_actor_key(request: Request) -> str:
    uid = request.session.get("uid")
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    client_host = request.client.host if request.client else ""
    user_agent = (request.headers.get("user-agent") or "")[:160]
    raw = f"{uid or 'none'}|{forwarded or client_host}|{user_agent}"
    return hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:24]


def _consume_rate_limit(key: str, count: int) -> bool:
    now = time.monotonic()
    cutoff = now - 60.0
    limit = _rate_limit_per_minute()

    with _RATE_LOCK:
        bucket = _RATE_BUCKETS.setdefault(key, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) + count > limit:
            return False
        bucket.extend([now] * count)
        return True


def _event_retention_days() -> int:
    try:
        return min(365, max(1, int(os.getenv("PRODUCT_EVENT_RETENTION_DAYS", "90"))))
    except ValueError:
        return 90


def purge_product_events(
    session: Session,
    *,
    before: datetime,
    batch_size: int = 500,
    apply: bool = False,
) -> int:
    """Conta ou remove eventos anteriores ao corte, em lotes idempotentes."""
    total = 0
    while True:
        rows = session.exec(
            select(ProductEvent)
            .where(ProductEvent.created_at < before)
            .order_by(ProductEvent.id)
            .limit(max(1, min(batch_size, 5000)))
        ).all()
        if not rows:
            break
        total += len(rows)
        if not apply:
            break
        for row in rows:
            session.delete(row)
        session.commit()
    return total


@router.post("/api/events", include_in_schema=False)
def ingest_product_events(
    payload: ProductEventBatch,
    request: Request,
    session: Session = Depends(get_session),
):
    if not payload.events or len(payload.events) > MAX_BATCH_SIZE:
        raise HTTPException(422, "lote de eventos inválido")

    validated = [validate_product_event(item) for item in payload.events]
    if not feature_enabled("product_analytics"):
        return _accepted_response({"accepted": 0, "dropped": len(validated), "disabled": True})

    actor_key = _request_actor_key(request)
    if not _consume_rate_limit(actor_key, len(validated)):
        raise HTTPException(429, "limite de eventos excedido")

    uid = request.session.get("uid")
    user = session.get(Usuario, uid) if uid else None
    if user and user.is_demo:
        return _accepted_response({"accepted": 0, "dropped": len(validated), "ignored_demo": True})

    accepted = 0
    dropped = 0
    for event_name, properties, client_event_id in validated:
        event = ProductEvent(
            client_event_id=client_event_id,
            event_name=event_name,
            user_id=user.id if user else None,
            actor_type="connected" if user and user.google_sub else "anonymous",
            properties_json=json.dumps(properties, ensure_ascii=False, sort_keys=True),
        )
        session.add(event)
        try:
            session.commit()
            accepted += 1
        except IntegrityError:
            session.rollback()
            dropped += 1
        except SQLAlchemyError:
            session.rollback()
            logger.exception("falha ao persistir evento de produto")
            dropped += 1

    return _accepted_response({"accepted": accepted, "dropped": dropped})

"""Reações literárias em críticas públicas.

O módulo é aditivo e registrado pelo entrypoint antes do primeiro startup. Cada
leitor mantém no máximo uma reação por crítica; trocar o tipo atualiza a mesma
linha. O dono recebe apenas agrupamentos agregados, nunca uma notificação por
clique nem uma lista pública de pessoas que reagiram.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel, Session, select

from auth import usuario_sessao
from feature_flags import feature_enabled
from models import Edicao, Leitura, Obra, Usuario, get_session


REACTION_TYPES = ("want_to_read", "moved_me", "good_reading")
REACTION_TYPE_SET = frozenset(REACTION_TYPES)
MAX_BATCH_REVIEWS = 50
MAX_INBOX_GROUPS = 20


class LiteraryReaction(SQLModel, table=True):
    __tablename__ = "literary_reaction"
    __table_args__ = (
        UniqueConstraint("leitura_id", "usuario_id", name="uq_literary_reaction_pair"),
        CheckConstraint(
            "reaction_type IN ('want_to_read','moved_me','good_reading')",
            name="ck_literary_reaction_type",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    leitura_id: int = Field(foreign_key="leitura.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    reaction_type: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class LiteraryReactionInboxState(SQLModel, table=True):
    __tablename__ = "literary_reaction_inbox_state"
    __table_args__ = (
        UniqueConstraint("usuario_id", name="uq_literary_reaction_inbox_user"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    seen_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LiteraryReactionPayload(BaseModel):
    reaction_type: str


router = APIRouter()


def _require_enabled() -> None:
    if not feature_enabled("literary_reactions"):
        raise HTTPException(404, "recurso indisponível")


def _require_connected(user: Usuario) -> None:
    if not user.google_sub:
        raise HTTPException(401, "conecte sua conta Google para reagir")
    if user.is_demo:
        raise HTTPException(403, "perfis de demonstração não podem reagir")


def _normalize_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in REACTION_TYPE_SET:
        raise HTTPException(422, "reação inválida")
    return normalized


def _public_review(session: Session, leitura_id: int) -> tuple[Leitura, Usuario | None]:
    reading = session.get(Leitura, leitura_id)
    if not reading or not reading.publico or not (reading.relato or "").strip():
        # 404 evita revelar a existência de uma crítica privada.
        raise HTTPException(404, "crítica pública não encontrada")
    owner = session.get(Usuario, reading.usuario_id) if reading.usuario_id else None
    return reading, owner


def _review_can_receive_reactions(reading: Leitura, owner: Usuario | None) -> bool:
    return bool(
        reading.usuario_id
        and not reading.is_demo
        and owner
        and not owner.is_demo
    )


def _reaction_rows(session: Session, reading_ids: list[int]) -> list[LiteraryReaction]:
    if not reading_ids:
        return []
    return list(
        session.exec(
            select(LiteraryReaction).where(LiteraryReaction.leitura_id.in_(reading_ids))
        ).all()
    )


def reaction_summary(
    session: Session,
    reading: Leitura,
    viewer: Usuario,
    *,
    rows: list[LiteraryReaction] | None = None,
    owner: Usuario | None = None,
) -> dict:
    relevant = rows if rows is not None else _reaction_rows(session, [reading.id])
    relevant = [row for row in relevant if row.leitura_id == reading.id]
    counts = Counter(row.reaction_type for row in relevant if row.reaction_type in REACTION_TYPE_SET)
    mine = next((row.reaction_type for row in relevant if row.usuario_id == viewer.id), None)
    is_owner = reading.usuario_id == viewer.id
    connected = bool(viewer.google_sub and not viewer.is_demo)
    valid_target = _review_can_receive_reactions(reading, owner)
    return {
        "reading_id": reading.id,
        "counts": {reaction_type: counts[reaction_type] for reaction_type in REACTION_TYPES},
        "total": sum(counts.values()),
        "mine": mine,
        "is_owner": is_owner,
        "connected": connected,
        "can_react": bool(connected and valid_target and not is_owner),
    }


def batch_reaction_summaries(
    session: Session,
    viewer: Usuario,
    reading_ids: list[int],
) -> dict[str, dict]:
    unique_ids = list(dict.fromkeys(reading_ids))[:MAX_BATCH_REVIEWS]
    if not unique_ids:
        return {}
    readings = list(
        session.exec(
            select(Leitura)
            .where(Leitura.id.in_(unique_ids))
            .where(Leitura.publico == True)  # noqa: E712
        ).all()
    )
    readings = [reading for reading in readings if (reading.relato or "").strip()]
    rows = _reaction_rows(session, [reading.id for reading in readings])
    owner_ids = {reading.usuario_id for reading in readings if reading.usuario_id}
    owners = {
        owner.id: owner
        for owner in session.exec(select(Usuario).where(Usuario.id.in_(owner_ids))).all()
    } if owner_ids else {}
    return {
        str(reading.id): reaction_summary(
            session,
            reading,
            viewer,
            rows=rows,
            owner=owners.get(reading.usuario_id),
        )
        for reading in readings
    }


def set_literary_reaction(
    session: Session,
    user: Usuario,
    leitura_id: int,
    reaction_type: str,
) -> tuple[dict, str]:
    _require_connected(user)
    normalized = _normalize_type(reaction_type)
    reading, owner = _public_review(session, leitura_id)
    if not _review_can_receive_reactions(reading, owner):
        raise HTTPException(404, "crítica pública não encontrada")
    if reading.usuario_id == user.id:
        raise HTTPException(409, "você não pode reagir à própria crítica")

    existing = session.exec(
        select(LiteraryReaction).where(
            LiteraryReaction.leitura_id == leitura_id,
            LiteraryReaction.usuario_id == user.id,
        )
    ).first()
    action = "set"
    now = datetime.utcnow()
    if existing:
        action = "changed" if existing.reaction_type != normalized else "set"
        existing.reaction_type = normalized
        existing.updated_at = now
        session.add(existing)
    else:
        session.add(
            LiteraryReaction(
                leitura_id=leitura_id,
                usuario_id=user.id,
                reaction_type=normalized,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
    return reaction_summary(session, reading, user, owner=owner), action


def remove_literary_reaction(
    session: Session,
    user: Usuario,
    leitura_id: int,
) -> tuple[dict, bool]:
    _require_connected(user)
    reading, owner = _public_review(session, leitura_id)
    if reading.usuario_id == user.id:
        raise HTTPException(409, "você não pode reagir à própria crítica")
    existing = session.exec(
        select(LiteraryReaction).where(
            LiteraryReaction.leitura_id == leitura_id,
            LiteraryReaction.usuario_id == user.id,
        )
    ).first()
    removed = bool(existing)
    if existing:
        session.delete(existing)
        session.commit()
    return reaction_summary(session, reading, user, owner=owner), removed


def _reading_book_metadata(session: Session, reading_ids: set[int]) -> dict[int, dict]:
    if not reading_ids:
        return {}
    rows = session.exec(
        select(Leitura, Edicao, Obra)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .where(Leitura.id.in_(reading_ids))
    ).all()
    return {
        reading.id: {
            "title": work.titulo,
            "author": work.autor,
            "cover_url": edition.capa_url or "",
        }
        for reading, edition, work in rows
    }


def grouped_reaction_inbox(
    session: Session,
    owner: Usuario,
    *,
    limit: int = MAX_INBOX_GROUPS,
) -> dict:
    state = session.exec(
        select(LiteraryReactionInboxState).where(
            LiteraryReactionInboxState.usuario_id == owner.id
        )
    ).first()
    seen_at = state.seen_at if state else datetime.min
    rows = session.exec(
        select(LiteraryReaction, Leitura)
        .join(Leitura, LiteraryReaction.leitura_id == Leitura.id)
        .where(Leitura.usuario_id == owner.id)
        .where(Leitura.publico == True)  # noqa: E712
        .order_by(LiteraryReaction.updated_at.desc())
    ).all()
    rows = [
        (reaction, reading)
        for reaction, reading in rows
        if (reading.relato or "").strip()
    ]

    grouped: dict[int, dict] = {}
    for reaction, reading in rows:
        group = grouped.setdefault(
            reading.id,
            {
                "reading_id": reading.id,
                "counts": {reaction_type: 0 for reaction_type in REACTION_TYPES},
                "total": 0,
                "last_at": reaction.updated_at,
                "unread": False,
            },
        )
        if reaction.reaction_type in REACTION_TYPE_SET:
            group["counts"][reaction.reaction_type] += 1
            group["total"] += 1
        if reaction.updated_at > group["last_at"]:
            group["last_at"] = reaction.updated_at
        if reaction.updated_at > seen_at:
            group["unread"] = True

    ordered = sorted(
        grouped.values(),
        key=lambda group: group["last_at"],
        reverse=True,
    )[: max(1, min(limit, MAX_INBOX_GROUPS))]
    metadata = _reading_book_metadata(session, {group["reading_id"] for group in ordered})
    unread_groups = 0
    for group in ordered:
        group.update(metadata.get(group["reading_id"], {"title": "", "author": "", "cover_url": ""}))
        group["last_at"] = group["last_at"].isoformat() + "Z"
        if group["unread"]:
            unread_groups += 1
    return {
        "groups": ordered,
        "unread_groups": unread_groups,
        "grouped": True,
        "individual_notifications": False,
    }


def mark_reaction_inbox_seen(session: Session, owner: Usuario) -> datetime:
    now = datetime.utcnow()
    state = session.exec(
        select(LiteraryReactionInboxState).where(
            LiteraryReactionInboxState.usuario_id == owner.id
        )
    ).first()
    if state:
        state.seen_at = now
        state.updated_at = now
        session.add(state)
    else:
        session.add(
            LiteraryReactionInboxState(
                usuario_id=owner.id,
                seen_at=now,
                updated_at=now,
            )
        )
    session.commit()
    return now


def _parse_ids(raw: str) -> list[int]:
    parsed: list[int] = []
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError as exc:
            raise HTTPException(422, "ids inválidos") from exc
        if value <= 0:
            raise HTTPException(422, "ids inválidos")
        parsed.append(value)
    if len(parsed) > MAX_BATCH_REVIEWS:
        raise HTTPException(422, f"consulte no máximo {MAX_BATCH_REVIEWS} críticas")
    return list(dict.fromkeys(parsed))


@router.get("/api/reviews/reactions", include_in_schema=False)
def get_batch_reactions(
    request: Request,
    ids: str = Query(default=""),
    session: Session = Depends(get_session),
):
    _require_enabled()
    viewer = usuario_sessao(request, session)
    return {"reviews": batch_reaction_summaries(session, viewer, _parse_ids(ids))}


@router.get("/api/reviews/{leitura_id}/reactions", include_in_schema=False)
def get_review_reactions(
    leitura_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    _require_enabled()
    viewer = usuario_sessao(request, session)
    reading, owner = _public_review(session, leitura_id)
    return reaction_summary(session, reading, viewer, owner=owner)


@router.put("/api/reviews/{leitura_id}/reaction", include_in_schema=False)
def put_review_reaction(
    leitura_id: int,
    payload: LiteraryReactionPayload,
    request: Request,
    session: Session = Depends(get_session),
):
    _require_enabled()
    user = usuario_sessao(request, session)
    summary, action = set_literary_reaction(
        session,
        user,
        leitura_id,
        payload.reaction_type,
    )
    return {**summary, "action": action}


@router.delete("/api/reviews/{leitura_id}/reaction", include_in_schema=False)
def delete_review_reaction(
    leitura_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    _require_enabled()
    user = usuario_sessao(request, session)
    summary, removed = remove_literary_reaction(session, user, leitura_id)
    return {**summary, "action": "removed", "removed": removed}


@router.get("/api/eu/reacoes-literarias", include_in_schema=False)
def get_my_reaction_inbox(
    request: Request,
    limit: int = Query(default=MAX_INBOX_GROUPS, ge=1, le=MAX_INBOX_GROUPS),
    session: Session = Depends(get_session),
):
    _require_enabled()
    owner = usuario_sessao(request, session)
    _require_connected(owner)
    return grouped_reaction_inbox(session, owner, limit=limit)


@router.post("/api/eu/reacoes-literarias/vistas", include_in_schema=False)
def mark_my_reaction_inbox_seen(
    request: Request,
    session: Session = Depends(get_session),
):
    _require_enabled()
    owner = usuario_sessao(request, session)
    _require_connected(owner)
    seen_at = mark_reaction_inbox_seen(session, owner)
    return {"seen": True, "seen_at": seen_at.isoformat() + "Z"}


def install_product_analytics_contract(product_analytics_module) -> None:
    product_analytics_module.EVENT_PROPERTY_SCHEMAS.setdefault(
        "literary_reaction",
        {
            "source": frozenset({"feed", "work", "profile"}),
            "action": frozenset({"set", "changed", "removed", "viewed"}),
            "reaction_type": frozenset((*REACTION_TYPES, "none")),
        },
    )
    product_analytics_module.ALLOWED_EVENT_NAMES = frozenset(
        product_analytics_module.EVENT_PROPERTY_SCHEMAS
    )

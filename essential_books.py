"""Quatro essenciais: identidade literária escolhida pelo próprio leitor.

O módulo é aditivo, protegido pela flag pública ``favorite_books`` e instalado
pelo entrypoint antes do lifespan criar as tabelas. A seleção é limitada a obras
já presentes na estante do usuário.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Field, SQLModel, Session, select

from auth import usuario_sessao
from feature_flags import feature_enabled
from models import Edicao, Leitura, Obra, Usuario, get_session


class UserEssentialBook(SQLModel, table=True):
    __tablename__ = "user_essential_book"
    __table_args__ = (
        UniqueConstraint("usuario_id", "position", name="uq_essential_user_position"),
        UniqueConstraint("usuario_id", "obra_id", name="uq_essential_user_work"),
        CheckConstraint("position >= 1 AND position <= 4", name="ck_essential_position"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    obra_id: int = Field(foreign_key="obra.id", index=True)
    edicao_id: Optional[int] = Field(default=None, foreign_key="edicao.id", index=True)
    position: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EssentialBooksPayload(BaseModel):
    work_keys: list[str] = PydanticField(default_factory=list, max_length=4)


router = APIRouter()


def _require_enabled() -> None:
    if not feature_enabled("favorite_books"):
        raise HTTPException(404, "recurso indisponível")


def _book_payload(obra: Obra, edicao: Edicao | None, position: int) -> dict:
    return {
        "position": position,
        "work_key": obra.ol_work_key,
        "title": obra.titulo,
        "author": obra.autor,
        "cover_url": edicao.capa_url if edicao else "",
        "edition_id": edicao.id if edicao else None,
    }


def essential_books_for_user(session: Session, user_id: int) -> list[dict]:
    rows = session.exec(
        select(UserEssentialBook)
        .where(UserEssentialBook.usuario_id == user_id)
        .order_by(UserEssentialBook.position)
    ).all()
    books: list[dict] = []
    for row in rows:
        obra = session.get(Obra, row.obra_id)
        if not obra:
            continue
        edicao = session.get(Edicao, row.edicao_id) if row.edicao_id else None
        if not edicao:
            edicao = session.exec(
                select(Edicao)
                .where(Edicao.obra_id == obra.id)
                .order_by(Edicao.capa_url.desc(), Edicao.id)
            ).first()
        books.append(_book_payload(obra, edicao, row.position))
    return books


def _normalize_work_keys(values: list[str]) -> list[str]:
    normalized = [str(value or "").strip() for value in values]
    if any(not value for value in normalized):
        raise HTTPException(422, "obra inválida")
    if len(normalized) > 4:
        raise HTTPException(422, "escolha no máximo quatro obras")
    if len(set(normalized)) != len(normalized):
        raise HTTPException(422, "não repita a mesma obra")
    return normalized


def replace_essential_books(
    session: Session,
    user: Usuario,
    work_keys: list[str],
) -> list[dict]:
    normalized = _normalize_work_keys(work_keys)
    if not user.google_sub:
        raise HTTPException(403, "conecte sua conta Google para salvar seus essenciais")

    chosen: dict[str, tuple[Obra, Edicao]] = {}
    if normalized:
        rows = session.exec(
            select(Leitura, Edicao, Obra)
            .join(Edicao, Leitura.edicao_id == Edicao.id)
            .join(Obra, Edicao.obra_id == Obra.id)
            .where(Leitura.usuario_id == user.id)
            .where(Obra.ol_work_key.in_(normalized))
            .order_by(Leitura.criado_em.desc())
        ).all()
        for _, edicao, obra in rows:
            chosen.setdefault(obra.ol_work_key, (obra, edicao))

        missing = [key for key in normalized if key not in chosen]
        if missing:
            raise HTTPException(422, "escolha somente obras da sua estante")

    current = session.exec(
        select(UserEssentialBook).where(UserEssentialBook.usuario_id == user.id)
    ).all()
    for row in current:
        session.delete(row)

    now = datetime.utcnow()
    for position, work_key in enumerate(normalized, start=1):
        obra, edicao = chosen[work_key]
        session.add(
            UserEssentialBook(
                usuario_id=user.id,
                obra_id=obra.id,
                edicao_id=edicao.id,
                position=position,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
    return essential_books_for_user(session, user.id)


@router.get("/api/eu/essenciais", include_in_schema=False)
def get_my_essential_books(
    request: Request,
    session: Session = Depends(get_session),
):
    _require_enabled()
    user = usuario_sessao(request, session)
    return {
        "books": essential_books_for_user(session, user.id),
        "can_edit": bool(user.google_sub),
        "limit": 4,
    }


@router.put("/api/eu/essenciais", include_in_schema=False)
def put_my_essential_books(
    payload: EssentialBooksPayload,
    request: Request,
    session: Session = Depends(get_session),
):
    _require_enabled()
    user = usuario_sessao(request, session)
    books = replace_essential_books(session, user, payload.work_keys)
    return {"books": books, "saved": True, "limit": 4}


@router.get("/api/u/{handle}/essenciais", include_in_schema=False)
def get_public_essential_books(
    handle: str,
    session: Session = Depends(get_session),
):
    _require_enabled()
    user = session.exec(
        select(Usuario).where(Usuario.handle == handle.lower().strip())
    ).first()
    if not user:
        raise HTTPException(404, "perfil não encontrado")
    return {"handle": user.handle, "books": essential_books_for_user(session, user.id)}


def _public_book_card(book: dict, position: int) -> str:
    title = str(book.get("title") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    author = str(book.get("author") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    cover = str(book.get("cover_url") or "").replace("&", "&amp;").replace('"', "&quot;")
    params = urlencode({"obra": book.get("work_key") or "", "t": book.get("title") or "", "a": book.get("author") or ""})
    cover_html = (
        f'<div class="cover"><img src="{cover}" alt="" loading="lazy" '
        'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
        f'<div class="fb" style="display:none">{title}</div><span class="essential-rank">{position}</span></div>'
        if cover
        else f'<div class="cover"><div class="fb">{title}</div><span class="essential-rank">{position}</span></div>'
    )
    return f'<a class="book essential-book" href="/?{params}" aria-label="Abrir obra {title}">{cover_html}<div class="t">{title}</div><div class="a">{author}</div></a>'


def inject_public_essentials(html: str, books: list[dict]) -> str:
    if not books:
        return html
    cards = "".join(_public_book_card(book, index) for index, book in enumerate(books, start=1))
    section = (
        '<section class="section essential-public"><div class="essential-public-head">'
        '<div><div class="label">identidade literária</div><h2>Quatro essenciais</h2></div>'
        f'<span>{len(books)}/4</span></div><div class="shelf-strip essentials">{cards}</div></section>'
    )
    css = (
        '.essential-public-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:14px}'
        '.essential-public-head h2{margin:3px 0 0}.essential-public-head>span{font:700 10px/1 "Space Mono",monospace;color:var(--gold)}'
        '.shelf-strip.essentials{grid-template-columns:repeat(2,1fr)}'
        '@media(min-width:420px){.shelf-strip.essentials{grid-template-columns:repeat(4,1fr)}}'
        '.essential-book .cover{outline:1px solid color-mix(in srgb,var(--gold),transparent 55%)}'
        '.essential-rank{position:absolute;right:6px;top:6px;display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:var(--paper);color:var(--gold);font:700 10px/1 "Space Mono",monospace;border:1px solid var(--gold)}'
    )
    html = html.replace("</style>", css + "</style>", 1)
    marker = '<section class="section"><h2>Lendo agora</h2>'
    if marker in html:
        return html.replace(marker, section + marker, 1)
    return html.replace('<a class="cta" href="/">', section + '<a class="cta" href="/">', 1)


def install_public_profile_patch(main_module) -> None:
    if getattr(main_module.app.state, "essential_public_profile_patch_installed", False):
        return
    original = main_module.render_estante_publica

    def render_with_essentials(user, readings, social=None, textos=None):
        html = original(user, readings, social, textos=textos)
        if not feature_enabled("favorite_books"):
            return html
        try:
            with Session(main_module.engine) as session:
                books = essential_books_for_user(session, user.id)
            return inject_public_essentials(html, books)
        except SQLAlchemyError:
            return html

    main_module.render_estante_publica = render_with_essentials
    main_module.app.state.essential_public_profile_patch_installed = True


def install_product_analytics_contract(product_analytics_module) -> None:
    product_analytics_module.EVENT_PROPERTY_SCHEMAS.setdefault(
        "essential_books",
        {
            "source": frozenset({"profile"}),
            "action": frozenset({"saved", "cleared", "shared"}),
            "completion": frozenset({"empty", "partial", "complete"}),
        },
    )
    product_analytics_module.ALLOWED_EVENT_NAMES = frozenset(
        product_analytics_module.EVENT_PROPERTY_SCHEMAS
    )

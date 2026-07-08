"""API pública somente leitura do catálogo do Lombada."""
import json
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import distinct, or_
from sqlmodel import Session, select, func

from models import Obra, Edicao, get_session

PUBLIC_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=86400"

router = APIRouter(prefix="/api/public/v1", tags=["public-api"])


def _cache(response: Response) -> None:
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL


def _clean(value: Optional[str]) -> str:
    return " ".join((value or "").strip().split())


def _like(value: str) -> str:
    return f"%{value.lower()}%"


def _genres(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except (TypeError, json.JSONDecodeError):
        pass
    return []


def _edition_payload(edicao: Edicao) -> dict:
    return {
        "id": edicao.id,
        "edition_key": edicao.ol_edition_key or "",
        "publisher": edicao.editora or "",
        "translator": edicao.tradutor or "",
        "isbn": edicao.isbn or "",
        "language": edicao.idioma or "",
        "year": edicao.ano,
        "cover_url": edicao.capa_url or "",
        "pages": edicao.paginas,
    }


def _book_payload(obra: Obra, edicoes: list[Edicao]) -> dict:
    return {
        "id": obra.id,
        "work_key": obra.ol_work_key or "",
        "title": obra.titulo or "",
        "author": obra.autor or "",
        "year": obra.ano,
        "original_language": obra.idioma_original or "",
        "description": obra.descricao or "",
        "genres": _genres(obra.generos_json or ""),
        "editions": [_edition_payload(edicao) for edicao in edicoes],
    }


def _book_summary(obra: Obra) -> dict:
    return {
        "id": obra.id,
        "work_key": obra.ol_work_key or "",
        "title": obra.titulo or "",
        "author": obra.autor or "",
        "year": obra.ano,
        "original_language": obra.idioma_original or "",
    }


def _filtered_books_query(
    q: str = "",
    title: str = "",
    author: str = "",
    publisher: str = "",
    translator: str = "",
    isbn: str = "",
    language: str = "",
    year: Optional[int] = None,
    has_cover: Optional[bool] = None,
):
    stmt = select(Obra.id).join(Edicao, isouter=True)
    filters = []
    if q:
        pattern = _like(q)
        filters.append(or_(
            func.lower(Obra.titulo).like(pattern),
            func.lower(Obra.autor).like(pattern),
            func.lower(Edicao.editora).like(pattern),
            func.lower(Edicao.tradutor).like(pattern),
            func.lower(Edicao.isbn).like(pattern),
        ))
    if title:
        filters.append(func.lower(Obra.titulo).like(_like(title)))
    if author:
        filters.append(func.lower(Obra.autor).like(_like(author)))
    if publisher:
        filters.append(func.lower(Edicao.editora).like(_like(publisher)))
    if translator:
        filters.append(func.lower(Edicao.tradutor).like(_like(translator)))
    if isbn:
        filters.append(func.lower(Edicao.isbn).like(_like(isbn)))
    if language:
        filters.append(func.lower(Edicao.idioma).like(_like(language)))
    if year is not None:
        filters.append(or_(Obra.ano == year, Edicao.ano == year))
    if has_cover is True:
        filters.append(Edicao.capa_url != "")
    elif has_cover is False:
        filters.append(or_(Edicao.capa_url == "", Edicao.capa_url.is_(None)))
    for item in filters:
        stmt = stmt.where(item)
    return stmt


@router.get("/health")
def public_health(response: Response):
    _cache(response)
    return {"ok": True, "service": "lombada-public-api", "version": "v1"}


@router.get("/books")
def list_books(
    response: Response,
    q: str = "",
    title: str = "",
    author: str = "",
    publisher: str = "",
    translator: str = "",
    isbn: str = "",
    language: str = "",
    year: Optional[int] = None,
    has_cover: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    s: Session = Depends(get_session),
):
    _cache(response)
    params = {k: _clean(v) for k, v in {"q": q, "title": title, "author": author, "publisher": publisher, "translator": translator, "isbn": isbn, "language": language}.items()}
    base = _filtered_books_query(**params, year=year, has_cover=has_cover)
    total = s.exec(select(func.count(distinct(Obra.id))).select_from(Obra).join(Edicao, isouter=True).where(*base._where_criteria)).one()
    ids = s.exec(base.distinct().order_by(Obra.titulo, Obra.autor).offset((page - 1) * limit).limit(limit)).all()
    obras = s.exec(select(Obra).where(Obra.id.in_(ids)).order_by(Obra.titulo, Obra.autor)).all() if ids else []
    edicoes = s.exec(select(Edicao).where(Edicao.obra_id.in_(ids)).order_by(Edicao.ano, Edicao.editora, Edicao.id)).all() if ids else []
    por_obra: dict[int, list[Edicao]] = {}
    for edicao in edicoes:
        por_obra.setdefault(edicao.obra_id, [])
        if len(por_obra[edicao.obra_id]) < 5:
            por_obra[edicao.obra_id].append(edicao)
    return {"data": [_book_payload(obra, por_obra.get(obra.id or 0, [])) for obra in obras], "pagination": {"page": page, "limit": limit, "total": total, "pages": math.ceil(total / limit) if total else 0}}


@router.get("/books/{book_id}")
def get_book(book_id: int, response: Response, s: Session = Depends(get_session)):
    _cache(response)
    obra = s.get(Obra, book_id)
    if not obra:
        raise HTTPException(404, "obra não encontrada")
    edicoes = s.exec(select(Edicao).where(Edicao.obra_id == book_id).order_by(Edicao.ano, Edicao.editora, Edicao.id)).all()
    return _book_payload(obra, edicoes)


@router.get("/editions/{edition_id}")
def get_edition(edition_id: int, response: Response, s: Session = Depends(get_session)):
    _cache(response)
    edicao = s.get(Edicao, edition_id)
    if not edicao:
        raise HTTPException(404, "edição não encontrada")
    obra = s.get(Obra, edicao.obra_id)
    payload = _edition_payload(edicao)
    payload["book"] = _book_summary(obra) if obra else None
    return payload


@router.get("/publishers")
def list_publishers(response: Response, q: str = "", page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=50), s: Session = Depends(get_session)):
    _cache(response)
    q = _clean(q)
    stmt = select(Edicao.editora, func.count(Edicao.id)).where(Edicao.editora != "").group_by(Edicao.editora)
    count_stmt = select(func.count(distinct(Edicao.editora))).where(Edicao.editora != "")
    if q:
        pattern = _like(q)
        stmt = stmt.where(func.lower(Edicao.editora).like(pattern))
        count_stmt = count_stmt.where(func.lower(Edicao.editora).like(pattern))
    total = s.exec(count_stmt).one()
    rows = s.exec(stmt.order_by(Edicao.editora).offset((page - 1) * limit).limit(limit)).all()
    return {"data": [{"name": name, "editions_count": count} for name, count in rows], "pagination": {"page": page, "limit": limit, "total": total, "pages": math.ceil(total / limit) if total else 0}}


@router.get("/literatures")
def list_literatures(response: Response, s: Session = Depends(get_session)):
    _cache(response)
    rows = s.exec(select(Obra.literatura_pais, Obra.literatura_regiao).where(or_(Obra.literatura_pais != "", Obra.literatura_regiao != "")).distinct().order_by(Obra.literatura_pais, Obra.literatura_regiao)).all()
    return {"data": [{"country": pais or "", "region": regiao or ""} for pais, regiao in rows]}

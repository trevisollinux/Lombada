"""Retrospectivas semanais e mensais a partir do diário de leitura.

O serviço é somente leitura, protegido pela flag ``period_recaps`` e não cria
snapshot persistido. Janelas são definidas em America/Sao_Paulo e convertidas
para UTC antes das consultas porque os timestamps atuais são armazenados como
``datetime`` UTC sem timezone.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from auth import usuario_sessao
from feature_flags import feature_enabled
from models import Edicao, Leitura, Obra, ReadingJournalEntry, get_session


SAO_PAULO = ZoneInfo("America/Sao_Paulo")
UTC = timezone.utc
ALLOWED_PERIODS = frozenset({"week", "month"})
MAX_OFFSET = 12


@dataclass(frozen=True, slots=True)
class PeriodWindow:
    period: Literal["week", "month"]
    offset: int
    start_local: datetime
    end_local: datetime
    start_utc: datetime
    end_utc: datetime
    is_current: bool

    @property
    def start_date(self) -> str:
        return self.start_local.date().isoformat()

    @property
    def end_date_inclusive(self) -> str:
        return (self.end_local.date() - timedelta(days=1)).isoformat()


def _aware_utc(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        return current.replace(tzinfo=UTC)
    return current.astimezone(UTC)


def _month_shift(year: int, month: int, delta: int) -> tuple[int, int]:
    zero_based = year * 12 + (month - 1) + delta
    return zero_based // 12, zero_based % 12 + 1


def period_window(
    period: str,
    offset: int = 0,
    *,
    now: datetime | None = None,
) -> PeriodWindow:
    normalized = str(period or "").strip().lower()
    if normalized not in ALLOWED_PERIODS:
        raise HTTPException(422, "período inválido")
    if offset < 0 or offset > MAX_OFFSET:
        raise HTTPException(422, f"offset deve estar entre 0 e {MAX_OFFSET}")

    local_now = _aware_utc(now).astimezone(SAO_PAULO)
    if normalized == "week":
        current_start_date = local_now.date() - timedelta(days=local_now.weekday())
        start_date = current_start_date - timedelta(weeks=offset)
        end_date = start_date + timedelta(days=7)
    else:
        current_start_date = local_now.date().replace(day=1)
        year, month = _month_shift(current_start_date.year, current_start_date.month, -offset)
        start_date = date(year, month, 1)
        end_year, end_month = _month_shift(year, month, 1)
        end_date = date(end_year, end_month, 1)

    start_local = datetime.combine(start_date, time.min, tzinfo=SAO_PAULO)
    end_local = datetime.combine(end_date, time.min, tzinfo=SAO_PAULO)
    # Banco atual usa UTC naive. A conversão é explícita para manter limites
    # inclusivo/exclusivo consistentes mesmo se regras de timezone mudarem.
    start_utc = start_local.astimezone(UTC).replace(tzinfo=None)
    end_utc = end_local.astimezone(UTC).replace(tzinfo=None)
    return PeriodWindow(
        period=normalized,  # type: ignore[arg-type]
        offset=offset,
        start_local=start_local,
        end_local=end_local,
        start_utc=start_utc,
        end_utc=end_utc,
        is_current=offset == 0,
    )


def _entry_local_date(entry: ReadingJournalEntry) -> str:
    timestamp = entry.created_at or datetime.utcnow()
    return timestamp.replace(tzinfo=UTC).astimezone(SAO_PAULO).date().isoformat()


def _entry_progress(entry: ReadingJournalEntry) -> dict:
    if entry.pagina is not None:
        return {"type": "page", "value": entry.pagina}
    if entry.porcentagem is not None:
        return {"type": "percentage", "value": entry.porcentagem}
    if (entry.capitulo or "").strip():
        return {"type": "chapter", "label": entry.capitulo.strip()[:160]}
    return {"type": "session"}


def _positive_page_delta(entry: ReadingJournalEntry, previous_page: int | None) -> tuple[int, bool]:
    if entry.paginas_delta is not None:
        return max(0, int(entry.paginas_delta)), True
    if entry.pagina is not None and previous_page is not None:
        return max(0, int(entry.pagina) - int(previous_page)), True
    return 0, False


def _previous_positions(
    session: Session,
    user_id: int,
    reading_ids: set[int],
    before: datetime,
) -> dict[int, dict[str, int | None]]:
    if not reading_ids:
        return {}
    rows = session.exec(
        select(ReadingJournalEntry)
        .where(ReadingJournalEntry.usuario_id == user_id)
        .where(ReadingJournalEntry.leitura_id.in_(reading_ids))
        .where(ReadingJournalEntry.created_at < before)
        .order_by(
            ReadingJournalEntry.leitura_id,
            ReadingJournalEntry.created_at,
            ReadingJournalEntry.id,
        )
    ).all()
    positions: dict[int, dict[str, int | None]] = defaultdict(
        lambda: {"page": None, "percentage": None}
    )
    for entry in rows:
        if entry.pagina is not None:
            positions[entry.leitura_id]["page"] = entry.pagina
        if entry.porcentagem is not None:
            positions[entry.leitura_id]["percentage"] = entry.porcentagem
    return dict(positions)


def _reading_metadata(session: Session, reading_ids: set[int]) -> dict[int, dict]:
    if not reading_ids:
        return {}
    rows = session.exec(
        select(Leitura, Edicao, Obra)
        .join(Edicao, Leitura.edicao_id == Edicao.id)
        .join(Obra, Edicao.obra_id == Obra.id)
        .where(Leitura.id.in_(reading_ids))
    ).all()
    return {
        leitura.id: {
            "reading_id": leitura.id,
            "work_key": obra.ol_work_key,
            "title": obra.titulo,
            "author": obra.autor,
            "cover_url": edicao.capa_url or "",
        }
        for leitura, edicao, obra in rows
    }


def build_period_recap(
    session: Session,
    user_id: int,
    window: PeriodWindow,
) -> dict:
    entries = session.exec(
        select(ReadingJournalEntry)
        .where(ReadingJournalEntry.usuario_id == user_id)
        .where(ReadingJournalEntry.created_at >= window.start_utc)
        .where(ReadingJournalEntry.created_at < window.end_utc)
        .order_by(
            ReadingJournalEntry.leitura_id,
            ReadingJournalEntry.created_at,
            ReadingJournalEntry.id,
        )
    ).all()

    reading_ids = {entry.leitura_id for entry in entries}
    previous = _previous_positions(session, user_id, reading_ids, window.start_utc)
    metadata = _reading_metadata(session, reading_ids)
    active_days: set[str] = set()
    type_counts: Counter[str] = Counter()
    pages_advanced = 0
    calculable_page_sessions = 0
    per_book: dict[int, dict] = {}

    for entry in entries:
        active_days.add(_entry_local_date(entry))
        progress = _entry_progress(entry)
        progress_type = str(progress["type"])
        type_counts[progress_type] += 1

        positions = previous.setdefault(
            entry.leitura_id,
            {"page": None, "percentage": None},
        )
        page_delta, calculable = _positive_page_delta(
            entry,
            positions.get("page"),  # type: ignore[arg-type]
        )
        if calculable:
            calculable_page_sessions += 1
            pages_advanced += page_delta
        if entry.pagina is not None:
            positions["page"] = entry.pagina
        if entry.porcentagem is not None:
            positions["percentage"] = entry.porcentagem

        book = per_book.setdefault(
            entry.leitura_id,
            {
                **metadata.get(
                    entry.leitura_id,
                    {
                        "reading_id": entry.leitura_id,
                        "work_key": "",
                        "title": "",
                        "author": "",
                        "cover_url": "",
                    },
                ),
                "sessions": 0,
                "pages_advanced": 0,
                "last_progress": {"type": "session"},
                "latest_at": entry.created_at,
            },
        )
        book["sessions"] += 1
        book["pages_advanced"] += page_delta
        if entry.created_at >= book["latest_at"]:
            book["latest_at"] = entry.created_at
            book["last_progress"] = progress

    highlights = sorted(
        per_book.values(),
        key=lambda book: (
            -int(book["sessions"]),
            -int(book["pages_advanced"]),
            -book["latest_at"].timestamp(),
            str(book["title"]).lower(),
        ),
    )[:4]
    for book in highlights:
        book["latest_at"] = book["latest_at"].replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")

    state = "active" if entries else "empty"
    return {
        "version": 1,
        "period": window.period,
        "offset": window.offset,
        "timezone": "America/Sao_Paulo",
        "start_date": window.start_date,
        "end_date": window.end_date_inclusive,
        "is_current": window.is_current,
        "is_complete": not window.is_current,
        "state": state,
        "sessions": len(entries),
        "active_days": len(active_days),
        "books_touched": len(reading_ids),
        "pages_advanced": pages_advanced,
        "page_sessions_calculable": calculable_page_sessions,
        "progress_types": {
            "page": type_counts["page"],
            "percentage": type_counts["percentage"],
            "chapter": type_counts["chapter"],
            "session": type_counts["session"],
        },
        "highlights": highlights,
        "can_go_newer": window.offset > 0,
        "can_go_older": window.offset < MAX_OFFSET,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


router = APIRouter()


@router.get("/api/eu/retrospectiva", include_in_schema=False)
def get_period_recap(
    request: Request,
    period: str = Query(default="week"),
    offset: int = Query(default=0, ge=0, le=MAX_OFFSET),
    session: Session = Depends(get_session),
):
    if not feature_enabled("period_recaps"):
        raise HTTPException(404, "recurso indisponível")
    user = usuario_sessao(request, session)
    recap = build_period_recap(session, user.id, period_window(period, offset))
    return JSONResponse(
        recap,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def install_product_analytics_contract(product_analytics_module) -> None:
    product_analytics_module.EVENT_PROPERTY_SCHEMAS.setdefault(
        "period_recap",
        {
            "period": frozenset({"week", "month"}),
            "action": frozenset({"viewed", "shared", "navigate"}),
            "state": frozenset({"empty", "active"}),
        },
    )
    product_analytics_module.ALLOWED_EVENT_NAMES = frozenset(
        product_analytics_module.EVENT_PROPERTY_SCHEMAS
    )

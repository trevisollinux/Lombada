"""Painel agregado de ativação e retenção do Lombada.

A resposta nunca contém eventos ou usuários individuais. O acesso exige a flag
interna ``admin_retention_dashboard`` e uma conta Google cujo email esteja em
``ADMIN_EMAILS``, o mesmo mecanismo já usado pelo admin de catálogo.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import Session, select

from analytics_models import ProductEvent
from auth import usuario_sessao
from feature_flags import feature_enabled
from models import Usuario, get_session


router = APIRouter()

ALLOWED_PERIODS = frozenset({7, 30, 90})
FUNNEL_EVENTS = (
    "app_opened",
    "search_submitted",
    "book_opened",
    "reading_created",
    "progress_logged",
    "share_started",
    "profile_connected",
)
SIGNIFICANT_EVENTS = frozenset({
    "search_submitted",
    "book_opened",
    "reading_created",
    "reading_updated",
    "progress_logged",
    "share_started",
    "profile_connected",
})
ACTIVATION_EVENTS = frozenset({"reading_created", "progress_logged"})
DISPLAY_TIMEZONE = "America/Sao_Paulo"
_ADMIN_EMAILS = {
    value.strip().lower()
    for value in os.getenv("ADMIN_EMAILS", "").split(",")
    if value.strip()
}


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _percent(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 1)


def _event_parts(event) -> tuple[int | None, str, datetime]:
    if isinstance(event, dict):
        return event.get("user_id"), str(event.get("event_name") or ""), _utc_naive(event["created_at"])
    return event.user_id, str(event.event_name or ""), _utc_naive(event.created_at)


def calculate_retention_report(
    events: Iterable[ProductEvent | dict],
    *,
    now: datetime,
    days: int,
    truncated: bool = False,
) -> dict:
    """Calcula somente agregados reproduzíveis a partir de eventos já filtrados."""
    if days not in ALLOWED_PERIODS:
        raise ValueError("período inválido")

    now = _utc_naive(now)
    period_start = now - timedelta(days=days)
    wau_start = now - timedelta(days=7)

    by_user: dict[int, list[tuple[str, datetime]]] = defaultdict(list)
    for event in events:
        user_id, event_name, created_at = _event_parts(event)
        if user_id is None or not event_name or created_at > now:
            continue
        by_user[int(user_id)].append((event_name, created_at))

    for rows in by_user.values():
        rows.sort(key=lambda item: item[1])

    funnel_users: dict[str, set[int]] = {name: set() for name in FUNNEL_EVENTS}
    active_period: set[int] = set()
    active_wau: set[int] = set()

    for user_id, rows in by_user.items():
        for event_name, created_at in rows:
            if created_at >= period_start:
                if event_name in funnel_users:
                    funnel_users[event_name].add(user_id)
                if event_name in SIGNIFICANT_EVENTS:
                    active_period.add(user_id)
            if created_at >= wau_start and event_name in SIGNIFICANT_EVENTS:
                active_wau.add(user_id)

    funnel = []
    previous_count: int | None = None
    opened_count = len(funnel_users["app_opened"])
    for event_name in FUNNEL_EVENTS:
        count = len(funnel_users[event_name])
        funnel.append({
            "event": event_name,
            "users": count,
            "conversion_from_previous_pct": _percent(count, previous_count or 0) if previous_count is not None else None,
            "conversion_from_open_pct": _percent(count, opened_count),
        })
        previous_count = count

    cohort_users: list[tuple[int, datetime, list[tuple[str, datetime]]]] = []
    for user_id, rows in by_user.items():
        app_opens = [created_at for event_name, created_at in rows if event_name == "app_opened"]
        cohort_at = min(app_opens) if app_opens else rows[0][1]
        if period_start <= cohort_at <= now:
            cohort_users.append((user_id, cohort_at, rows))

    activated_24h = 0
    activated_7d = 0
    retention = {
        1: {"eligible": 0, "retained": 0},
        7: {"eligible": 0, "retained": 0},
        30: {"eligible": 0, "retained": 0},
    }
    local_tz = ZoneInfo(DISPLAY_TIMEZONE)
    cohort_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"users": 0, "activated_24h": 0, "activated_7d": 0, "d1": 0, "d7": 0, "d30": 0}
    )

    for _user_id, cohort_at, rows in cohort_users:
        activation_times = [
            created_at
            for event_name, created_at in rows
            if event_name in ACTIVATION_EVENTS and created_at >= cohort_at
        ]
        first_activation = min(activation_times) if activation_times else None
        in_24h = bool(first_activation and first_activation < cohort_at + timedelta(days=1))
        in_7d = bool(first_activation and first_activation < cohort_at + timedelta(days=7))
        activated_24h += int(in_24h)
        activated_7d += int(in_7d)

        local_date = cohort_at.replace(tzinfo=timezone.utc).astimezone(local_tz).date().isoformat()
        bucket = cohort_buckets[local_date]
        bucket["users"] += 1
        bucket["activated_24h"] += int(in_24h)
        bucket["activated_7d"] += int(in_7d)

        for target_day in (1, 7, 30):
            window_start = cohort_at + timedelta(days=target_day)
            window_end = window_start + timedelta(days=1)
            # Coortes que ainda não completaram a janela não entram no denominador.
            if now < window_end:
                continue
            retention[target_day]["eligible"] += 1
            retained = any(
                event_name in SIGNIFICANT_EVENTS and window_start <= created_at < window_end
                for event_name, created_at in rows
            )
            retention[target_day]["retained"] += int(retained)
            bucket[f"d{target_day}"] += int(retained)

    retention_payload = {
        f"d{target_day}": {
            **values,
            "rate_pct": _percent(values["retained"], values["eligible"]),
        }
        for target_day, values in retention.items()
    }

    cohort_rows = []
    for cohort_date, values in sorted(cohort_buckets.items(), reverse=True):
        cohort_rows.append({
            "date": cohort_date,
            **values,
            "activation_24h_pct": _percent(values["activated_24h"], values["users"]),
            "activation_7d_pct": _percent(values["activated_7d"], values["users"]),
        })

    cohort_count = len(cohort_users)
    return {
        "schema_version": 1,
        "generated_at_utc": now.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "display_timezone": DISPLAY_TIMEZONE,
        "period_days": days,
        "period_start_utc": period_start.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "data_truncated": bool(truncated),
        "definitions": {
            "active_user": "usuário com evento significativo no período",
            "activation": ["reading_created", "progress_logged"],
            "cohort": "primeiro app_opened; na ausência, primeiro evento observado",
            "retention_windows": {"d1": "24h–48h", "d7": "168h–192h", "d30": "720h–744h"},
        },
        "summary": {
            "active_users": len(active_period),
            "wau": len(active_wau),
            "cohort_users": cohort_count,
            "activated_24h": activated_24h,
            "activation_24h_pct": _percent(activated_24h, cohort_count),
            "activated_7d": activated_7d,
            "activation_7d_pct": _percent(activated_7d, cohort_count),
        },
        "funnel": funnel,
        "retention": retention_payload,
        "cohorts": cohort_rows,
    }


def _retention_max_rows() -> int:
    try:
        return min(200_000, max(1_000, int(os.getenv("RETENTION_DASHBOARD_MAX_ROWS", "50000"))))
    except ValueError:
        return 50_000


def _require_dashboard_admin(request: Request, session: Session) -> Usuario:
    if not feature_enabled("admin_retention_dashboard"):
        raise HTTPException(404, "não encontrado")
    user = usuario_sessao(request, session)
    email = (user.email or "").strip().lower()
    if not email or email not in _ADMIN_EMAILS:
        raise HTTPException(404, "não encontrado")
    return user


def build_report_from_session(session: Session, *, days: int, now: datetime | None = None) -> dict:
    if days not in ALLOWED_PERIODS:
        raise HTTPException(422, "período permitido: 7, 30 ou 90 dias")
    now = _utc_naive(now or datetime.utcnow())
    # ProductEvent tem retenção de 90 dias. Consultar a janela inteira evita
    # classificar um retorno recente como uma nova coorte dentro do período menor.
    retained_since = now - timedelta(days=90)
    max_rows = _retention_max_rows()
    rows = session.exec(
        select(ProductEvent)
        .join(Usuario, ProductEvent.user_id == Usuario.id)
        .where(
            ProductEvent.user_id.is_not(None),
            ProductEvent.created_at >= retained_since,
            Usuario.is_demo == False,  # noqa: E712
        )
        .order_by(ProductEvent.created_at.asc(), ProductEvent.id.asc())
        .limit(max_rows + 1)
    ).all()
    truncated = len(rows) > max_rows
    if truncated:
        rows = rows[:max_rows]
    return calculate_retention_report(rows, now=now, days=days, truncated=truncated)


def _fmt_pct(value) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _dashboard_html(report: dict) -> str:
    summary = report["summary"]
    retention = report["retention"]
    funnel_labels = {
        "app_opened": "Abriram o app",
        "search_submitted": "Buscaram um livro",
        "book_opened": "Abriram um livro",
        "reading_created": "Registraram uma leitura",
        "progress_logged": "Atualizaram o progresso",
        "share_started": "Iniciaram compartilhamento",
        "profile_connected": "Conectaram o perfil",
    }
    cards = [
        ("Usuários ativos", summary["active_users"]),
        ("WAU", summary["wau"]),
        ("Ativação 24h", _fmt_pct(summary["activation_24h_pct"])),
        ("Ativação 7d", _fmt_pct(summary["activation_7d_pct"])),
        ("Retenção D1", _fmt_pct(retention["d1"]["rate_pct"])),
        ("Retenção D7", _fmt_pct(retention["d7"]["rate_pct"])),
        ("Retenção D30", _fmt_pct(retention["d30"]["rate_pct"])),
    ]
    funnel_rows = "".join(
        f"<tr><td>{html.escape(funnel_labels.get(row['event'], row['event']))}</td>"
        f"<td>{row['users']}</td><td>{_fmt_pct(row['conversion_from_previous_pct'])}</td></tr>"
        for row in report["funnel"]
    )
    cohort_rows = "".join(
        f"<tr><td>{html.escape(row['date'])}</td><td>{row['users']}</td>"
        f"<td>{_fmt_pct(row['activation_24h_pct'])}</td><td>{_fmt_pct(row['activation_7d_pct'])}</td>"
        f"<td>{row['d1']}</td><td>{row['d7']}</td><td>{row['d30']}</td></tr>"
        for row in report["cohorts"][:45]
    ) or '<tr><td colspan="7">Ainda não há dados suficientes.</td></tr>'
    warning = '<p class="warning">A consulta atingiu o limite de linhas; números podem estar incompletos.</p>' if report["data_truncated"] else ""
    cards_html = "".join(f"<article><span>{html.escape(label)}</span><strong>{value}</strong></article>" for label, value in cards)
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Retenção · Admin · Lombada</title>
<style>
body{{font-family:system-ui,sans-serif;background:#171310;color:#f4efe6;margin:0}}main{{max-width:1100px;margin:auto;padding:24px}}a{{color:#d6a75b}}h1{{font-family:Georgia,serif}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}}article{{background:#241d18;border:1px solid #44372d;border-radius:12px;padding:16px}}article span{{display:block;color:#c9b9a7;font-size:13px}}article strong{{font-size:28px}}table{{width:100%;border-collapse:collapse;margin:18px 0;background:#211a16}}th,td{{padding:10px;border-bottom:1px solid #44372d;text-align:left}}.table-wrap{{overflow:auto}}.periods a{{margin-right:12px}}.warning{{background:#5a2d20;padding:12px;border-radius:8px}}
</style></head><body><main>
<p><a href="/admin">← voltar ao admin</a></p><h1>Ativação e retenção</h1>
<p>Período: últimos {report['period_days']} dias · gerado em {html.escape(report['generated_at_utc'])} · datas exibidas em {DISPLAY_TIMEZONE}.</p>
<p class="periods"><a href="?days=7">7 dias</a><a href="?days=30">30 dias</a><a href="?days=90">90 dias</a></p>{warning}
<section class="cards">{cards_html}</section>
<h2>Funil</h2><div class="table-wrap"><table><thead><tr><th>Etapa</th><th>Usuários</th><th>Conversão da etapa anterior</th></tr></thead><tbody>{funnel_rows}</tbody></table></div>
<h2>Coortes</h2><p>Somente totais agregados; nenhuma pessoa ou evento individual é exibido.</p>
<div class="table-wrap"><table><thead><tr><th>Data</th><th>Usuários</th><th>Ativação 24h</th><th>Ativação 7d</th><th>Retidos D1</th><th>D7</th><th>D30</th></tr></thead><tbody>{cohort_rows}</tbody></table></div>
<p><a href="/api/admin/retention?days={report['period_days']}">ver JSON agregado</a></p>
</main></body></html>"""


@router.get("/api/admin/retention", include_in_schema=False)
def api_retention_dashboard(
    request: Request,
    days: int = Query(30),
    session: Session = Depends(get_session),
):
    _require_dashboard_admin(request, session)
    report = build_report_from_session(session, days=days)
    return JSONResponse(report, headers={"Cache-Control": "no-store, max-age=0"})


@router.get("/admin/retention", include_in_schema=False)
def retention_dashboard_page(
    request: Request,
    days: int = Query(30),
    session: Session = Depends(get_session),
):
    _require_dashboard_admin(request, session)
    report = build_report_from_session(session, days=days)
    return HTMLResponse(_dashboard_html(report), headers={"Cache-Control": "no-store, max-age=0"})

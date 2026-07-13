#!/usr/bin/env python3
"""
Carrega o cadastro normalizado de editoras e injeta as fontes habilitadas no
scraper principal, sem duplicar as fontes que já têm configuração especializada.

Uso:
    python scripts/sync_publishers_catalog.py

As mesmas variáveis de ambiente de sync_publishers.py continuam válidas:
PUBLISHER_GROUP, PUBLISHER_SLUGS, PUBLISHER_DIAGNOSE, PUBLISHER_DRY_RUN etc.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "publishers"
_ALLOWED_STATUS = {"active"}
_COPYABLE_SCRAPE_KEYS = {
    "platform",
    "platforms",
    "id_template",
    "id_start",
    "id_end",
}


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split("|") if item.strip()]


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    """Lê todos os CSVs do diretório e devolve um catálogo único."""
    files = sorted(path.glob("*.csv")) if path.is_dir() else [path]
    rows: list[dict[str, str]] = []
    for file_path in files:
        with file_path.open(encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    if not rows:
        raise ValueError("nenhum registro encontrado no catálogo de editoras")
    publishers: list[dict[str, Any]] = []
    for row in rows:
        publishers.append(
            {
                "slug": row["slug"].strip(),
                "name": row["name"].strip(),
                "aliases": _split_list(row.get("aliases", "")),
                "previous_names": _split_list(row.get("previous_names", "")),
                "category": row["category"].strip(),
                "focus": row["focus"].strip(),
                "status": row["status"].strip(),
                "entity_type": row["entity_type"].strip(),
                "notes": row.get("notes", "").strip(),
                "scrape": {
                    "enabled": row.get("scrape_enabled", "").strip().lower() == "true",
                    "base_url": row.get("base_url", "").strip(),
                    "url_status": row.get("url_status", "").strip(),
                    "platform": row.get("platform", "").strip() or "auto",
                    "group": row.get("group", "").strip(),
                    "priority": int(row.get("priority", "3") or 3),
                },
            }
        )
    return {"schema_version": 1, "publishers": publishers}


def scraper_sources(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Converte somente editoras ativas e habilitadas em SOURCES do scraper."""
    result: list[dict[str, Any]] = []
    for publisher in catalog["publishers"]:
        scrape = publisher.get("scrape") or {}
        base_url = str(scrape.get("base_url") or "").strip()
        if publisher.get("status") not in _ALLOWED_STATUS:
            continue
        if not scrape.get("enabled") or not base_url:
            continue

        source: dict[str, Any] = {
            "slug": publisher["slug"],
            "name": publisher["name"],
            "base_url": base_url.rstrip("/"),
            "platform": scrape.get("platform") or "auto",
            "group": scrape.get("group") or "catalogo_a",
        }
        for key in _COPYABLE_SCRAPE_KEYS:
            if key in scrape and scrape[key] not in (None, "", []):
                source[key] = scrape[key]
        result.append(source)
    return result


def extend_sources(sync_module: Any, catalog: dict[str, Any] | None = None) -> int:
    """
    Acrescenta fontes do catálogo ao módulo sync_publishers.

    A configuração especializada já existente sempre vence. Isso preserva, por
    exemplo, id_range da Editora 34 e categoria_json da Companhia das Letras.
    """
    catalog = catalog or load_catalog()
    existing = {source["slug"].lower() for source in sync_module.SOURCES}
    added = 0
    for source in scraper_sources(catalog):
        if source["slug"].lower() in existing:
            continue
        sync_module.SOURCES.append(source)
        existing.add(source["slug"].lower())
        added += 1
    return added


def main() -> int:
    import sync_publishers

    catalog = load_catalog()
    candidates = scraper_sources(catalog)
    added = extend_sources(sync_publishers, catalog)
    print(
        "Catálogo de editoras: "
        f"{len(catalog['publishers'])} cadastradas · "
        f"{len(candidates)} habilitadas · "
        f"{added} novas fontes injetadas · "
        f"{len(candidates) - added} já configuradas no scraper principal."
    )
    return sync_publishers.main()


if __name__ == "__main__":
    raise SystemExit(main())

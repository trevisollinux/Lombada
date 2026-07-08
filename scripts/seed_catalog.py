"""Importa o catálogo inicial de data/catalog_seed.json no DATABASE_URL.

O seed é idempotente: reaproveita obras/edições existentes por work_key,
ol_edition_key, ISBN ou combinação obra/editora/tradutor/ano.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _require_database_url() -> None:
    if not os.getenv("DATABASE_URL", "").strip():
        raise SystemExit(
            "DATABASE_URL não definido. Exemplo: "
            "DATABASE_URL='postgresql://usuario:senha@host:porta/db' python scripts/seed_catalog.py"
        )


def main() -> None:
    _require_database_url()
    os.environ["CATALOG_SEED_ENABLED"] = "1"

    from sqlmodel import SQLModel
    from models import engine, migrar
    from main import seed_catalog_content

    SQLModel.metadata.create_all(engine)
    migrar()
    seed_catalog_content()
    print("Seed de catálogo concluído a partir de data/catalog_seed.json.")


if __name__ == "__main__":
    main()

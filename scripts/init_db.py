"""Inicializa o banco configurado por DATABASE_URL sem apagar dados.

Uso:
    DATABASE_URL='postgresql://...' python scripts/init_db.py
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
            "DATABASE_URL='postgresql://usuario:senha@host:porta/db' python scripts/init_db.py"
        )


def main() -> None:
    _require_database_url()
    from sqlmodel import SQLModel
    from sqlalchemy import text
    from models import engine, migrar

    SQLModel.metadata.create_all(engine)
    migrar()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print(f"Banco inicializado com sucesso usando dialect={engine.dialect.name}.")


if __name__ == "__main__":
    main()

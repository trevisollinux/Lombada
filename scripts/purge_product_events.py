"""Remove eventos de produto antigos em lotes controlados.

Por padrão apenas conta o lote elegível. Use ``--apply`` para excluir.
Nunca imprime DATABASE_URL, propriedades ou identificadores de usuário.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session  # noqa: E402

from models import engine  # noqa: E402
from product_analytics import purge_product_events  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Limpa ProductEvent além da retenção configurada.")
    parser.add_argument("--days", type=int, default=90, help="Retenção em dias; padrão: 90")
    parser.add_argument("--limit", type=int, default=5000, help="Máximo por execução; padrão: 5000")
    parser.add_argument("--apply", action="store_true", help="Executa a exclusão; sem esta flag é dry-run")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    days = min(3650, max(1, args.days))
    limit = min(50_000, max(1, args.limit))
    cutoff = datetime.utcnow() - timedelta(days=days)

    with Session(engine) as session:
        count = purge_product_events(
            session,
            before=cutoff,
            limit=limit,
            apply=args.apply,
        )

    mode = "aplicado" if args.apply else "dry-run"
    print(f"product_events_cleanup mode={mode} days={days} limit={limit} matched={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Renomeia handles de usuários demo antigos (prefixo "demo-", de um dump
anterior) para os handles novos, sem prefixo.

Faz SÓ isso: `UPDATE usuario SET handle = novo WHERE handle = antigo`.
Não mexe em Follow, Leitura, ReadingJournalEntry, ReviewLike nem nada
mais -- ao contrário de seed_demo_users.py, que reseta toda a atividade
social de usuários demo a cada execução (e apagaria follows reais que
apontam pra esses perfis). Segue esse padrão pra quem já segue um
perfil demo continuar seguindo, só que com o handle certo.

Dry-run é o padrão. Use --apply para persistir.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select  # noqa: E402

from models import Usuario, engine, migrar  # noqa: E402
from scripts.seed_demo_users import LEGACY_HANDLE_RENAMES  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Mostra o que seria feito sem persistir (padrão).")
    mode.add_argument("--apply", action="store_true", help="Persiste as mudanças.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    apply = bool(args.apply)
    migrar()
    renamed = 0
    skipped_missing = 0
    skipped_taken = 0
    with Session(engine) as session:
        for old_handle, new_handle in LEGACY_HANDLE_RENAMES:
            user = session.exec(select(Usuario).where(Usuario.handle == old_handle)).first()
            if not user:
                skipped_missing += 1
                continue
            taken_by = session.exec(select(Usuario).where(Usuario.handle == new_handle)).first()
            if taken_by and taken_by.id != user.id:
                print(f"AVISO: handle novo já em uso, pulando: {old_handle} -> {new_handle}")
                skipped_taken += 1
                continue
            print(f"{'[apply]' if apply else '[dry-run]'} {old_handle} -> {new_handle} (usuario_id={user.id})")
            user.handle = new_handle
            session.add(user)
            renamed += 1
        if apply:
            session.commit()
        else:
            session.rollback()
    print(
        f"\n{'APPLY' if apply else 'DRY RUN'} -- "
        f"renomeados: {renamed}, sem correspondência (já renomeado ou nunca existiu): {skipped_missing}, "
        f"pulados por colisão de handle: {skipped_taken}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

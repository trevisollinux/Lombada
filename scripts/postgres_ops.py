#!/usr/bin/env python3
"""Backup, restauração temporária e verificação do PostgreSQL do Lombada.

As URLs são lidas apenas de variáveis de ambiente. Credenciais são convertidas
para variáveis PG* dos subprocessos e nunca aparecem nos argumentos ou logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import parse_qs, unquote, urlparse


SOURCE_URL_ENV = "DATABASE_URL"
RESTORE_URL_ENV = "RESTORE_DATABASE_URL"
RESTORE_CONFIRM_ENV = "RESTORE_CONFIRM"
RESTORE_CONFIRM_VALUE = "RESTORE_TEMP_DATABASE"
RESTORE_ALLOWED_DB_ENV = "RESTORE_ALLOWED_DATABASE"
TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


class OperationError(RuntimeError):
    """Erro operacional seguro para exibição, sem dados de conexão."""


@dataclass(frozen=True)
class DatabaseTarget:
    host: str
    port: int
    user: str
    password: str
    database: str
    sslmode: str | None = None

    @classmethod
    def from_url(cls, raw_url: str, *, variable: str) -> "DatabaseTarget":
        if not raw_url:
            raise OperationError(f"variável {variable} não definida")
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise OperationError(f"{variable} deve usar postgres:// ou postgresql://")
        if not parsed.hostname or not parsed.username:
            raise OperationError(f"{variable} está incompleta")
        database = unquote(parsed.path.lstrip("/"))
        if not database:
            raise OperationError(f"{variable} não informa o banco")
        query = parse_qs(parsed.query)
        sslmode = query.get("sslmode", [None])[0]
        return cls(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=unquote(parsed.username),
            password=unquote(parsed.password or ""),
            database=database,
            sslmode=sslmode,
        )

    @property
    def identity(self) -> tuple[str, int, str]:
        return (self.host.lower().rstrip("."), self.port, self.database)

    def subprocess_env(self, base: Mapping[str, str] | None = None) -> dict[str, str]:
        env = dict(base or os.environ)
        # Evita que ferramentas-filhas recebam as URLs completas por herança.
        env.pop(SOURCE_URL_ENV, None)
        env.pop(RESTORE_URL_ENV, None)
        env.update(
            {
                "PGHOST": self.host,
                "PGPORT": str(self.port),
                "PGUSER": self.user,
                "PGPASSWORD": self.password,
                "PGDATABASE": self.database,
                "PGCONNECT_TIMEOUT": env.get("PGCONNECT_TIMEOUT", "15"),
            }
        )
        if self.sslmode:
            env["PGSSLMODE"] = self.sslmode
        return env


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise OperationError(f"ferramenta obrigatória não encontrada: {name}")
    return path


def _run(
    command: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(command),
            env=dict(env) if env is not None else None,
            check=False,
            text=True,
            capture_output=capture,
        )
    except OSError as exc:
        raise OperationError(f"não foi possível executar {Path(command[0]).name}") from exc
    if result.returncode != 0:
        # Não reproduz stderr porque clientes PostgreSQL podem incluir detalhes
        # de conexão em mensagens de erro dependendo da versão/configuração.
        raise OperationError(
            f"{Path(command[0]).name} falhou com código {result.returncode}"
        )
    return result


def _source_target(environ: Mapping[str, str] | None = None) -> DatabaseTarget:
    env = environ or os.environ
    return DatabaseTarget.from_url(env.get(SOURCE_URL_ENV, ""), variable=SOURCE_URL_ENV)


def _restore_target(environ: Mapping[str, str] | None = None) -> DatabaseTarget:
    env = environ or os.environ
    return DatabaseTarget.from_url(env.get(RESTORE_URL_ENV, ""), variable=RESTORE_URL_ENV)


def require_restore_guard(
    source: DatabaseTarget,
    destination: DatabaseTarget,
    environ: Mapping[str, str] | None = None,
) -> None:
    env = environ or os.environ
    if source.identity == destination.identity:
        raise OperationError("restore recusado: origem e destino apontam para o mesmo banco")
    if env.get(RESTORE_CONFIRM_ENV) != RESTORE_CONFIRM_VALUE:
        raise OperationError(
            f"restore recusado: defina {RESTORE_CONFIRM_ENV}={RESTORE_CONFIRM_VALUE}"
        )
    allowed_database = env.get(RESTORE_ALLOWED_DB_ENV, "")
    if not allowed_database:
        raise OperationError(
            f"restore recusado: defina {RESTORE_ALLOWED_DB_ENV} com o nome exato do banco temporário"
        )
    if allowed_database != destination.database:
        raise OperationError(
            f"restore recusado: {RESTORE_ALLOWED_DB_ENV} não corresponde ao destino"
        )


def _secure_output_path(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        output_dir.chmod(0o700)
    except OSError:
        pass
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = output_dir / f"lombada-{timestamp}.dump"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"lombada-{timestamp}-{suffix}.dump"
        suffix += 1
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dump(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise OperationError("arquivo de backup inexistente ou vazio")
    _run([_tool("pg_restore"), "--list", str(path)])


def backup(output_dir: Path, environ: Mapping[str, str] | None = None) -> dict:
    source = _source_target(environ)
    pg_dump = _tool("pg_dump")
    _tool("pg_restore")
    output_path = _secure_output_path(output_dir)
    started = time.monotonic()
    try:
        _run(
            [
                pg_dump,
                "--format=custom",
                "--compress=6",
                "--no-owner",
                "--no-privileges",
                f"--file={output_path}",
            ],
            env=source.subprocess_env(environ),
        )
        output_path.chmod(0o600)
        validate_dump(output_path)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return {
        "operation": "backup",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "file": str(output_path),
        "bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
        "duration_seconds": round(time.monotonic() - started, 2),
    }


def _quote_identifier(name: str) -> str:
    if not TABLE_NAME_RE.fullmatch(name):
        raise OperationError("nome de tabela inesperado durante verificação")
    return '"' + name.replace('"', '""') + '"'


def _psql(target: DatabaseTarget, sql: str, environ: Mapping[str, str] | None = None) -> str:
    result = _run(
        [
            _tool("psql"),
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--set=ON_ERROR_STOP=1",
            f"--dbname={target.database}",
            "--command",
            sql,
        ],
        env=target.subprocess_env(environ),
    )
    return result.stdout.strip()


def table_counts(
    target: DatabaseTarget,
    environ: Mapping[str, str] | None = None,
) -> dict[str, int]:
    table_output = _psql(
        target,
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;",
        environ,
    )
    table_names = [line.strip() for line in table_output.splitlines() if line.strip()]
    counts: dict[str, int] = {}
    for table_name in table_names:
        quoted = _quote_identifier(table_name)
        raw_count = _psql(
            target,
            f'SELECT count(*) FROM "public".{quoted};',
            environ,
        )
        try:
            counts[table_name] = int(raw_count)
        except ValueError as exc:
            raise OperationError("contagem inválida retornada pelo PostgreSQL") from exc
    return counts


def compare_counts(
    source: DatabaseTarget,
    destination: DatabaseTarget,
    environ: Mapping[str, str] | None = None,
) -> dict:
    source_counts = table_counts(source, environ)
    destination_counts = table_counts(destination, environ)
    tables = sorted(set(source_counts) | set(destination_counts))
    mismatches = [
        {
            "table": table,
            "source": source_counts.get(table),
            "destination": destination_counts.get(table),
        }
        for table in tables
        if source_counts.get(table) != destination_counts.get(table)
    ]
    return {
        "tables_checked": len(tables),
        "matching": not mismatches,
        "mismatches": mismatches,
    }


def verify(environ: Mapping[str, str] | None = None) -> dict:
    source = _source_target(environ)
    destination = _restore_target(environ)
    require_restore_guard(source, destination, environ)
    started = time.monotonic()
    result = compare_counts(source, destination, environ)
    result.update(
        {
            "operation": "verify",
            "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "duration_seconds": round(time.monotonic() - started, 2),
        }
    )
    if not result["matching"]:
        raise OperationError(
            "verificação falhou: contagens divergentes; consulte o relatório JSON gerado em memória"
        )
    return result


def restore(dump_path: Path, environ: Mapping[str, str] | None = None) -> dict:
    source = _source_target(environ)
    destination = _restore_target(environ)
    require_restore_guard(source, destination, environ)
    validate_dump(dump_path)
    started = time.monotonic()
    _run(
        [
            _tool("pg_restore"),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            f"--dbname={destination.database}",
            str(dump_path),
        ],
        env=destination.subprocess_env(environ),
    )
    comparison = compare_counts(source, destination, environ)
    result = {
        "operation": "restore",
        "restored_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "file": str(dump_path),
        "duration_seconds": round(time.monotonic() - started, 2),
        **comparison,
    }
    if not comparison["matching"]:
        raise OperationError("restore concluído, mas as contagens divergem")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backup e restauração segura do PostgreSQL do Lombada"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="gera e valida um pg_dump custom")
    backup_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.getenv("BACKUP_DIR", "backups")),
    )

    restore_parser = subparsers.add_parser(
        "restore", help="restaura em banco temporário e compara contagens"
    )
    restore_parser.add_argument("--dump", required=True, type=Path)

    subparsers.add_parser("verify", help="compara contagens entre origem e destino")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "backup":
            result = backup(args.output_dir)
        elif args.command == "restore":
            result = restore(args.dump)
        else:
            result = verify()
    except OperationError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

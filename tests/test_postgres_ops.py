"""Testes dos scripts operacionais de backup e restauração.

Nenhum teste acessa PostgreSQL real ou usa segredo de produção.
"""
from __future__ import annotations

import stat
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from scripts import postgres_ops


SOURCE_URL = "postgresql://source_user:source-secret@source.example:5432/lombada"
DEST_URL = "postgresql://restore_user:restore-secret@restore.example:5432/lombada_restore"
SAFE_ENV = {
    "DATABASE_URL": SOURCE_URL,
    "RESTORE_DATABASE_URL": DEST_URL,
    "RESTORE_CONFIRM": "RESTORE_TEMP_DATABASE",
    "RESTORE_ALLOWED_DATABASE": "lombada_restore",
}


class DatabaseTargetTest(TestCase):
    def test_url_is_parsed_and_child_environment_does_not_inherit_urls(self):
        target = postgres_ops.DatabaseTarget.from_url(SOURCE_URL, variable="DATABASE_URL")
        child = target.subprocess_env(
            {"DATABASE_URL": SOURCE_URL, "RESTORE_DATABASE_URL": DEST_URL, "OTHER": "ok"}
        )

        self.assertEqual(target.identity, ("source.example", 5432, "lombada"))
        self.assertNotIn("DATABASE_URL", child)
        self.assertNotIn("RESTORE_DATABASE_URL", child)
        self.assertEqual(child["PGPASSWORD"], "source-secret")
        self.assertEqual(child["PGDATABASE"], "lombada")
        self.assertEqual(child["OTHER"], "ok")

    def test_invalid_or_incomplete_url_is_rejected_without_echoing_value(self):
        secret = "do-not-print-this"
        with self.assertRaises(postgres_ops.OperationError) as raised:
            postgres_ops.DatabaseTarget.from_url(secret, variable="DATABASE_URL")
        self.assertNotIn(secret, str(raised.exception))


class RestoreGuardTest(TestCase):
    def setUp(self):
        self.source = postgres_ops.DatabaseTarget.from_url(SOURCE_URL, variable="DATABASE_URL")
        self.destination = postgres_ops.DatabaseTarget.from_url(
            DEST_URL, variable="RESTORE_DATABASE_URL"
        )

    def test_same_database_is_always_rejected(self):
        same = postgres_ops.DatabaseTarget.from_url(SOURCE_URL, variable="RESTORE_DATABASE_URL")
        with self.assertRaisesRegex(postgres_ops.OperationError, "mesmo banco"):
            postgres_ops.require_restore_guard(self.source, same, SAFE_ENV)

    def test_confirmation_is_required(self):
        env = dict(SAFE_ENV)
        env.pop("RESTORE_CONFIRM")
        with self.assertRaisesRegex(postgres_ops.OperationError, "RESTORE_CONFIRM"):
            postgres_ops.require_restore_guard(self.source, self.destination, env)

    def test_exact_destination_database_name_is_required(self):
        env = dict(SAFE_ENV, RESTORE_ALLOWED_DATABASE="outro_banco")
        with self.assertRaisesRegex(postgres_ops.OperationError, "não corresponde"):
            postgres_ops.require_restore_guard(self.source, self.destination, env)

    def test_valid_temporary_destination_passes(self):
        postgres_ops.require_restore_guard(self.source, self.destination, SAFE_ENV)


class BackupCommandTest(TestCase):
    def test_backup_uses_pg_environment_and_restricted_file(self):
        calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_run(command, *, env=None, capture=True):
            command = list(command)
            calls.append((command, dict(env) if env is not None else None))
            for argument in command:
                if argument.startswith("--file="):
                    Path(argument.split("=", 1)[1]).write_bytes(b"valid custom dump")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            postgres_ops, "_tool", side_effect=lambda name: name
        ), patch.object(postgres_ops, "_run", side_effect=fake_run), patch.object(
            postgres_ops, "validate_dump", return_value=None
        ):
            result = postgres_ops.backup(Path(tmp), SAFE_ENV)
            output = Path(result["file"])

        pg_dump_command, child_env = calls[0]
        joined = " ".join(pg_dump_command)
        self.assertNotIn(SOURCE_URL, joined)
        self.assertNotIn("source-secret", joined)
        self.assertNotIn("DATABASE_URL", child_env)
        self.assertEqual(child_env["PGPASSWORD"], "source-secret")
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertEqual(result["bytes"], len(b"valid custom dump"))
        self.assertEqual(len(result["sha256"]), 64)


class RestoreCommandTest(TestCase):
    def test_restore_never_places_connection_url_or_password_in_arguments(self):
        calls: list[tuple[list[str], dict[str, str] | None]] = []

        def fake_run(command, *, env=None, capture=True):
            calls.append((list(command), dict(env) if env is not None else None))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / "backup.dump"
            dump.write_bytes(b"dump")
            with patch.object(postgres_ops, "_tool", side_effect=lambda name: name), patch.object(
                postgres_ops, "_run", side_effect=fake_run
            ), patch.object(postgres_ops, "validate_dump", return_value=None), patch.object(
                postgres_ops,
                "compare_counts",
                return_value={"tables_checked": 5, "matching": True, "mismatches": []},
            ):
                result = postgres_ops.restore(dump, SAFE_ENV)

        restore_command, child_env = calls[0]
        joined = " ".join(restore_command)
        self.assertIn("--dbname=lombada_restore", restore_command)
        self.assertNotIn(DEST_URL, joined)
        self.assertNotIn("restore-secret", joined)
        self.assertNotIn("RESTORE_DATABASE_URL", child_env)
        self.assertEqual(child_env["PGPASSWORD"], "restore-secret")
        self.assertTrue(result["matching"])


class CountVerificationTest(TestCase):
    def test_compare_counts_reports_only_table_names_and_aggregates(self):
        source = postgres_ops.DatabaseTarget.from_url(SOURCE_URL, variable="DATABASE_URL")
        destination = postgres_ops.DatabaseTarget.from_url(
            DEST_URL, variable="RESTORE_DATABASE_URL"
        )
        with patch.object(
            postgres_ops,
            "table_counts",
            side_effect=[{"usuario": 10, "leitura": 25}, {"usuario": 10, "leitura": 24}],
        ):
            report = postgres_ops.compare_counts(source, destination, SAFE_ENV)

        self.assertFalse(report["matching"])
        self.assertEqual(
            report["mismatches"],
            [{"table": "leitura", "source": 25, "destination": 24}],
        )
        serialized = str(report).lower()
        self.assertNotIn("source-secret", serialized)
        self.assertNotIn("restore-secret", serialized)
        self.assertNotIn("email", serialized)

    def test_unexpected_table_identifier_is_rejected(self):
        with self.assertRaisesRegex(postgres_ops.OperationError, "nome de tabela"):
            postgres_ops._quote_identifier('usuario"; drop table usuario; --')


if __name__ == "__main__":
    import unittest

    unittest.main()

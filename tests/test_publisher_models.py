"""Testes do domínio normalizado de editoras e selos."""
import unittest
from unittest.mock import patch

import models


class PublisherModelsTest(unittest.TestCase):
    def test_expected_tables_are_registered(self):
        expected = {
            "publishergroup",
            "publisher",
            "imprint",
            "publisheralias",
            "publishersource",
        }
        self.assertTrue(expected.issubset(models.SQLModel.metadata.tables))

    def test_edition_keeps_legacy_name_and_optional_references(self):
        columns = models.Edicao.__table__.columns
        self.assertIn("editora", columns)
        self.assertIn("editora_raw", columns)
        self.assertTrue(columns["publisher_id"].nullable)
        self.assertTrue(columns["imprint_id"].nullable)
        self.assertEqual(
            next(iter(columns["publisher_id"].foreign_keys)).target_fullname,
            "publisher.id",
        )
        self.assertEqual(
            next(iter(columns["imprint_id"].foreign_keys)).target_fullname,
            "imprint.id",
        )

    def test_imprint_name_is_unique_inside_publisher(self):
        names = {constraint.name for constraint in models.Imprint.__table__.constraints}
        self.assertIn("uq_imprint_publisher_name", names)

    def test_alias_targets_exactly_one_entity(self):
        names = {constraint.name for constraint in models.PublisherAlias.__table__.constraints}
        self.assertIn("ck_publisheralias_one_target", names)
        self.assertIn("uq_publisheralias_normalized", names)

    def test_migration_adds_edition_reference_columns(self):
        with patch.object(models, "_is_postgres", return_value=False), patch.object(
            models, "_add_column_if_missing"
        ) as add_column, patch.object(models, "_run_ddl"):
            models.migrar()

        calls = {(call.args[0], call.args[1]) for call in add_column.call_args_list}
        self.assertIn(("edicao", "editora_raw"), calls)
        self.assertIn(("edicao", "publisher_id"), calls)
        self.assertIn(("edicao", "imprint_id"), calls)


if __name__ == "__main__":
    unittest.main()

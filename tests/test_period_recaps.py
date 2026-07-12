"""Testes das retrospectivas semanais e mensais."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import product_analytics
from feature_flags import feature_enabled, public_feature_flags
from models import Edicao, Leitura, Obra, ReadingJournalEntry, Usuario
from period_recaps import (
    build_period_recap,
    install_product_analytics_contract,
    period_window,
)
from product_analytics import ProductEventInput, validate_product_event


ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


class PeriodWindowTest(TestCase):
    def test_week_uses_monday_in_sao_paulo_and_exclusive_end(self):
        window = period_window(
            "week",
            0,
            now=datetime(2026, 7, 12, 20, 0, tzinfo=UTC),
        )
        self.assertEqual(window.start_date, "2026-07-06")
        self.assertEqual(window.end_date_inclusive, "2026-07-12")
        self.assertEqual(window.start_utc, datetime(2026, 7, 6, 3, 0))
        self.assertEqual(window.end_utc, datetime(2026, 7, 13, 3, 0))
        self.assertTrue(window.is_current)

        previous = period_window(
            "week",
            1,
            now=datetime(2026, 7, 12, 20, 0, tzinfo=UTC),
        )
        self.assertEqual(previous.start_date, "2026-06-29")
        self.assertEqual(previous.end_date_inclusive, "2026-07-05")
        self.assertFalse(previous.is_current)

    def test_month_shift_crosses_year_boundary(self):
        window = period_window(
            "month",
            1,
            now=datetime(2026, 1, 15, 15, 0, tzinfo=UTC),
        )
        self.assertEqual(window.start_date, "2025-12-01")
        self.assertEqual(window.end_date_inclusive, "2025-12-31")
        self.assertEqual(window.start_utc, datetime(2025, 12, 1, 3, 0))
        self.assertEqual(window.end_utc, datetime(2026, 1, 1, 3, 0))

    def test_invalid_period_and_offset_are_rejected(self):
        with self.assertRaises(HTTPException):
            period_window("year", 0)
        with self.assertRaises(HTTPException):
            period_window("week", 13)
        with self.assertRaises(HTTPException):
            period_window("month", -1)


class PeriodRecapDatabaseTest(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            user = Usuario(handle="memoria", nome="Memória")
            session.add(user)
            session.commit()
            session.refresh(user)
            self.user_id = user.id

            self.reading_ids = []
            for index in range(1, 3):
                work = Obra(
                    ol_work_key=f"work:{index}",
                    titulo=f"Livro {index}",
                    autor=f"Autor {index}",
                )
                session.add(work)
                session.commit()
                session.refresh(work)
                edition = Edicao(
                    obra_id=work.id,
                    ol_edition_key=f"edition:{index}",
                    capa_url=f"https://covers.example/{index}.jpg",
                    paginas=300,
                )
                session.add(edition)
                session.commit()
                session.refresh(edition)
                reading = Leitura(
                    usuario_id=self.user_id,
                    edicao_id=edition.id,
                    status="Lendo",
                )
                session.add(reading)
                session.commit()
                session.refresh(reading)
                self.reading_ids.append(reading.id)

    def add_entry(self, session: Session, reading_index: int, created_at: datetime, **values):
        entry = ReadingJournalEntry(
            leitura_id=self.reading_ids[reading_index],
            usuario_id=self.user_id,
            created_at=created_at,
            updated_at=created_at,
            progresso_tipo=values.pop("progresso_tipo", "livre"),
            **values,
        )
        session.add(entry)
        session.commit()
        return entry

    def test_recap_sums_only_positive_trustworthy_page_deltas(self):
        window = period_window(
            "week",
            0,
            now=datetime(2026, 7, 12, 20, 0, tzinfo=UTC),
        )
        with Session(self.engine) as session:
            # Base anterior: permite calcular a primeira atualização da semana.
            self.add_entry(
                session,
                0,
                datetime(2026, 7, 5, 12, 0),
                progresso_tipo="pagina",
                pagina=10,
                nota="texto privado anterior",
            )
            self.add_entry(
                session,
                0,
                datetime(2026, 7, 6, 4, 0),
                progresso_tipo="pagina",
                pagina=25,
                nota="texto privado",
            )
            # Correção para trás é calculável, mas não subtrai nem celebra páginas.
            self.add_entry(
                session,
                0,
                datetime(2026, 7, 7, 5, 0),
                progresso_tipo="pagina",
                pagina=20,
            )
            # Delta persistido é a fonte de verdade quando existe.
            self.add_entry(
                session,
                0,
                datetime(2026, 7, 8, 6, 0),
                progresso_tipo="pagina",
                pagina=27,
                paginas_delta=7,
            )
            self.add_entry(
                session,
                1,
                datetime(2026, 7, 6, 14, 0),
                progresso_tipo="porcentagem",
                porcentagem=20,
            )
            self.add_entry(
                session,
                1,
                datetime(2026, 7, 9, 14, 0),
                progresso_tipo="capitulo",
                capitulo="A casa no lago",
                nota="não deve sair na resposta",
            )

            recap = build_period_recap(session, self.user_id, window)

        self.assertEqual(recap["state"], "active")
        self.assertEqual(recap["sessions"], 5)
        self.assertEqual(recap["active_days"], 4)
        self.assertEqual(recap["books_touched"], 2)
        self.assertEqual(recap["pages_advanced"], 22)
        self.assertEqual(recap["page_sessions_calculable"], 3)
        self.assertEqual(
            recap["progress_types"],
            {"page": 3, "percentage": 1, "chapter": 1, "session": 0},
        )
        self.assertEqual(recap["highlights"][0]["title"], "Livro 1")
        self.assertEqual(recap["highlights"][0]["sessions"], 3)
        self.assertEqual(recap["highlights"][0]["pages_advanced"], 22)
        serialized = str(recap).lower()
        self.assertNotIn("texto privado", serialized)
        self.assertNotIn("nota", serialized)
        self.assertNotIn("spoiler", serialized)

    def test_start_is_inclusive_and_end_is_exclusive(self):
        window = period_window(
            "week",
            0,
            now=datetime(2026, 7, 12, 20, 0, tzinfo=UTC),
        )
        with Session(self.engine) as session:
            self.add_entry(
                session,
                0,
                window.start_utc,
                progresso_tipo="pagina",
                pagina=10,
            )
            self.add_entry(
                session,
                0,
                window.end_utc,
                progresso_tipo="pagina",
                pagina=20,
                paginas_delta=10,
            )
            recap = build_period_recap(session, self.user_id, window)
        self.assertEqual(recap["sessions"], 1)
        self.assertEqual(recap["pages_advanced"], 0)
        self.assertEqual(recap["page_sessions_calculable"], 0)

    def test_first_page_without_baseline_does_not_invent_pages(self):
        window = period_window(
            "week",
            0,
            now=datetime(2026, 7, 12, 20, 0, tzinfo=UTC),
        )
        with Session(self.engine) as session:
            self.add_entry(
                session,
                0,
                datetime(2026, 7, 6, 12, 0),
                progresso_tipo="pagina",
                pagina=80,
            )
            recap = build_period_recap(session, self.user_id, window)
        self.assertEqual(recap["sessions"], 1)
        self.assertEqual(recap["pages_advanced"], 0)
        self.assertEqual(recap["page_sessions_calculable"], 0)
        self.assertEqual(recap["highlights"][0]["last_progress"], {"type": "page", "value": 80})

    def test_empty_period_is_gentle_and_navigable(self):
        window = period_window(
            "month",
            1,
            now=datetime(2026, 7, 12, 20, 0, tzinfo=UTC),
        )
        with Session(self.engine) as session:
            recap = build_period_recap(session, self.user_id, window)
        self.assertEqual(recap["state"], "empty")
        self.assertEqual(recap["sessions"], 0)
        self.assertEqual(recap["highlights"], [])
        self.assertTrue(recap["is_complete"])
        self.assertTrue(recap["can_go_newer"])


class PeriodRecapFlagAndAnalyticsTest(TestCase):
    def test_flag_is_public_and_off_by_default(self):
        self.assertFalse(feature_enabled("period_recaps", {}))
        self.assertTrue(feature_enabled("period_recaps", {"FF_PERIOD_RECAPS": "true"}))
        self.assertIn("period_recaps", public_feature_flags({}))

    def test_analytics_contract_accepts_only_structural_fields(self):
        install_product_analytics_contract(product_analytics)
        properties = {"period": "week", "action": "viewed", "state": "active"}
        name, normalized, _ = validate_product_event(
            ProductEventInput(
                event="period_recap",
                properties=properties,
                client_event_id="period-recap-0001",
            )
        )
        self.assertEqual(name, "period_recap")
        self.assertEqual(normalized, properties)

        for private_key in ("title", "author", "pages", "sessions", "chapter", "note"):
            with self.assertRaises(HTTPException):
                validate_product_event(
                    ProductEventInput(
                        event="period_recap",
                        properties={**properties, private_key: "private"},
                        client_event_id=f"period-{private_key}-0001",
                    )
                )


class PeriodRecapFrontendContractTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = (ROOT / "static" / "period-recaps.js").read_text(encoding="utf-8")
        cls.flags = (ROOT / "static" / "feature-flags.js").read_text(encoding="utf-8")
        cls.client = (ROOT / "static" / "product-analytics.js").read_text(encoding="utf-8")

    def test_module_loads_only_behind_flag(self):
        self.assertIn("isEnabled('period_recaps')", self.flags)
        self.assertIn("/static/period-recaps.js", self.flags)
        self.assertNotIn("period-recaps.js", (ROOT / "index.html").read_text(encoding="utf-8"))

    def test_period_navigation_empty_state_and_share_card_exist(self):
        for contract in (
            "data-recap-period=\"week\"",
            "data-recap-period=\"month\"",
            "data-recap-nav=\"older\"",
            "data-recap-nav=\"newer\"",
            "emptyCurrent",
            "emptyPast",
            "canvas.width = 1080",
            "lombada-retrospectiva-",
            "navigator.share",
        ):
            self.assertIn(contract, self.module)

    def test_accessibility_responsive_and_three_locales(self):
        self.assertIn("role=\"tablist\"", self.module)
        self.assertIn("aria-selected", self.module)
        self.assertIn("prefers-reduced-motion:reduce", self.module)
        self.assertIn("theme-dark", self.module)
        self.assertIn("@media(max-width:620px)", self.module)
        for text in (
            "Sua retrospectiva de leitura",
            "Your reading recap",
            "Tu retrospectiva de lectura",
        ):
            self.assertIn(text, self.module)

    def test_analytics_is_structural_and_client_allowlisted(self):
        self.assertIn("period_recap: ['period', 'action', 'state']", self.client)
        start = self.module.index("function track(")
        end = self.module.index("function metric(")
        analytics_block = self.module[start:end].lower()
        for forbidden in ("title", "author", "pages", "sessions", "chapter", "note", "work_key"):
            self.assertNotIn(forbidden, analytics_block)

    def test_router_is_registered_once(self):
        entrypoint = (ROOT / "app_entry.py").read_text(encoding="utf-8")
        self.assertIn("period_recaps_router", entrypoint)
        self.assertIn("period_recaps_router_installed", entrypoint)
        self.assertEqual(entrypoint.count("app.include_router(period_recaps_router)"), 1)


if __name__ == "__main__":
    import unittest

    unittest.main()

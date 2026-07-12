"""Testes das métricas agregadas de ativação e retenção."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from starlette.middleware.sessions import SessionMiddleware

import retention_dashboard
from analytics_models import ProductEvent
from models import Usuario, get_session
from retention_dashboard import calculate_retention_report, router


NOW = datetime(2026, 7, 12, 12, 0, 0)


def event(user_id: int | None, name: str, at: datetime) -> dict:
    return {"user_id": user_id, "event_name": name, "created_at": at}


class RetentionFormulaTest(TestCase):
    def test_funil_wau_activation_and_retention(self):
        u1 = NOW - timedelta(days=40)
        u2 = NOW - timedelta(days=10)
        u3 = NOW - timedelta(days=2)
        events = [
            event(1, "app_opened", u1),
            event(1, "search_submitted", u1 + timedelta(minutes=5)),
            event(1, "book_opened", u1 + timedelta(minutes=10)),
            event(1, "reading_created", u1 + timedelta(hours=2)),
            event(1, "progress_logged", u1 + timedelta(days=1, hours=1)),
            event(1, "progress_logged", u1 + timedelta(days=7, hours=1)),
            event(1, "progress_logged", u1 + timedelta(days=30, hours=1)),
            event(2, "app_opened", u2),
            event(2, "search_submitted", u2 + timedelta(minutes=2)),
            event(3, "app_opened", u3),
            event(3, "reading_created", u3 + timedelta(hours=25)),
            # Evento sem identidade nunca entra em métricas de pessoa.
            event(None, "progress_logged", NOW - timedelta(hours=1)),
        ]

        report = calculate_retention_report(events, now=NOW, days=90)

        self.assertEqual(report["summary"]["wau"], 1)
        self.assertEqual(report["summary"]["cohort_users"], 3)
        self.assertEqual(report["summary"]["activated_24h"], 1)
        self.assertEqual(report["summary"]["activation_24h_pct"], 33.3)
        self.assertEqual(report["summary"]["activated_7d"], 2)
        self.assertEqual(report["summary"]["activation_7d_pct"], 66.7)
        self.assertEqual(report["retention"]["d1"], {"eligible": 3, "retained": 2, "rate_pct": 66.7})
        self.assertEqual(report["retention"]["d7"], {"eligible": 2, "retained": 1, "rate_pct": 50.0})
        self.assertEqual(report["retention"]["d30"], {"eligible": 1, "retained": 1, "rate_pct": 100.0})

        funnel = {row["event"]: row["users"] for row in report["funnel"]}
        self.assertEqual(funnel["app_opened"], 3)
        self.assertEqual(funnel["search_submitted"], 2)
        self.assertEqual(funnel["reading_created"], 2)
        self.assertEqual(funnel["progress_logged"], 1)

    def test_retention_windows_include_start_and_exclude_end(self):
        cohort = NOW - timedelta(days=40)
        events = [
            event(1, "app_opened", cohort),
            event(1, "search_submitted", cohort + timedelta(days=1)),
            event(1, "search_submitted", cohort + timedelta(days=2)),
            event(1, "progress_logged", cohort + timedelta(days=7)),
            event(1, "progress_logged", cohort + timedelta(days=8)),
            event(1, "reading_updated", cohort + timedelta(days=30)),
            event(1, "reading_updated", cohort + timedelta(days=31)),
        ]

        report = calculate_retention_report(events, now=NOW, days=90)

        self.assertEqual(report["retention"]["d1"]["retained"], 1)
        self.assertEqual(report["retention"]["d7"]["retained"], 1)
        self.assertEqual(report["retention"]["d30"]["retained"], 1)

    def test_immature_cohorts_do_not_enter_denominator(self):
        cohort = NOW - timedelta(hours=30)
        report = calculate_retention_report(
            [event(1, "app_opened", cohort), event(1, "search_submitted", cohort + timedelta(hours=25))],
            now=NOW,
            days=7,
        )

        self.assertEqual(report["retention"]["d1"]["eligible"], 0)
        self.assertIsNone(report["retention"]["d1"]["rate_pct"])
        self.assertEqual(report["retention"]["d7"]["eligible"], 0)
        self.assertEqual(report["retention"]["d30"]["eligible"], 0)

    def test_app_opened_alone_is_not_active(self):
        report = calculate_retention_report(
            [event(1, "app_opened", NOW - timedelta(hours=2))],
            now=NOW,
            days=7,
        )
        self.assertEqual(report["summary"]["active_users"], 0)
        self.assertEqual(report["summary"]["wau"], 0)

    def test_invalid_period_is_rejected_by_pure_function(self):
        with self.assertRaisesRegex(ValueError, "período inválido"):
            calculate_retention_report([], now=NOW, days=365)


class RetentionDashboardEndpointTest(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="retention-test-secret", https_only=False)
        app.include_router(router)

        def override_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session

        @app.post("/_test/session/{uid}")
        def set_session(uid: int, request: Request):
            request.session["uid"] = uid
            return {"ok": True}

        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

        with Session(self.engine) as session:
            admin = Usuario(
                handle="retention-admin",
                email="admin@example.test",
                google_sub="admin-google-sub",
                nome="Admin Privado",
            )
            regular = Usuario(
                handle="retention-user",
                email="reader@example.test",
                google_sub="reader-google-sub",
                nome="Pessoa Privada",
            )
            demo = Usuario(handle="retention-demo", is_demo=True)
            session.add(admin)
            session.add(regular)
            session.add(demo)
            session.commit()
            session.refresh(admin)
            session.refresh(regular)
            session.refresh(demo)
            self.admin_id = admin.id
            self.regular_id = regular.id
            self.demo_id = demo.id

            rows = [
                ProductEvent(client_event_id="dash-admin-open", event_name="app_opened", user_id=admin.id, actor_type="connected", created_at=NOW - timedelta(days=3)),
                ProductEvent(client_event_id="dash-admin-search", event_name="search_submitted", user_id=admin.id, actor_type="connected", created_at=NOW - timedelta(days=3) + timedelta(minutes=2)),
                ProductEvent(client_event_id="dash-user-open", event_name="app_opened", user_id=regular.id, actor_type="connected", created_at=NOW - timedelta(days=2)),
                ProductEvent(client_event_id="dash-user-reading", event_name="reading_created", user_id=regular.id, actor_type="connected", created_at=NOW - timedelta(days=2) + timedelta(hours=1)),
                ProductEvent(client_event_id="dash-demo-open", event_name="app_opened", user_id=demo.id, actor_type="anonymous", created_at=NOW - timedelta(days=1)),
                ProductEvent(client_event_id="dash-demo-reading", event_name="reading_created", user_id=demo.id, actor_type="anonymous", created_at=NOW - timedelta(days=1) + timedelta(minutes=5)),
            ]
            session.add_all(rows)
            session.commit()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.engine.dispose()

    def _login(self, uid: int):
        response = self.client.post(f"/_test/session/{uid}")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_is_hidden_when_internal_flag_is_off(self):
        self._login(self.admin_id)
        with patch.dict(os.environ, {"FF_ADMIN_RETENTION_DASHBOARD": "false"}, clear=False), patch.object(
            retention_dashboard, "_ADMIN_EMAILS", {"admin@example.test"}
        ):
            response = self.client.get("/api/admin/retention")
        self.assertEqual(response.status_code, 404)

    def test_dashboard_is_hidden_from_non_admin(self):
        self._login(self.regular_id)
        with patch.dict(os.environ, {"FF_ADMIN_RETENTION_DASHBOARD": "true"}, clear=False), patch.object(
            retention_dashboard, "_ADMIN_EMAILS", {"admin@example.test"}
        ):
            response = self.client.get("/api/admin/retention")
        self.assertEqual(response.status_code, 404)

    def test_admin_receives_only_aggregates_and_demo_is_excluded(self):
        self._login(self.admin_id)
        with patch.dict(os.environ, {"FF_ADMIN_RETENTION_DASHBOARD": "true"}, clear=False), patch.object(
            retention_dashboard, "_ADMIN_EMAILS", {"admin@example.test"}
        ), patch.object(retention_dashboard, "datetime") as mocked_datetime:
            mocked_datetime.utcnow.return_value = NOW
            response = self.client.get("/api/admin/retention?days=7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        payload = response.json()
        self.assertEqual(payload["period_days"], 7)
        self.assertEqual(payload["summary"]["cohort_users"], 2)
        self.assertEqual(payload["summary"]["active_users"], 2)
        serialized = json.dumps(payload).lower()
        for private in (
            "admin@example.test",
            "reader@example.test",
            "retention-admin",
            "retention-user",
            "pessoa privada",
            "user_id",
            "client_event_id",
        ):
            self.assertNotIn(private, serialized)

    def test_admin_html_page_contains_aggregates_only(self):
        self._login(self.admin_id)
        with patch.dict(os.environ, {"FF_ADMIN_RETENTION_DASHBOARD": "true"}, clear=False), patch.object(
            retention_dashboard, "_ADMIN_EMAILS", {"admin@example.test"}
        ), patch.object(retention_dashboard, "datetime") as mocked_datetime:
            mocked_datetime.utcnow.return_value = NOW
            response = self.client.get("/admin/retention?days=30")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Ativação e retenção", response.text)
        self.assertIn("Usuários ativos", response.text)
        self.assertNotIn("admin@example.test", response.text)
        self.assertNotIn("retention-user", response.text)

    def test_invalid_period_is_rejected(self):
        self._login(self.admin_id)
        with patch.dict(os.environ, {"FF_ADMIN_RETENTION_DASHBOARD": "true"}, clear=False), patch.object(
            retention_dashboard, "_ADMIN_EMAILS", {"admin@example.test"}
        ):
            response = self.client.get("/api/admin/retention?days=365")
        self.assertEqual(response.status_code, 422)


class RetentionDashboardContractTest(TestCase):
    def test_entrypoint_registers_dashboard_router_once(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        source = (root / "app_entry.py").read_text(encoding="utf-8")
        self.assertIn("retention_dashboard_router", source)
        self.assertIn("retention_dashboard_router_installed", source)
        self.assertIn("app.include_router(retention_dashboard_router)", source)


if __name__ == "__main__":
    import unittest

    unittest.main()

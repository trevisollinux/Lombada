"""Testes da camada privada e opt-in de eventos de produto."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select
from starlette.middleware.sessions import SessionMiddleware

import product_analytics
from analytics_models import ProductEvent
from models import Usuario, get_session
from product_analytics import purge_product_events, router


ROOT = Path(__file__).resolve().parents[1]


class ProductAnalyticsEndpointTest(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="analytics-test-secret", https_only=False)
        app.include_router(router)

        def override_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session

        @app.post("/_test/session/{uid}")
        def set_session(uid: int, request: Request):
            request.session["uid"] = uid
            return {"ok": True}

        self.app = app
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        product_analytics._RATE_BUCKETS.clear()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.engine.dispose()
        product_analytics._RATE_BUCKETS.clear()

    def _rows(self):
        with Session(self.engine) as session:
            return session.exec(select(ProductEvent).order_by(ProductEvent.id)).all()

    def _event(self, event="app_opened", event_id="event-0001", properties=None):
        return {
            "events": [
                {
                    "event": event,
                    "client_event_id": event_id,
                    "properties": properties or {},
                }
            ]
        }

    def test_flag_off_validates_but_does_not_persist(self):
        with patch.dict(os.environ, {"FF_PRODUCT_ANALYTICS": "false"}, clear=False):
            response = self.client.post(
                "/api/events",
                json=self._event(properties={"source": "web", "locale": "pt-BR", "standalone": False}),
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["disabled"], True)
        self.assertEqual(response.headers["cache-control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(self._rows(), [])

    def test_unknown_event_and_private_property_are_rejected_even_when_disabled(self):
        with patch.dict(os.environ, {"FF_PRODUCT_ANALYTICS": "false"}, clear=False):
            unknown = self.client.post("/api/events", json=self._event(event="secret_event"))
            private = self.client.post(
                "/api/events",
                json=self._event(
                    event="search_submitted",
                    event_id="event-0002",
                    properties={"query": "Crime e Castigo"},
                ),
            )

        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(private.status_code, 422)
        self.assertEqual(self._rows(), [])

    def test_enabled_event_persists_only_allowlisted_structure(self):
        with patch.dict(os.environ, {"FF_PRODUCT_ANALYTICS": "true"}, clear=False):
            response = self.client.post(
                "/api/events",
                json=self._event(
                    event="progress_logged",
                    properties={"source": "diary", "progress_type": "page", "public": False},
                ),
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"accepted": 1, "dropped": 0})
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event_name, "progress_logged")
        self.assertEqual(rows[0].actor_type, "anonymous")
        self.assertIsNone(rows[0].user_id)
        self.assertEqual(
            json.loads(rows[0].properties_json),
            {"progress_type": "page", "public": False, "source": "diary"},
        )

    def test_connected_user_is_linked_without_copying_personal_fields(self):
        with Session(self.engine) as session:
            user = Usuario(
                handle="analytics-connected",
                email="reader@example.test",
                google_sub="google-test-sub",
                nome="Nome Privado",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            uid = user.id

        self.client.post(f"/_test/session/{uid}")
        with patch.dict(os.environ, {"FF_PRODUCT_ANALYTICS": "true"}, clear=False):
            response = self.client.post(
                "/api/events",
                json=self._event(
                    event="profile_connected",
                    properties={"provider": "google", "source": "profile", "success": True},
                ),
            )

        self.assertEqual(response.status_code, 202)
        row = self._rows()[0]
        self.assertEqual(row.user_id, uid)
        self.assertEqual(row.actor_type, "connected")
        serialized = row.properties_json.lower()
        self.assertNotIn("reader@example", serialized)
        self.assertNotIn("nome privado", serialized)
        self.assertNotIn("analytics-connected", serialized)

    def test_demo_user_is_ignored(self):
        with Session(self.engine) as session:
            user = Usuario(handle="analytics-demo", is_demo=True)
            session.add(user)
            session.commit()
            session.refresh(user)
            uid = user.id

        self.client.post(f"/_test/session/{uid}")
        with patch.dict(os.environ, {"FF_PRODUCT_ANALYTICS": "true"}, clear=False):
            response = self.client.post("/api/events", json=self._event())

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["ignored_demo"])
        self.assertEqual(self._rows(), [])

    def test_client_event_id_is_idempotent(self):
        payload = self._event(event_id="same-event-0001")
        with patch.dict(os.environ, {"FF_PRODUCT_ANALYTICS": "true"}, clear=False):
            first = self.client.post("/api/events", json=payload)
            second = self.client.post("/api/events", json=payload)

        self.assertEqual(first.json()["accepted"], 1)
        self.assertEqual(second.json()["accepted"], 0)
        self.assertEqual(second.json()["dropped"], 1)
        self.assertEqual(len(self._rows()), 1)

    def test_rate_limit_rejects_batch_without_persisting(self):
        payload = {
            "events": [
                {"event": "app_opened", "client_event_id": "rate-0001", "properties": {}},
                {"event": "app_opened", "client_event_id": "rate-0002", "properties": {}},
            ]
        }
        with patch.dict(
            os.environ,
            {"FF_PRODUCT_ANALYTICS": "true", "ANALYTICS_RATE_LIMIT_PER_MINUTE": "1"},
            clear=False,
        ):
            response = self.client.post("/api/events", json=payload)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(self._rows(), [])

    def test_retention_is_dry_run_by_default_and_apply_is_batched(self):
        with Session(self.engine) as session:
            session.add(
                ProductEvent(
                    client_event_id="retention-old",
                    event_name="app_opened",
                    actor_type="anonymous",
                    created_at=datetime.utcnow() - timedelta(days=120),
                )
            )
            session.add(
                ProductEvent(
                    client_event_id="retention-new",
                    event_name="app_opened",
                    actor_type="anonymous",
                    created_at=datetime.utcnow() - timedelta(days=2),
                )
            )
            session.commit()

            cutoff = datetime.utcnow() - timedelta(days=90)
            self.assertEqual(purge_product_events(session, before=cutoff), 1)
            self.assertEqual(len(session.exec(select(ProductEvent)).all()), 2)
            self.assertEqual(purge_product_events(session, before=cutoff, apply=True), 1)
            remaining = session.exec(select(ProductEvent)).all()

        self.assertEqual([row.client_event_id for row in remaining], ["retention-new"])


class ProductAnalyticsContractTest(TestCase):
    def test_model_contains_no_raw_personal_or_network_fields(self):
        columns = set(ProductEvent.__table__.columns.keys())
        self.assertEqual(
            columns,
            {
                "id",
                "client_event_id",
                "event_name",
                "user_id",
                "actor_type",
                "properties_json",
                "schema_version",
                "created_at",
            },
        )
        for forbidden in ("email", "handle", "ip", "user_agent", "query", "text"):
            self.assertNotIn(forbidden, columns)

    def test_frontend_client_is_fail_safe_and_loaded_after_flags(self):
        client = (ROOT / "static" / "product-analytics.js").read_text(encoding="utf-8")
        index = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("LombadaFeatures.isEnabled('product_analytics')", client)
        self.assertIn("sanitizeProperties", client)
        self.assertIn("keepalive: true", client)
        self.assertIn("catch (_)", client)
        # carregado junto com a primeira experiência gated, depois do helper
        # de flags e antes do app.js
        self.assertIn("/static/product-analytics.js", index)
        self.assertLess(index.index("/static/feature-flags.js"), index.index("/static/product-analytics.js"))
        self.assertLess(index.index("/static/product-analytics.js"), index.index("/static/app.js"))

    def test_entrypoint_registers_analytics_router_once(self):
        source = (ROOT / "app_entry.py").read_text(encoding="utf-8")
        self.assertIn("product_analytics_router", source)
        self.assertIn("product_analytics_router_installed", source)
        self.assertIn("app.include_router(product_analytics_router)", source)


if __name__ == "__main__":
    import unittest

    unittest.main()

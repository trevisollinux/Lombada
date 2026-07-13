"""Testes das reações literárias em críticas públicas."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import product_analytics
from feature_flags import feature_enabled, public_feature_flags
from literary_reactions import (
    LiteraryReaction,
    LiteraryReactionInboxState,
    batch_reaction_summaries,
    grouped_reaction_inbox,
    install_product_analytics_contract,
    mark_reaction_inbox_seen,
    remove_literary_reaction,
    set_literary_reaction,
)
from models import Edicao, Leitura, Obra, Usuario
from product_analytics import ProductEventInput, validate_product_event


ROOT = Path(__file__).resolve().parents[1]


class LiteraryReactionDatabaseTest(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            owner = Usuario(handle="autora", nome="Autora", google_sub="google-owner")
            reader = Usuario(handle="leitora", nome="Leitora", google_sub="google-reader")
            other = Usuario(handle="outro", nome="Outro", google_sub="google-other")
            anonymous = Usuario(handle="anonimo", nome="Anônimo")
            demo = Usuario(handle="demo", nome="Demo", google_sub="google-demo", is_demo=True)
            session.add(owner)
            session.add(reader)
            session.add(other)
            session.add(anonymous)
            session.add(demo)
            session.commit()
            for user in (owner, reader, other, anonymous, demo):
                session.refresh(user)
            self.owner_id = owner.id
            self.reader_id = reader.id
            self.other_id = other.id
            self.anonymous_id = anonymous.id
            self.demo_id = demo.id

            work = Obra(ol_work_key="work:reaction", titulo="Livro público", autor="Autora do livro")
            session.add(work)
            session.commit()
            session.refresh(work)
            edition = Edicao(
                obra_id=work.id,
                ol_edition_key="edition:reaction",
                capa_url="https://covers.example/reaction.jpg",
            )
            session.add(edition)
            session.commit()
            session.refresh(edition)

            public_review = Leitura(
                usuario_id=owner.id,
                edicao_id=edition.id,
                status="Lido",
                relato="Uma crítica pública que não deve aparecer no inbox.",
                publico=True,
            )
            private_review = Leitura(
                usuario_id=owner.id,
                edicao_id=edition.id,
                status="Lido",
                relato="Crítica privada",
                publico=False,
            )
            empty_review = Leitura(
                usuario_id=owner.id,
                edicao_id=edition.id,
                status="Lido",
                relato="   ",
                publico=True,
            )
            reader_review = Leitura(
                usuario_id=reader.id,
                edicao_id=edition.id,
                status="Lido",
                relato="Crítica da própria leitora",
                publico=True,
            )
            demo_review = Leitura(
                usuario_id=demo.id,
                edicao_id=edition.id,
                status="Lido",
                relato="Crítica demo",
                publico=True,
                is_demo=True,
            )
            session.add(public_review)
            session.add(private_review)
            session.add(empty_review)
            session.add(reader_review)
            session.add(demo_review)
            session.commit()
            for review in (public_review, private_review, empty_review, reader_review, demo_review):
                session.refresh(review)
            self.public_review_id = public_review.id
            self.private_review_id = private_review.id
            self.empty_review_id = empty_review.id
            self.reader_review_id = reader_review.id
            self.demo_review_id = demo_review.id

    def test_set_change_and_remove_use_one_row(self):
        with Session(self.engine) as session:
            reader = session.get(Usuario, self.reader_id)
            summary, action = set_literary_reaction(
                session, reader, self.public_review_id, "want_to_read"
            )
            self.assertEqual(action, "set")
            self.assertEqual(summary["mine"], "want_to_read")
            self.assertEqual(summary["total"], 1)

            summary, action = set_literary_reaction(
                session, reader, self.public_review_id, "moved_me"
            )
            self.assertEqual(action, "changed")
            self.assertEqual(summary["mine"], "moved_me")
            self.assertEqual(summary["counts"]["want_to_read"], 0)
            self.assertEqual(summary["counts"]["moved_me"], 1)
            rows = session.exec(select(LiteraryReaction)).all()
            self.assertEqual(len(rows), 1)

            summary, removed = remove_literary_reaction(
                session, reader, self.public_review_id
            )
            self.assertTrue(removed)
            self.assertIsNone(summary["mine"])
            self.assertEqual(summary["total"], 0)
            self.assertEqual(session.exec(select(LiteraryReaction)).all(), [])

            _, removed_again = remove_literary_reaction(
                session, reader, self.public_review_id
            )
            self.assertFalse(removed_again)

    def test_aggregate_counts_and_viewer_state_are_correct(self):
        with Session(self.engine) as session:
            reader = session.get(Usuario, self.reader_id)
            other = session.get(Usuario, self.other_id)
            owner = session.get(Usuario, self.owner_id)
            set_literary_reaction(session, reader, self.public_review_id, "good_reading")
            set_literary_reaction(session, other, self.public_review_id, "moved_me")

            reader_data = batch_reaction_summaries(
                session, reader, [self.public_review_id, self.private_review_id]
            )
            self.assertEqual(list(reader_data), [str(self.public_review_id)])
            summary = reader_data[str(self.public_review_id)]
            self.assertEqual(summary["total"], 2)
            self.assertEqual(summary["counts"]["good_reading"], 1)
            self.assertEqual(summary["counts"]["moved_me"], 1)
            self.assertEqual(summary["mine"], "good_reading")
            self.assertTrue(summary["can_react"])

            owner_summary = batch_reaction_summaries(
                session, owner, [self.public_review_id]
            )[str(self.public_review_id)]
            self.assertTrue(owner_summary["is_owner"])
            self.assertFalse(owner_summary["can_react"])
            self.assertNotIn("users", owner_summary)
            self.assertNotIn("actors", owner_summary)

    def test_private_empty_own_anonymous_and_demo_are_rejected(self):
        with Session(self.engine) as session:
            reader = session.get(Usuario, self.reader_id)
            owner = session.get(Usuario, self.owner_id)
            anonymous = session.get(Usuario, self.anonymous_id)
            for review_id in (self.private_review_id, self.empty_review_id, self.demo_review_id):
                with self.assertRaises(HTTPException) as raised:
                    set_literary_reaction(session, reader, review_id, "good_reading")
                self.assertEqual(raised.exception.status_code, 404)

            with self.assertRaises(HTTPException) as own:
                set_literary_reaction(session, owner, self.public_review_id, "moved_me")
            self.assertEqual(own.exception.status_code, 409)

            with self.assertRaises(HTTPException) as disconnected:
                set_literary_reaction(
                    session, anonymous, self.public_review_id, "want_to_read"
                )
            self.assertEqual(disconnected.exception.status_code, 401)

            with self.assertRaises(HTTPException) as invalid:
                set_literary_reaction(session, reader, self.public_review_id, "love")
            self.assertEqual(invalid.exception.status_code, 422)

    def test_inbox_is_grouped_and_contains_no_review_text_or_reactor_identity(self):
        with Session(self.engine) as session:
            reader = session.get(Usuario, self.reader_id)
            other = session.get(Usuario, self.other_id)
            owner = session.get(Usuario, self.owner_id)
            set_literary_reaction(session, reader, self.public_review_id, "want_to_read")
            set_literary_reaction(session, other, self.public_review_id, "good_reading")

            inbox = grouped_reaction_inbox(session, owner)
            self.assertTrue(inbox["grouped"])
            self.assertFalse(inbox["individual_notifications"])
            self.assertEqual(inbox["unread_groups"], 1)
            self.assertEqual(len(inbox["groups"]), 1)
            group = inbox["groups"][0]
            self.assertEqual(group["total"], 2)
            self.assertEqual(group["title"], "Livro público")
            self.assertTrue(group["unread"])
            serialized = str(inbox).lower()
            self.assertNotIn("uma crítica pública", serialized)
            self.assertNotIn("google-reader", serialized)
            self.assertNotIn("leitora", serialized)
            self.assertNotIn("ator", serialized)

            mark_reaction_inbox_seen(session, owner)
            seen = grouped_reaction_inbox(session, owner)
            self.assertEqual(seen["unread_groups"], 0)
            self.assertFalse(seen["groups"][0]["unread"])
            states = session.exec(select(LiteraryReactionInboxState)).all()
            self.assertEqual(len(states), 1)


class LiteraryReactionFlagAndFrontendTest(TestCase):
    def test_flag_is_public_and_off_by_default(self):
        self.assertFalse(feature_enabled("literary_reactions", {}))
        self.assertTrue(
            feature_enabled("literary_reactions", {"FF_LITERARY_REACTIONS": "true"})
        )
        self.assertIn("literary_reactions", public_feature_flags({}))

    def test_frontend_loads_only_behind_flag_and_uses_batch_endpoint(self):
        flags = (ROOT / "static" / "feature-flags.js").read_text(encoding="utf-8")
        source = (ROOT / "static" / "literary-reactions.js").read_text(encoding="utf-8")
        self.assertIn("isEnabled('literary_reactions')", flags)
        self.assertIn("/static/literary-reactions.js", flags)
        self.assertIn("/api/reviews/reactions?ids=", source)
        self.assertIn("data-like-btn", source)
        self.assertNotIn("literary-reactions.js", (ROOT / "index.html").read_text(encoding="utf-8"))

    def test_three_reactions_copy_accessibility_and_mobile_exist(self):
        source = (ROOT / "static" / "literary-reactions.js").read_text(encoding="utf-8")
        for key in ("want_to_read", "moved_me", "good_reading"):
            self.assertIn(key, source)
        for text in (
            "Quero ler também", "Esse me marcou", "Boa leitura",
            "I want to read it too", "This one stayed with me", "Good reading",
            "Quiero leerlo también", "Este me marcó", "Buena lectura",
        ):
            self.assertIn(text, source)
        self.assertIn("aria-pressed", source)
        self.assertIn("aria-busy", source)
        self.assertIn("@media(max-width:520px)", source)
        self.assertIn("prefers-reduced-motion:reduce", source)
        self.assertIn("theme-dark", source)

    def test_feed_remains_finite_and_notifications_are_grouped(self):
        source = (ROOT / "static" / "literary-reactions.js").read_text(encoding="utf-8")
        backend = (ROOT / "literary_reactions.py").read_text(encoding="utf-8")
        self.assertNotIn("IntersectionObserver", source)
        self.assertNotIn("addEventListener('scroll'", source)
        self.assertNotIn("loadMore", source)
        self.assertIn('"grouped": True', backend)
        self.assertIn('"individual_notifications": False', backend)
        self.assertNotIn("Notificacao(", backend)

    def test_router_is_registered_once(self):
        entrypoint = (ROOT / "app_entry.py").read_text(encoding="utf-8")
        self.assertIn("literary_reactions_router", entrypoint)
        self.assertIn("literary_reactions_router_installed", entrypoint)
        self.assertEqual(entrypoint.count("app.include_router(literary_reactions_router)"), 1)


class LiteraryReactionAnalyticsTest(TestCase):
    def test_backend_accepts_only_structural_properties(self):
        install_product_analytics_contract(product_analytics)
        properties = {
            "source": "feed",
            "action": "set",
            "reaction_type": "want_to_read",
        }
        name, normalized, _ = validate_product_event(
            ProductEventInput(
                event="literary_reaction",
                properties=properties,
                client_event_id="literary-reaction-0001",
            )
        )
        self.assertEqual(name, "literary_reaction")
        self.assertEqual(normalized, properties)

        for private_key in (
            "title", "author", "review", "relato", "isbn", "reading_id", "actor"
        ):
            with self.assertRaises(HTTPException):
                validate_product_event(
                    ProductEventInput(
                        event="literary_reaction",
                        properties={**properties, private_key: "private"},
                        client_event_id=f"literary-{private_key}-0001",
                    )
                )

    def test_client_allowlist_has_no_reading_content(self):
        client = (ROOT / "static" / "product-analytics.js").read_text(encoding="utf-8")
        source = (ROOT / "static" / "literary-reactions.js").read_text(encoding="utf-8")
        self.assertIn(
            "literary_reaction: ['source', 'action', 'reaction_type']",
            client,
        )
        start = source.index("function track(")
        end = source.index("function requestConnection")
        block = source[start:end].lower()
        for forbidden in ("title", "author", "review", "relato", "isbn", "reading_id", "actor"):
            self.assertNotIn(forbidden, block)


if __name__ == "__main__":
    import unittest

    unittest.main()

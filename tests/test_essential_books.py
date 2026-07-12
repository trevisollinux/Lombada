"""Testes dos Quatro Essenciais sem acessar o banco de produção."""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import product_analytics
from essential_books import (
    UserEssentialBook,
    inject_public_essentials,
    install_product_analytics_contract,
    replace_essential_books,
)
from feature_flags import feature_enabled, public_feature_flags
from models import Edicao, Leitura, Obra, Usuario
from product_analytics import ProductEventInput, validate_product_event


ROOT = Path(__file__).resolve().parents[1]


class EssentialBooksDatabaseTest(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            self.user = Usuario(handle="leitora", nome="Leitora", google_sub="google-1")
            self.other = Usuario(handle="outro", nome="Outro", google_sub="google-2")
            session.add(self.user)
            session.add(self.other)
            session.commit()
            session.refresh(self.user)
            session.refresh(self.other)
            self.user_id = self.user.id
            self.other_id = self.other.id

            self.keys = []
            for index in range(1, 6):
                obra = Obra(
                    ol_work_key=f"work:{index}",
                    titulo=f"Livro {index}",
                    autor=f"Autor {index}",
                )
                session.add(obra)
                session.commit()
                session.refresh(obra)
                edicao = Edicao(
                    obra_id=obra.id,
                    ol_edition_key=f"edition:{index}",
                    capa_url=f"https://covers.example/{index}.jpg",
                )
                session.add(edicao)
                session.commit()
                session.refresh(edicao)
                owner_id = self.user_id if index <= 4 else self.other_id
                session.add(
                    Leitura(
                        usuario_id=owner_id,
                        edicao_id=edicao.id,
                        status="Lido",
                    )
                )
                session.commit()
                self.keys.append(obra.ol_work_key)

    def test_selection_persists_order_and_replaces_previous_rows(self):
        with Session(self.engine) as session:
            user = session.get(Usuario, self.user_id)
            books = replace_essential_books(
                session,
                user,
                [self.keys[2], self.keys[0], self.keys[1]],
            )
            self.assertEqual(
                [book["work_key"] for book in books],
                [self.keys[2], self.keys[0], self.keys[1]],
            )
            self.assertEqual([book["position"] for book in books], [1, 2, 3])

            books = replace_essential_books(session, user, [self.keys[3]])
            self.assertEqual([book["work_key"] for book in books], [self.keys[3]])
            rows = session.query(UserEssentialBook).all()
            self.assertEqual(len(rows), 1)

    def test_clear_is_allowed(self):
        with Session(self.engine) as session:
            user = session.get(Usuario, self.user_id)
            replace_essential_books(session, user, [self.keys[0]])
            self.assertEqual(replace_essential_books(session, user, []), [])

    def test_fifth_duplicate_and_foreign_shelf_book_are_rejected(self):
        with Session(self.engine) as session:
            user = session.get(Usuario, self.user_id)
            with self.assertRaises(HTTPException) as fifth:
                replace_essential_books(session, user, self.keys)
            self.assertEqual(fifth.exception.status_code, 422)

            with self.assertRaises(HTTPException) as duplicate:
                replace_essential_books(session, user, [self.keys[0], self.keys[0]])
            self.assertEqual(duplicate.exception.status_code, 422)

            with self.assertRaises(HTTPException) as foreign:
                replace_essential_books(session, user, [self.keys[4]])
            self.assertEqual(foreign.exception.status_code, 422)
            self.assertIn("estante", str(foreign.exception.detail))

    def test_google_connection_is_required_to_save(self):
        with Session(self.engine) as session:
            anonymous = Usuario(handle="anonimo")
            session.add(anonymous)
            session.commit()
            session.refresh(anonymous)
            with self.assertRaises(HTTPException) as raised:
                replace_essential_books(session, anonymous, [])
            self.assertEqual(raised.exception.status_code, 403)


class EssentialBooksFlagAndProfileTest(TestCase):
    def test_existing_public_flag_is_off_by_default(self):
        self.assertFalse(feature_enabled("favorite_books", {}))
        self.assertTrue(feature_enabled("favorite_books", {"FF_FAVORITE_BOOKS": "true"}))
        self.assertIn("favorite_books", public_feature_flags({}))

    def test_public_profile_injection_is_explicit_and_ordered(self):
        html = '<html><head><style>.x{}</style></head><body><section class="section"><h2>Lendo agora</h2></section></body></html>'
        books = [
            {"work_key": "w:2", "title": "Segundo", "author": "B", "cover_url": "", "position": 1},
            {"work_key": "w:1", "title": "Primeiro", "author": "A", "cover_url": "", "position": 2},
        ]
        rendered = inject_public_essentials(html, books)
        self.assertIn("Quatro essenciais", rendered)
        self.assertLess(rendered.index("Segundo"), rendered.index("Primeiro"))
        self.assertLess(rendered.index("Quatro essenciais"), rendered.index("Lendo agora"))
        self.assertIn("essential-rank", rendered)

    def test_empty_selection_does_not_change_public_profile(self):
        html = "<html><body>perfil</body></html>"
        self.assertEqual(inject_public_essentials(html, []), html)


class EssentialBooksFrontendContractTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = (ROOT / "static" / "essential-books.js").read_text(encoding="utf-8")
        cls.flags = (ROOT / "static" / "feature-flags.js").read_text(encoding="utf-8")

    def test_module_loads_only_behind_flag(self):
        self.assertIn("isEnabled('favorite_books')", self.flags)
        self.assertIn("/static/essential-books.js", self.flags)
        self.assertIn("loadScriptOnce", self.flags)
        self.assertNotIn("essential-books.js", (ROOT / "index.html").read_text(encoding="utf-8"))

    def test_editor_reuses_shelf_and_enforces_four(self):
        self.assertIn("Array.isArray(prateleira)", self.module)
        self.assertIn("const MAX_BOOKS = 4", self.module)
        self.assertIn("selectedKeys.length >= MAX_BOOKS", self.module)
        self.assertIn("data-move", self.module)
        self.assertIn("data-remove", self.module)
        self.assertIn("work_keys: selectedKeys", self.module)

    def test_card_and_accessibility_contracts_exist(self):
        self.assertIn("canvas.width = 1080", self.module)
        self.assertIn("lombada-quatro-essenciais.png", self.module)
        self.assertIn("role=\"dialog\"", self.module)
        self.assertIn("aria-modal=\"true\"", self.module)
        self.assertIn("prefers-reduced-motion:reduce", self.module)
        self.assertIn("theme-dark", self.module)

    def test_copy_is_available_in_three_locales(self):
        for text in ("Quatro essenciais", "Four essentials", "Cuatro esenciales"):
            self.assertIn(text, self.module)

    def test_analytics_contains_only_structural_fields(self):
        self.assertIn("event: 'essential_books'", self.module)
        self.assertIn("properties: {source: 'profile', action, completion", self.module)
        analytics_block = self.module[self.module.index("function track("):self.module.index("function coverMarkup")]
        for forbidden in ("title", "author", "isbn", "work_key", "position", "email"):
            self.assertNotIn(forbidden, analytics_block.lower())


class EssentialBooksAnalyticsContractTest(TestCase):
    def test_backend_contract_accepts_only_action_and_completion(self):
        install_product_analytics_contract(product_analytics)
        properties = {"source": "profile", "action": "saved", "completion": "complete"}
        name, normalized, _ = validate_product_event(
            ProductEventInput(
                event="essential_books",
                properties=properties,
                client_event_id="essential-books-0001",
            )
        )
        self.assertEqual(name, "essential_books")
        self.assertEqual(normalized, properties)

        for private_key in ("title", "author", "isbn", "work_key", "position"):
            with self.assertRaises(HTTPException):
                validate_product_event(
                    ProductEventInput(
                        event="essential_books",
                        properties={**properties, private_key: "private"},
                        client_event_id=f"essential-{private_key}-0001",
                    )
                )


if __name__ == "__main__":
    import unittest

    unittest.main()

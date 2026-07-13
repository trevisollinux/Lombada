"""Regressão: reações não podem bloquear exclusão de leitura ou usuário."""
from unittest import TestCase

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from literary_reaction_cascade import install_literary_reaction_cascades
from literary_reactions import LiteraryReaction, LiteraryReactionInboxState
from models import Edicao, Leitura, Obra, Usuario


class LiteraryReactionCascadeTest(TestCase):
    def setUp(self):
        install_literary_reaction_cascades()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def _fixture(self, session: Session):
        owner = Usuario(handle="cascade-owner", google_sub="cascade-owner")
        reactor = Usuario(handle="cascade-reactor", google_sub="cascade-reactor")
        session.add(owner)
        session.add(reactor)
        session.commit()
        session.refresh(owner)
        session.refresh(reactor)
        work = Obra(ol_work_key="work:cascade", titulo="Livro")
        session.add(work)
        session.commit()
        session.refresh(work)
        edition = Edicao(obra_id=work.id, ol_edition_key="edition:cascade")
        session.add(edition)
        session.commit()
        session.refresh(edition)
        reading = Leitura(
            usuario_id=owner.id,
            edicao_id=edition.id,
            publico=True,
            relato="Crítica pública",
        )
        session.add(reading)
        session.commit()
        session.refresh(reading)
        session.add(
            LiteraryReaction(
                leitura_id=reading.id,
                usuario_id=reactor.id,
                reaction_type="good_reading",
            )
        )
        session.add(LiteraryReactionInboxState(usuario_id=reactor.id))
        session.commit()
        return owner, reactor, reading

    def test_deleting_reading_removes_reactions_in_same_transaction(self):
        with Session(self.engine) as session:
            _, _, reading = self._fixture(session)
            session.delete(reading)
            session.commit()
            self.assertEqual(session.exec(select(LiteraryReaction)).all(), [])

    def test_deleting_reactor_removes_reaction_and_inbox_state(self):
        with Session(self.engine) as session:
            _, reactor, _ = self._fixture(session)
            session.delete(reactor)
            session.commit()
            self.assertEqual(session.exec(select(LiteraryReaction)).all(), [])
            self.assertEqual(session.exec(select(LiteraryReactionInboxState)).all(), [])


if __name__ == "__main__":
    import unittest

    unittest.main()

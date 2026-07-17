"""Merge de conta anônima → conta Google no callback do OAuth.

O bug em produção: o callback migrava só parte das tabelas que referenciam
usuario antes de deletar o anônimo. Qualquer linha esquecida (ProductEvent
de analytics era a mais comum) violava FK no DELETE, caía no except e o
usuário via "não foi possível conectar sua conta".
"""

import unittest
from datetime import datetime

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

# importa todos os módulos que definem tabelas para popular o metadata
import analytics_models  # noqa: F401
import essential_books
import literary_reactions
import models
from analytics_models import ProductEvent
from auth import _merge_usuario_orfao
from essential_books import UserEssentialBook
from literary_reactions import LiteraryReaction, LiteraryReactionInboxState
from models import (
    Edicao,
    Follow,
    Leitura,
    Notificacao,
    Obra,
    ProfileReport,
    ReadingJournalEntry,
    ReviewComment,
    ReviewLike,
    TextoUsuario,
    UserEdition,
    UserReadingStatus,
    Usuario,
)

# Toda coluna com FK para usuario.id precisa estar aqui E ser tratada em
# _merge_usuario_orfao (ou nos helpers por leitura). Se este teste falhar
# com uma tabela nova, estenda o merge em auth.py antes de adicioná-la.
COBERTAS_PELO_MERGE = {
    ("leitura", "usuario_id"),
    ("readingjournalentry", "usuario_id"),
    ("useredition", "usuario_id"),
    ("catalogsuggestion", "user_id"),
    ("reviewlike", "usuario_id"),
    ("savedreview", "usuario_id"),
    ("reviewreport", "usuario_id"),
    ("follow", "follower_id"),
    ("follow", "following_id"),
    ("userreadingstatus", "usuario_id"),
    ("textousuario", "usuario_id"),
    ("profilereport", "target_id"),
    ("profilereport", "reporter_id"),
    ("notificacao", "usuario_id"),
    ("notificacao", "ator_id"),
    ("reviewcomment", "usuario_id"),
    ("productevent", "user_id"),
    ("user_essential_book", "usuario_id"),
    ("literary_reaction", "usuario_id"),
    ("literary_reaction_inbox_state", "usuario_id"),
}


def _colunas_com_fk_para_usuario() -> set[tuple[str, str]]:
    encontradas = set()
    for table in SQLModel.metadata.tables.values():
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == "usuario":
                    encontradas.add((table.name, column.name))
    return encontradas


class CoberturaDoMergeTest(unittest.TestCase):
    def test_toda_fk_para_usuario_esta_coberta_pelo_merge(self):
        """Sentinela: tabela nova com FK para usuario exige estender o merge.

        Se esta asserção falhar, o login Google com merge de conta anônima
        vai quebrar em produção (FK violada no DELETE do usuário órfão).
        Trate a tabela nova em auth._merge_usuario_orfao e adicione o par
        (tabela, coluna) em COBERTAS_PELO_MERGE.
        """
        encontradas = _colunas_com_fk_para_usuario()
        faltando = encontradas - COBERTAS_PELO_MERGE
        self.assertFalse(
            faltando,
            f"FKs para usuario sem tratamento no merge de contas: {sorted(faltando)}",
        )
        sobrando = COBERTAS_PELO_MERGE - encontradas
        self.assertFalse(
            sobrando,
            f"Entradas obsoletas em COBERTAS_PELO_MERGE: {sorted(sobrando)}",
        )


class MergeUsuarioOrfaoTest(unittest.TestCase):
    def setUp(self):
        # FKs ligadas no SQLite para reproduzir o comportamento do Postgres
        self.engine = create_engine("sqlite://")

        @event.listens_for(self.engine, "connect")
        def _fk_on(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        SQLModel.metadata.create_all(self.engine)

    def _seed(self, s: Session):
        anon = Usuario(handle="anon-123")
        conta = Usuario(handle="leitor", google_sub="sub-google", email="leitor@x.com")
        terceiro = Usuario(handle="terceiro")
        s.add(anon); s.add(conta); s.add(terceiro); s.commit()
        s.refresh(anon); s.refresh(conta); s.refresh(terceiro)

        obra = Obra(ol_work_key="OL1W", titulo="Obra")
        s.add(obra); s.commit(); s.refresh(obra)
        edicao = Edicao(obra_id=obra.id)
        edicao2 = Edicao(obra_id=obra.id)
        s.add(edicao); s.add(edicao2); s.commit()
        s.refresh(edicao); s.refresh(edicao2)

        # leitura duplicada (mesma edição nas duas contas) e leitura só do anônimo
        leitura_anon_dup = Leitura(edicao_id=edicao.id, usuario_id=anon.id, relato="do anon")
        leitura_conta = Leitura(edicao_id=edicao.id, usuario_id=conta.id)
        leitura_anon = Leitura(edicao_id=edicao2.id, usuario_id=anon.id)
        leitura_terceiro = Leitura(edicao_id=edicao2.id, usuario_id=terceiro.id, publico=True)
        for l in (leitura_anon_dup, leitura_conta, leitura_anon, leitura_terceiro):
            s.add(l)
        s.commit()
        for l in (leitura_anon_dup, leitura_conta, leitura_anon, leitura_terceiro):
            s.refresh(l)

        # uma linha em CADA tabela que referencia o usuário anônimo
        s.add(ReadingJournalEntry(leitura_id=leitura_anon.id, usuario_id=anon.id))
        s.add(UserEdition(usuario_id=anon.id, edicao_id=edicao2.id, tenho=True))
        s.add(ReviewLike(leitura_id=leitura_terceiro.id, usuario_id=anon.id))
        s.add(Follow(follower_id=anon.id, following_id=terceiro.id))
        s.add(UserReadingStatus(usuario_id=anon.id, nome="Relendo"))
        s.add(TextoUsuario(usuario_id=anon.id, titulo="Ensaio", conteudo="…"))
        s.add(ProfileReport(target_id=terceiro.id, reporter_id=anon.id, motivo="spam"))
        s.add(Notificacao(usuario_id=anon.id, ator_id=terceiro.id, tipo="follow"))
        s.add(ReviewComment(leitura_id=leitura_terceiro.id, usuario_id=anon.id, texto="oi"))
        s.add(ProductEvent(client_event_id="evt-1", event_name="page_view", user_id=anon.id))
        s.add(UserEssentialBook(usuario_id=anon.id, obra_id=obra.id, position=1))
        s.add(LiteraryReaction(
            leitura_id=leitura_terceiro.id, usuario_id=anon.id, reaction_type="moved_me",
        ))
        s.add(LiteraryReactionInboxState(usuario_id=anon.id, seen_at=datetime.utcnow()))
        # interações de terceiros presas à leitura duplicada que será apagada
        s.add(ReviewComment(leitura_id=leitura_anon_dup.id, usuario_id=terceiro.id, texto="!"))
        s.add(LiteraryReaction(
            leitura_id=leitura_anon_dup.id, usuario_id=terceiro.id, reaction_type="good_reading",
        ))
        s.add(Notificacao(usuario_id=anon.id, ator_id=terceiro.id, tipo="like",
                          leitura_id=leitura_anon_dup.id))
        s.commit()
        return anon, conta, terceiro

    def test_merge_migra_tudo_e_permite_deletar_o_anonimo(self):
        """Reproduz a sequência exata do callback: merge + delete + commit."""
        with Session(self.engine) as s:
            anon, conta, _ = self._seed(s)

            _merge_usuario_orfao(s, anon.id, conta.id)
            s.delete(s.get(Usuario, anon.id))
            s.commit()  # sem a correção: IntegrityError (FK) aqui

            self.assertIsNone(s.get(Usuario, anon.id))
            # amostras: cada tipo de vínculo mudou de dono
            self.assertEqual(
                s.exec(select(ProductEvent).where(ProductEvent.user_id == conta.id)).first().client_event_id,
                "evt-1",
            )
            self.assertIsNotNone(
                s.exec(select(TextoUsuario).where(TextoUsuario.usuario_id == conta.id)).first()
            )
            self.assertIsNotNone(
                s.exec(select(UserEssentialBook).where(UserEssentialBook.usuario_id == conta.id)).first()
            )
            self.assertIsNotNone(
                s.exec(select(LiteraryReactionInboxState).where(
                    LiteraryReactionInboxState.usuario_id == conta.id
                )).first()
            )
            self.assertIsNotNone(
                s.exec(select(UserReadingStatus).where(
                    UserReadingStatus.usuario_id == conta.id,
                    UserReadingStatus.nome == "Relendo",
                )).first()
            )
            # leituras: a duplicada foi consolidada, a exclusiva migrou
            leituras_conta = s.exec(select(Leitura).where(Leitura.usuario_id == conta.id)).all()
            self.assertEqual(len(leituras_conta), 2)

    def test_merge_deduplica_vinculos_ja_existentes_no_destino(self):
        with Session(self.engine) as s:
            anon, conta, terceiro = self._seed(s)
            # destino já tem os mesmos vínculos únicos
            s.add(UserReadingStatus(usuario_id=conta.id, nome="Relendo"))
            s.add(LiteraryReactionInboxState(usuario_id=conta.id, seen_at=datetime.utcnow()))
            s.add(UserEssentialBook(usuario_id=conta.id,
                                    obra_id=s.exec(select(Obra)).first().id, position=1))
            s.commit()

            _merge_usuario_orfao(s, anon.id, conta.id)
            s.delete(s.get(Usuario, anon.id))
            s.commit()

            self.assertEqual(
                len(s.exec(select(UserReadingStatus).where(
                    UserReadingStatus.usuario_id == conta.id
                )).all()),
                1,
            )
            self.assertEqual(
                len(s.exec(select(LiteraryReactionInboxState).where(
                    LiteraryReactionInboxState.usuario_id == conta.id
                )).all()),
                1,
            )
            self.assertEqual(
                len(s.exec(select(UserEssentialBook).where(
                    UserEssentialBook.usuario_id == conta.id
                )).all()),
                1,
            )


if __name__ == "__main__":
    unittest.main()

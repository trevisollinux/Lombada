"""Limpeza ORM das tabelas aditivas de reação.

Os modelos históricos usam chaves estrangeiras sem ON DELETE CASCADE. Para não
mudar constraints existentes nem criar migration destrutiva, a exclusão ORM de
uma leitura remove primeiro as reações relacionadas na mesma transação.
"""
from __future__ import annotations

from sqlalchemy import event

from literary_reactions import LiteraryReaction, LiteraryReactionInboxState
from models import Leitura, Usuario


_installed = False


def _delete_reading_reactions(_mapper, connection, target: Leitura) -> None:
    if target.id is None:
        return
    connection.execute(
        LiteraryReaction.__table__.delete().where(
            LiteraryReaction.leitura_id == target.id
        )
    )


def _delete_user_reaction_state(_mapper, connection, target: Usuario) -> None:
    if target.id is None:
        return
    connection.execute(
        LiteraryReaction.__table__.delete().where(
            LiteraryReaction.usuario_id == target.id
        )
    )
    connection.execute(
        LiteraryReactionInboxState.__table__.delete().where(
            LiteraryReactionInboxState.usuario_id == target.id
        )
    )


def install_literary_reaction_cascades() -> None:
    global _installed
    if _installed:
        return
    event.listen(Leitura, "before_delete", _delete_reading_reactions)
    event.listen(Usuario, "before_delete", _delete_user_reaction_state)
    _installed = True

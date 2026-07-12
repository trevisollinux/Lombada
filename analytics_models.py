"""Modelo aditivo de eventos de produto do Lombada.

Importado pelo router de analytics antes do lifespan executar ``create_all``.
Nenhum conteúdo literário ou dado pessoal textual deve ser armazenado aqui.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class ProductEvent(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("client_event_id", name="uq_productevent_client_event_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    client_event_id: str = Field(index=True)
    event_name: str = Field(index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="usuario.id", index=True)
    actor_type: str = Field(default="anonymous", index=True)
    properties_json: str = Field(default="{}")
    schema_version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

"""Importa dados de catálogo locais para o banco em DATABASE_URL.

Seguro para produção: cria/migra tabelas ausentes, não apaga dados e não usa
serviços externos. O import é idempotente e reaproveita obras/edições por chaves
estáveis antes de criar registros novos.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CATALOG_PATH = ROOT / "data" / "catalog_seed.json"
MAIN_TABLES = [
    "usuario", "obra", "edicao", "leitura", "reviewlike", "reviewcomment",
    "reviewreport", "savedreview", "buscacache", "catalogsuggestion",
    "useredition", "edicaocapitulo",
]


@dataclass
class ImportStats:
    obras_created: int = 0
    obras_existing: int = 0
    edicoes_created: int = 0
    edicoes_existing: int = 0


def _require_database_url() -> None:
    if not os.getenv("DATABASE_URL", "").strip():
        raise SystemExit(
            "DATABASE_URL não definido. No Railway, rode este comando no ambiente "
            "do serviço para usar somente a variável DATABASE_URL já configurada."
        )


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_catalog() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        raise SystemExit(f"Dataset local não encontrado: {CATALOG_PATH}")
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Dataset local inválido: esperado array JSON em {CATALOG_PATH}")
    return [item for item in data if isinstance(item, dict)]


def _create_and_migrate() -> None:
    from sqlmodel import SQLModel
    from models import engine, migrar

    SQLModel.metadata.create_all(engine)
    migrar()


def _table_exists(inspector, table: str) -> bool:
    return table in set(inspector.get_table_names())


def _scalar_count(session, model) -> int:
    from sqlmodel import select
    from sqlalchemy import func

    return int(session.exec(select(func.count()).select_from(model)).one() or 0)


def _distinct_count(session, column) -> int:
    from sqlmodel import select
    from sqlalchemy import func

    return int(session.exec(select(func.count(func.distinct(column))).where(column != "")).one() or 0)


def _print_table_report() -> None:
    from sqlalchemy import inspect
    from sqlmodel import Session
    from models import (
        engine, Usuario, Obra, Edicao, Leitura, ReviewLike, ReviewComment,
        ReviewReport, SavedReview, BuscaCache, CatalogSuggestion, UserEdition,
        EdicaoCapitulo,
    )

    model_by_table = {
        "usuario": Usuario,
        "obra": Obra,
        "edicao": Edicao,
        "leitura": Leitura,
        "reviewlike": ReviewLike,
        "reviewcomment": ReviewComment,
        "reviewreport": ReviewReport,
        "savedreview": SavedReview,
        "buscacache": BuscaCache,
        "catalogsuggestion": CatalogSuggestion,
        "useredition": UserEdition,
        "edicaocapitulo": EdicaoCapitulo,
    }
    inspector = inspect(engine)
    print("\nTabelas principais:")
    with Session(engine) as session:
        for table in MAIN_TABLES:
            exists = _table_exists(inspector, table)
            count = _scalar_count(session, model_by_table[table]) if exists else "n/a"
            print(f"- {table}: existe={str(exists).lower()} total={count}")
        print(f"- catálogo/editoras distintas (edicao.editora): {_distinct_count(session, Edicao.editora)}")
        print(f"- catálogo/autores distintos (obra.autor): {_distinct_count(session, Obra.autor)}")


def _find_obra(session, item):
    from sqlmodel import select
    from sqlalchemy import func
    from models import Obra

    work_key = _clean(item.get("work_key"))
    titulo = _clean(item.get("titulo"))
    autor = _clean(item.get("autor"))
    if work_key:
        found = session.exec(select(Obra).where(Obra.ol_work_key == work_key)).first()
        if found:
            return found
    if titulo:
        query = select(Obra).where(func.lower(Obra.titulo) == titulo.lower())
        if autor:
            query = query.where(func.lower(Obra.autor) == autor.lower())
        found = session.exec(query).first()
        if found:
            return found
    return None


def _find_edicao(session, obra, edicao_data):
    from sqlmodel import select
    from models import Edicao
    from fontes import normalizar_isbn

    ol_edition_key = _clean(edicao_data.get("ol_edition_key"))
    isbn = normalizar_isbn(_clean(edicao_data.get("isbn")))
    if ol_edition_key:
        found = session.exec(select(Edicao).where(Edicao.ol_edition_key == ol_edition_key)).first()
        if found:
            return found
    if isbn:
        found = session.exec(select(Edicao).where(Edicao.isbn == isbn)).first()
        if found:
            return found
    editora = _clean(edicao_data.get("editora"))
    tradutor = _clean(edicao_data.get("tradutor"))
    ano = _int_or_none(edicao_data.get("ano_edicao"))
    return session.exec(
        select(Edicao)
        .where(Edicao.obra_id == obra.id)
        .where(Edicao.editora == editora)
        .where(Edicao.tradutor == tradutor)
        .where(Edicao.ano == ano)
    ).first()


def _import_catalog(items: list[dict[str, Any]]) -> ImportStats:
    from sqlmodel import Session
    from models import engine, Obra, Edicao
    from fontes import normalizar_isbn

    stats = ImportStats()
    with Session(engine) as session:
        for item in items:
            work_key = _clean(item.get("work_key"))
            titulo = _clean(item.get("titulo"))
            if not work_key or not titulo:
                continue
            obra = _find_obra(session, item)
            if obra:
                stats.obras_existing += 1
                changed = False
                for attr, source in [
                    ("autor", "autor"), ("idioma_original", "idioma_original"),
                    ("descricao", "descricao"), ("generos_json", "generos_json"),
                    ("autor_pais", "autor_pais"), ("autor_nacionalidade", "autor_nacionalidade"),
                    ("literatura_pais", "literatura_pais"), ("literatura_regiao", "literatura_regiao"),
                ]:
                    val = _clean(item.get(source))
                    if val and not _clean(getattr(obra, attr, "")):
                        setattr(obra, attr, val); changed = True
                ano = _int_or_none(item.get("ano_obra"))
                if ano and obra.ano is None:
                    obra.ano = ano; changed = True
                if changed:
                    session.add(obra); session.commit(); session.refresh(obra)
            else:
                obra = Obra(
                    ol_work_key=work_key,
                    titulo=titulo,
                    autor=_clean(item.get("autor")),
                    ano=_int_or_none(item.get("ano_obra")),
                    idioma_original=_clean(item.get("idioma_original")),
                    descricao=_clean(item.get("descricao")),
                    generos_json=_clean(item.get("generos_json")),
                    autor_pais=_clean(item.get("autor_pais")),
                    autor_nacionalidade=_clean(item.get("autor_nacionalidade")),
                    literatura_pais=_clean(item.get("literatura_pais")),
                    literatura_regiao=_clean(item.get("literatura_regiao")),
                )
                session.add(obra); session.commit(); session.refresh(obra)
                stats.obras_created += 1

            for edicao_data in item.get("edicoes", []) or []:
                if not isinstance(edicao_data, dict):
                    continue
                edicao = _find_edicao(session, obra, edicao_data)
                if edicao:
                    stats.edicoes_existing += 1
                    changed = False
                    for attr, source in [("capa_url", "capa_url"), ("idioma", "idioma"), ("tradutor", "tradutor"), ("editora", "editora")]:
                        val = _clean(edicao_data.get(source))
                        if val and not _clean(getattr(edicao, attr, "")):
                            setattr(edicao, attr, val); changed = True
                    paginas = _int_or_none(edicao_data.get("paginas"))
                    if paginas and edicao.paginas is None:
                        edicao.paginas = paginas; changed = True
                    if changed:
                        session.add(edicao); session.commit()
                    continue
                edicao = Edicao(
                    obra_id=obra.id,
                    ol_edition_key=_clean(edicao_data.get("ol_edition_key")) or None,
                    editora=_clean(edicao_data.get("editora")),
                    tradutor=_clean(edicao_data.get("tradutor")),
                    isbn=normalizar_isbn(_clean(edicao_data.get("isbn"))),
                    idioma=_clean(edicao_data.get("idioma")),
                    ano=_int_or_none(edicao_data.get("ano_edicao")),
                    capa_url=_clean(edicao_data.get("capa_url")),
                    paginas=_int_or_none(edicao_data.get("paginas")),
                )
                session.add(edicao); session.commit()
                stats.edicoes_created += 1
    return stats


def _print_final_totals(stats: ImportStats) -> None:
    from sqlmodel import Session
    from models import engine, Obra, Edicao

    with Session(engine) as session:
        total_obras = _scalar_count(session, Obra)
        total_edicoes = _scalar_count(session, Edicao)
        total_editoras = _distinct_count(session, Edicao.editora)
        total_autores = _distinct_count(session, Obra.autor)
    print("\nImportação concluída:")
    print(f"- total de obras: {total_obras}")
    print(f"- total de edições: {total_edicoes}")
    print(f"- total de editoras: {total_editoras}")
    print(f"- total de autores: {total_autores}")
    print(f"- obras criadas: {stats.obras_created}")
    print(f"- obras já existentes: {stats.obras_existing}")
    print(f"- edições criadas: {stats.edicoes_created}")
    print(f"- edições já existentes: {stats.edicoes_existing}")


def main() -> None:
    _require_database_url()
    items = _load_catalog()
    print(f"Dataset local: {CATALOG_PATH.relative_to(ROOT)} ({len(items)} obras no arquivo)")
    _create_and_migrate()
    _print_table_report()
    stats = _import_catalog(items)
    _print_final_totals(stats)


if __name__ == "__main__":
    main()

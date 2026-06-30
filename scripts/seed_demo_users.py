#!/usr/bin/env python3
"""Seed/reset safe demo social data for Lombada.

Dry-run is the default. Use --apply to persist changes.
The script never deletes catalog tables (obra, edicao, source_records) and only
removes real-user activity when an explicit --reset-user-email/handle target is
provided.
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import or_, text  # noqa: E402
from sqlmodel import SQLModel, Session, select  # noqa: E402

from models import (  # noqa: E402
    CatalogSuggestion,
    Edicao,
    Follow,
    Leitura,
    Obra,
    ReadingJournalEntry,
    ReviewLike,
    ReviewReport,
    SavedReview,
    UserEdition,
    Usuario,
    engine,
    migrar,
)

DEMO_USERS = [
    ("Virginia Lobo", "demo-virginia-lobo", "Lê entre marés, quartos silenciosos e frases que parecem janelas."),
    ("Franz Carteiro", "demo-franz-carteiro", "Abre processos contra livros que não terminam nunca."),
    ("Clarice Lispectorinha", "demo-clarice-lispectorinha", "Procura epifanias em lombadas gastas e cafés frios."),
    ("Jorge Labirinto", "demo-jorge-labirinto", "Perdeu-se numa biblioteca e decidiu morar nela."),
    ("Machado de Bronze", "demo-machado-bronze", "Desconfia de narradores, principalmente dos muito simpáticos."),
    ("Ursula das Estrelas", "demo-ursula-estrelas", "Ficção científica, mundos possíveis e sociedades impossíveis."),
    ("Italo Viajante", "demo-italo-viajante", "Coleciona cidades invisíveis e capítulos curtos."),
    ("Toni Morrisonal", "demo-toni-morrisonal", "Lê memória, trauma, beleza e assombro."),
    ("Elena Ferragem", "demo-elena-ferragem", "Amizades difíceis, romances longos e capas dramáticas."),
    ("Octavia Jardim", "demo-octavia-jardim", "Planta futuros estranhos em terrenos pós-apocalípticos."),
]

REVIEW_TEXTS = [
    "Não é um livro que se fecha; é um livro que continua respirando na sala.",
    "Li devagar, como quem atravessa uma casa escura procurando o interruptor.",
    "A edição é bonita, mas o que fica mesmo é a sensação de ter sido observado pelo livro.",
    "Tem páginas que parecem escritas com uma calma perigosa.",
    "Gostei mais da atmosfera do que da trama, e talvez isso já diga bastante.",
    "Um livro que pede silêncio ao redor.",
    "Não sei se entendi tudo, mas fiquei pensando nele por dias.",
    "Há uma música baixa nessas páginas, mesmo quando a história escurece.",
    "Terminei com vontade de reler só para confirmar se o livro também me leu.",
]

JOURNAL_NOTES = [
    "Ainda estou procurando a porta secreta do livro.",
    "O ritmo ficou mais estranho e mais bonito.",
    "Pausa para respirar: a frase final do capítulo ficou comigo.",
    "A leitura está andando como chuva fina: sem pressa, mas constante.",
]

STATUSES = ["Lido", "Lendo", "Quero ler", "Abandonado"]
DEMO_HANDLES = [handle for _, handle, _ in DEMO_USERS]


@dataclass
class Summary:
    target: str = ""
    removed_leituras: int = 0
    removed_journals: int = 0
    removed_user_editions: int = 0
    removed_follows: int = 0
    removed_likes: int = 0
    removed_saved: int = 0
    removed_reports: int = 0
    removed_suggestions: int = 0
    removed_demo_users: int = 0
    demo_users: int = 0
    demo_readings: int = 0
    demo_reviews: int = 0
    demo_shelves: int = 0
    follows: int = 0
    likes: int = 0
    journals: int = 0
    books_used: int = 0
    warnings: list[str] | None = None

    def warn(self, message: str) -> None:
        if self.warnings is None:
            self.warnings = []
        self.warnings.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Limpa atividade de usuário e popula usuários demo literários.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Mostra o que seria feito sem persistir (padrão).")
    mode.add_argument("--apply", action="store_true", help="Persiste as mudanças.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--reset-user-email", help="Email do usuário real cuja atividade será limpa.")
    target.add_argument("--reset-user-handle", help="Handle do usuário real cuja atividade será limpa.")
    parser.add_argument("--reset-demo-users", action="store_true", help="Remove usuários demo existentes antes de recriar.")
    parser.add_argument("--seed", type=int, default=20260630, help="Seed determinística para dados demo.")
    return parser.parse_args()


def count_and_delete(session: Session, model, *criteria) -> int:
    rows = session.exec(select(model).where(*criteria)).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def user_leitura_ids(session: Session, user_ids: Iterable[int]) -> list[int]:
    ids = [uid for uid in user_ids if uid is not None]
    if not ids:
        return []
    return list(session.exec(select(Leitura.id).where(Leitura.usuario_id.in_(ids))).all())


def reset_activity(session: Session, user_ids: list[int], summary: Summary) -> None:
    if not user_ids:
        return
    leitura_ids = user_leitura_ids(session, user_ids)
    if leitura_ids:
        summary.removed_likes += count_and_delete(session, ReviewLike, ReviewLike.leitura_id.in_(leitura_ids))
        summary.removed_saved += count_and_delete(session, SavedReview, SavedReview.leitura_id.in_(leitura_ids))
        summary.removed_reports += count_and_delete(session, ReviewReport, ReviewReport.leitura_id.in_(leitura_ids))
        summary.removed_journals += count_and_delete(session, ReadingJournalEntry, ReadingJournalEntry.leitura_id.in_(leitura_ids))
    summary.removed_likes += count_and_delete(session, ReviewLike, ReviewLike.usuario_id.in_(user_ids))
    summary.removed_saved += count_and_delete(session, SavedReview, SavedReview.usuario_id.in_(user_ids))
    summary.removed_reports += count_and_delete(session, ReviewReport, ReviewReport.usuario_id.in_(user_ids))
    summary.removed_journals += count_and_delete(session, ReadingJournalEntry, ReadingJournalEntry.usuario_id.in_(user_ids))
    summary.removed_follows += count_and_delete(session, Follow, or_(Follow.follower_id.in_(user_ids), Follow.following_id.in_(user_ids)))
    summary.removed_user_editions += count_and_delete(session, UserEdition, UserEdition.usuario_id.in_(user_ids))
    summary.removed_suggestions += count_and_delete(session, CatalogSuggestion, CatalogSuggestion.user_id.in_(user_ids))
    summary.removed_leituras += count_and_delete(session, Leitura, Leitura.usuario_id.in_(user_ids))


def find_target_user(session: Session, args: argparse.Namespace, summary: Summary) -> Usuario | None:
    if args.reset_user_email:
        user = session.exec(select(Usuario).where(Usuario.email == args.reset_user_email)).first()
        summary.target = args.reset_user_email
    elif args.reset_user_handle:
        user = session.exec(select(Usuario).where(Usuario.handle == args.reset_user_handle)).first()
        summary.target = args.reset_user_handle
    else:
        return None
    if not user:
        summary.warn(f"Usuário alvo não encontrado: {summary.target}")
        return None
    return user


def demo_users_query(session: Session) -> list[Usuario]:
    return session.exec(select(Usuario).where(or_(Usuario.is_demo == True, Usuario.handle.in_(DEMO_HANDLES), Usuario.handle.startswith("demo-")))).all()


def load_editions(session: Session, summary: Summary, limit: int = 200) -> list[tuple[Edicao, Obra]]:
    rows = session.exec(
        select(Edicao, Obra)
        .join(Obra, Edicao.obra_id == Obra.id)
        .order_by(
            text("CASE WHEN edicao.capa_url <> '' THEN 0 ELSE 1 END"),
            text("CASE WHEN edicao.isbn <> '' THEN 0 ELSE 1 END"),
            text("CASE WHEN lower(edicao.idioma) IN ('pt','pt-br','português','portugues','por') THEN 0 ELSE 1 END"),
            Edicao.ano.desc(),
        )
        .limit(limit)
    ).all()
    if not rows:
        summary.warn("Nenhuma edição encontrada no catálogo; usuários demo serão criados sem estantes/leituras.")
    elif len(rows) < 80:
        summary.warn(f"Catálogo com poucas edições ({len(rows)}); o script vai reutilizar livros disponíveis sem quebrar.")
    return rows


def upsert_demo_users(session: Session, summary: Summary) -> list[Usuario]:
    users: list[Usuario] = []
    for name, handle, bio in DEMO_USERS:
        user = session.exec(select(Usuario).where(Usuario.handle == handle)).first()
        if user and user.google_sub:
            summary.warn(f"Handle demo ocupado por usuário Google preservado, não modificado: {handle}")
            continue
        if not user:
            slug = handle.removeprefix("demo-")
            user = Usuario(handle=handle, email=f"demo+{slug}@lombada.local", google_sub=None)
            session.add(user)
        user.nome = name
        user.bio = bio
        user.is_demo = True
        user.google_sub = None
        if not user.email:
            user.email = f"demo+{handle.removeprefix('demo-')}@lombada.local"
        users.append(user)
    session.flush()
    summary.demo_users = len(users)
    return users


def add_follow(session: Session, follower_id: int, following_id: int, summary: Summary) -> None:
    if follower_id == following_id:
        return
    exists = session.exec(select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == following_id)).first()
    if not exists:
        session.add(Follow(follower_id=follower_id, following_id=following_id))
        summary.follows += 1


def seed_demo_data(session: Session, users: list[Usuario], target_user: Usuario | None, summary: Summary, rng: random.Random) -> None:
    editions = load_editions(session, summary)
    if not editions:
        return
    all_reviews: list[Leitura] = []
    used_ids: set[int] = set()
    today = datetime.utcnow().date()
    for idx, user in enumerate(users):
        shelf_count = min(len(editions), rng.randint(8, 20))
        start = (idx * 11) % len(editions)
        chosen = [editions[(start + offset) % len(editions)] for offset in range(shelf_count)]
        for pos, (edition, _work) in enumerate(chosen):
            used_ids.add(edition.id)
            rel = session.exec(select(UserEdition).where(UserEdition.usuario_id == user.id, UserEdition.edicao_id == edition.id)).first()
            if not rel:
                rel = UserEdition(usuario_id=user.id, edicao_id=edition.id)
                session.add(rel)
                summary.demo_shelves += 1
            rel.tenho = pos % 3 != 1
            rel.quero = pos % 4 == 1
        reading_count = min(len(chosen), rng.randint(3, 8))
        for pos, (edition, _work) in enumerate(chosen[:reading_count]):
            status = STATUSES[(idx + pos) % len(STATUSES)]
            is_read = status == "Lido"
            relato = rng.choice(REVIEW_TEXTS) if is_read or pos % 2 == 0 else ""
            leitura = Leitura(
                edicao_id=edition.id,
                usuario_id=user.id,
                status=status,
                nota=round(rng.uniform(3.0, 5.0) * 2) / 2 if is_read else None,
                relato=relato,
                publico=bool(relato) or status in {"Lido", "Lendo"},
                spoiler=False,
                is_demo=True,
                data=str(today - timedelta(days=idx * 3 + pos * 5)),
            )
            session.add(leitura)
            session.flush()
            summary.demo_readings += 1
            if relato:
                summary.demo_reviews += 1
                all_reviews.append(leitura)
            if status == "Lendo":
                entry = ReadingJournalEntry(
                    leitura_id=leitura.id,
                    usuario_id=user.id,
                    progresso_tipo="pagina" if pos % 2 == 0 else "porcentagem",
                    pagina=42 + idx + pos if pos % 2 == 0 else None,
                    porcentagem=35 + idx if pos % 2 == 1 else None,
                    nota=rng.choice(JOURNAL_NOTES),
                    publico=pos % 2 == 0,
                    spoiler=False,
                )
                session.add(entry)
                summary.journals += 1
    summary.books_used = len(used_ids)

    for i, follower in enumerate(users):
        for offset in (1, 2, 4):
            add_follow(session, follower.id, users[(i + offset) % len(users)].id, summary)
        if target_user and i % 2 == 0:
            add_follow(session, follower.id, target_user.id, summary)

    session.flush()
    for review in all_reviews:
        likers = rng.sample(users, k=min(len(users), rng.randint(2, 5)))
        for liker in likers:
            if liker.id == review.usuario_id:
                continue
            exists = session.exec(select(ReviewLike).where(ReviewLike.leitura_id == review.id, ReviewLike.usuario_id == liker.id)).first()
            if not exists:
                session.add(ReviewLike(leitura_id=review.id, usuario_id=liker.id))
                summary.likes += 1


def print_summary(summary: Summary, apply: bool) -> None:
    print("APPLY" if apply else "DRY RUN")
    if summary.target:
        print(f"Usuário alvo: {summary.target}")
        print(
            "Atividades removidas/removíveis: "
            f"{summary.removed_leituras} leituras, {summary.removed_user_editions} estantes, "
            f"{summary.removed_likes} likes, {summary.removed_follows} follows, "
            f"{summary.removed_journals} diários, {summary.removed_suggestions} sugestões"
        )
    print(f"Usuários demo removidos: {summary.removed_demo_users}")
    print(f"Demo users: {summary.demo_users}")
    print(f"Leituras demo: {summary.demo_readings}")
    print(f"Críticas públicas: {summary.demo_reviews}")
    print(f"Estantes: {summary.demo_shelves}")
    print(f"Entradas de diário: {summary.journals}")
    print(f"Follows: {summary.follows}")
    print(f"Likes: {summary.likes}")
    print(f"Livros disponíveis usados: {summary.books_used}")
    for warning in summary.warnings or []:
        print(f"AVISO: {warning}")


def main() -> int:
    args = parse_args()
    apply = bool(args.apply)
    rng = random.Random(args.seed)
    summary = Summary()
    SQLModel.metadata.create_all(engine)
    migrar()
    with Session(engine) as session:
        target_user = find_target_user(session, args, summary)
        if target_user:
            reset_activity(session, [target_user.id], summary)

        existing_demo_users = demo_users_query(session)
        protected_demo_users = [u for u in existing_demo_users if u.google_sub]
        for user in protected_demo_users:
            summary.warn(f"Demo candidato com google_sub preservado, não modificado: {user.handle}")
        safe_demo_users = [u for u in existing_demo_users if not u.google_sub]
        # Always clear safe demo activity for idempotency; optionally delete/recreate demo users.
        reset_activity(session, [u.id for u in safe_demo_users if u.id], summary)
        if args.reset_demo_users:
            for user in safe_demo_users:
                session.delete(user)
                summary.removed_demo_users += 1
            session.flush()

        users = upsert_demo_users(session, summary)
        seed_demo_data(session, users, target_user, summary, rng)

        if apply:
            session.commit()
        else:
            session.rollback()
    print_summary(summary, apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

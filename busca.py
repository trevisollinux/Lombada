"""
Lombada — scoring, deduplicação e orquestração da busca.
"""
import json
import concurrent.futures as _fut
from datetime import datetime, timedelta

from sqlmodel import select, Session

from models import BuscaCache
from fontes import (
    gbooks_buscar, ol_buscar,
    _gbooks_info, _ol_isbn,
    normalizar_isbn, _sem_acento, _query_norm, _relevancia, _split_q,
    _limpa_capa_gb, _capa_ol_isbn,
    EDITORAS_BR_FORTES,
)


# ─── cache de busca (banco) ───────────────────────────────
def _cache_get(q: str, s: Session, minutos: int = 1440):
    qn = _query_norm(q)
    row = s.exec(
        select(BuscaCache)
        .where(BuscaCache.query_norm == qn)
        .order_by(BuscaCache.criado_em.desc())
    ).first()
    if not row:
        return None
    if datetime.utcnow() - row.criado_em > timedelta(minutes=minutos):
        return None
    try:
        return json.loads(row.resultados_json)
    except Exception:
        return None


def _cache_set(q: str, resultados: list, s: Session) -> None:
    try:
        row = BuscaCache(
            query=q,
            query_norm=_query_norm(q),
            resultados_json=json.dumps(resultados, ensure_ascii=False),
        )
        s.add(row)
        s.commit()
    except Exception:
        s.rollback()


# ─── quality score ────────────────────────────────────────
_FONTE_SCORE = {"me": 25, "gb": 10, "hardcover": 8, "ol": 5}


def quality_score(doc: dict, busca: str = "") -> dict:
    score   = 0
    titulo  = doc.get("titulo", "")
    autor   = doc.get("autor", "")
    capa    = doc.get("capa_url", "")
    ed      = doc.get("edicao_isbn") or {}
    isbn    = ed.get("isbn") or ""
    idioma  = ed.get("idioma") or doc.get("idioma_original") or ""
    editora = _sem_acento(ed.get("editora") or "")
    tradutor= ed.get("tradutor") or ""
    ano     = ed.get("ano") or doc.get("ano")
    rel     = _relevancia(titulo, busca)

    if isbn:     score += 40
    if capa:     score += 35
    if idioma == "Português": score += 30
    score += {0: 30, 1: 20, 2: 10}.get(rel, 0)
    if autor and autor != "—":                          score += 20
    if any(e in editora for e in EDITORAS_BR_FORTES):   score += 20
    if ano:      score += 10
    if tradutor: score += 15

    qn = _query_norm(busca)
    if idioma in ("Inglês", "Espanhol") and not any(
        x in qn for x in ("english", "ingles", "espanol", "espanhol")
    ):
        score -= 25
    if not capa:  score -= 20
    if not isbn:  score -= 15

    score += _FONTE_SCORE.get(doc.get("_fonte", ""), 0)
    doc["quality_score"] = max(score, 0)
    return doc


def ordenar_por_qualidade(docs: list, q: str) -> list:
    tratados = [quality_score(d, q) for d in docs if d]
    tratados.sort(key=lambda d: d.get("quality_score", 0), reverse=True)
    return tratados


def _dedup_key(doc: dict) -> str:
    ed   = doc.get("edicao_isbn") or {}
    isbn = normalizar_isbn(ed.get("isbn") or "")
    if isbn:
        return f"isbn:{isbn}"
    titulo  = _sem_acento(doc.get("titulo", ""))
    autor   = _sem_acento(doc.get("autor", ""))
    editora = _sem_acento(ed.get("editora", ""))
    ano     = ed.get("ano") or doc.get("ano") or ""
    return f"{titulo}|{autor}|{editora}|{ano}"


def deduplicar_docs(docs: list) -> list:
    melhores: dict = {}
    for doc in docs:
        if not doc: continue
        k = _dedup_key(doc)
        atual = melhores.get(k)
        if not atual or doc.get("quality_score", 0) > atual.get("quality_score", 0):
            melhores[k] = doc
    return list(melhores.values())


def _filtrar_relevancia(obras: list, q: str) -> list:
    """Corta ruído: mantém quem casa no título OU no autor.
    Se sobrar vazio, devolve tudo (nunca deixa o usuário na mão)."""
    titulo_q, autor_q = _split_q(q)
    tokens = [t for t in _sem_acento(autor_q or titulo_q).split() if len(t) >= 3]

    def relevante(o):
        if _relevancia(o.get("titulo", ""), titulo_q) <= 2:
            return True
        alvo = _sem_acento(" ".join(o.get("_autores") or []) + " " + (o.get("autor") or ""))
        return any(t in alvo for t in tokens)

    filtrados = [o for o in obras if relevante(o)]
    return filtrados or obras


# ─── orquestração ─────────────────────────────────────────
def buscar_titulo_v2(q: str) -> list:
    # Espinha: Google Books (BR-first, capa + ISBN, agrupado em obras sem segunda chamada).
    obras = gbooks_buscar(q, limite=18)

    # Fallback: Open Library quando GB volta vazio (clássicos mal catalogados).
    if not obras:
        obras = ol_buscar(q)

    # ME e Wikidata fora do hot path — ver flag ME_ATIVO em models.py:
    #   if ME_ATIVO: from fontes import me_buscar; obras = me_buscar(q) + obras
    #   from fontes import wikidata_buscar_obra; wiki = wikidata_buscar_obra(q); ...

    obras = _filtrar_relevancia(obras, q)
    obras = ordenar_por_qualidade(obras, q)
    obras = deduplicar_docs(obras)
    obras = ordenar_por_qualidade(obras, q)
    for o in obras:
        o.pop("_autores", None)
    return obras


def _edicao_por_isbn(isbn: str) -> dict | None:
    isbn = normalizar_isbn(isbn)
    if not isbn:
        return None
    with _fut.ThreadPoolExecutor(max_workers=2) as ex:
        f_gb = ex.submit(_gbooks_info, isbn)
        f_ol = ex.submit(_ol_isbn, isbn)
        gb, ol = f_gb.result(), f_ol.result()
    if not gb and not ol:
        return None
    titulo   = (gb.get("titulo") or ol.get("titulo") or "").strip()
    autor    = gb.get("autor") or "—"
    editora  = ol.get("editora") or gb.get("editora") or ""
    tradutor = ol.get("tradutor") or ""
    ano      = gb.get("ano") or ol.get("ano")
    idioma   = ol.get("idioma") or gb.get("idioma") or ""
    capa     = _limpa_capa_gb(gb.get("capa") or "") or ol.get("capa_url") or _capa_ol_isbn(isbn)
    work_key = ol.get("work_key") or ("isbn:" + isbn)
    if not titulo:
        titulo = "Edição " + isbn
    edicao = {
        "ol_edition_key": ol.get("ol_edition_key") or ("isbn:" + isbn),
        "titulo_edicao": titulo, "editora": editora,
        "tradutor": tradutor, "isbn": isbn,
        "idioma": idioma, "ano": ano, "capa_url": capa,
    }
    doc = {
        "work_key": work_key, "titulo": titulo, "autor": autor,
        "ano": ano, "idioma_original": idioma,
        "tem_pt": idioma == "Português", "capa_url": capa,
        "isbn_match": True, "edicao_isbn": edicao, "_fonte": "isbn",
    }
    return quality_score(doc, titulo)

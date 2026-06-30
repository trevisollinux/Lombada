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
    normalizar_isbn, _sem_acento, _query_norm, _match_norm, _relevancia, _split_q,
    _limpa_capa_gb, _capa_ol_isbn, chave_obra_canonica,
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
_RUIDO_TITULO = (
    "anais",
    "congresso",
    "seminario",
    "simposio",
    "coloquio",
    "artigo",
    "tese",
    "dissertacao",
    "thesis",
    "dissertation",
    "seminar",
    "study",
    "studies",
    "essays",
    "critique",
    "analysis",
    "biography",
    "lettres",
    "correspondance",
    "etudes",
    "resumo",
    "analise",
    "ensaio",
    "biografia",
    "estudo critico",
    "sociedades mediatizadas",
)
_TITULOS_PT_SINAIS = (
    "crime e castigo",
    "irmaos karamazov",
    "os irmaos karamazov",
    "a montanha magica",
    "memorias do subsolo",
    "o idiota",
    "os demonios",
    "notas do subsolo",
)
_IDIOMAS_PT = {"portugues", "pt", "por", "pt-br", "br"}
_ISBN_PREFIXOS_BR = ("97885", "97865")


def _parece_ruido(titulo: str) -> bool:
    titulo_norm = _sem_acento(titulo or "")
    return any(termo in titulo_norm for termo in _RUIDO_TITULO)


def _idioma_norm(idioma: str) -> str:
    return _sem_acento(idioma or "").replace("_", "-")


def _eh_portugues(idioma: str) -> bool:
    idioma_norm = _idioma_norm(idioma)
    return idioma_norm in _IDIOMAS_PT or "portugues" in idioma_norm


def _titulo_parece_pt(titulo: str) -> bool:
    titulo_norm = _query_norm(titulo)
    return any(sinal in titulo_norm for sinal in _TITULOS_PT_SINAIS)


def _isbn_parece_br(isbn: str) -> bool:
    isbn_norm = normalizar_isbn(isbn)
    return bool(isbn_norm and isbn_norm.startswith(_ISBN_PREFIXOS_BR))


def _tokens_busca(q: str) -> list[str]:
    return [t for t in _match_norm(q).split() if len(t) >= 3]


def _match_tokens(texto: str, tokens: list[str]) -> int:
    alvo = _match_norm(texto)
    return sum(1 for t in tokens if t in alvo)


def _score_match_busca(titulo: str, autor: str, busca: str) -> int:
    titulo_q, autor_q = _split_q(busca)
    tokens_titulo = _tokens_busca(titulo_q)
    tokens_autor = _tokens_busca(autor_q)
    todos_tokens = _tokens_busca(busca)
    score = 0

    rel = _relevancia(titulo, titulo_q)
    score += {0: 55, 1: 40, 2: 25}.get(rel, 0)

    titulo_hits = _match_tokens(titulo, tokens_titulo)
    autor_hits = _match_tokens(autor, tokens_autor or todos_tokens)
    if tokens_titulo and titulo_hits == len(tokens_titulo):
        score += 25
    elif titulo_hits:
        score += 8 * titulo_hits
    if autor_hits:
        score += 35 + (8 * autor_hits)

    # Em buscas só por autor, obras do próprio autor devem ganhar de estudos sobre ele.
    if not autor_q and autor_hits and not titulo_hits:
        score += 20
    if not autor_q and not autor_hits and _parece_ruido(titulo):
        score -= 35
    return score


def _busca_titulo_curto_sem_autor(q: str) -> bool:
    titulo_q, autor_q = _split_q(q)
    tokens = [t for t in _query_norm(titulo_q).split() if t]
    return not autor_q and 1 <= len(tokens) <= 5


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

    if isbn:     score += 40
    if capa:     score += 35
    if _eh_portugues(idioma) or doc.get("tem_pt"): score += 45
    if _titulo_parece_pt(titulo) or _titulo_parece_pt(ed.get("titulo_edicao") or ""):
        score += 20
    score += _score_match_busca(titulo, autor, busca)
    if autor and autor != "—":                          score += 20
    if any(e in editora for e in EDITORAS_BR_FORTES):   score += 20
    if _isbn_parece_br(isbn):                            score += 18
    if ano:      score += 10
    if tradutor: score += 15

    qn = _query_norm(busca)
    if not _eh_portugues(idioma) and idioma and not any(
        x in qn for x in (
            "english", "ingles", "espanol", "espanhol", "frances", "francais",
            "french", "russo", "russian", "alemao", "german", "italiano",
        )
    ):
        score -= 25
    if not capa:  score -= 20
    if not isbn:  score -= 15

    if _parece_ruido(titulo):
        score -= 55
    if _busca_titulo_curto_sem_autor(busca) and _relevancia(titulo, busca) > 0 and _parece_ruido(titulo):
        score -= 35

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


# ─── fusão obra-first (uma obra, várias edições) ──────────────────────────
def _assinatura_edicao(ed: dict) -> str:
    isbn = normalizar_isbn((ed or {}).get("isbn") or "")
    if isbn:
        return f"isbn:{isbn}"
    titulo  = _sem_acento((ed or {}).get("titulo_edicao") or "")
    editora = _sem_acento((ed or {}).get("editora") or "")
    ano     = (ed or {}).get("ano") or ""
    chave   = (ed or {}).get("ol_edition_key") or ""
    return f"{titulo}|{editora}|{ano}|{chave}"


def _edicoes_do_doc(doc: dict) -> list:
    eds = list(doc.get("edicoes") or [])
    ed_isbn = doc.get("edicao_isbn")
    if ed_isbn:
        eds = [ed_isbn] + eds
    return eds


def _merge_obras_canonico(docs: list) -> list:
    """Junta docs que são a MESMA obra (título/autor canônicos), somando edições.
    O doc de melhor qualidade vira a vitrine; os demais viram edições dele."""
    grupos: dict[str, dict] = {}
    ordem: list[str] = []
    for doc in docs:
        if not doc:
            continue
        chave = chave_obra_canonica(doc.get("titulo", ""), doc.get("autor", ""))
        if not chave:
            chave = f"uniq:{id(doc)}"
        atual = grupos.get(chave)
        if atual is None:
            grupos[chave] = doc
            ordem.append(chave)
            continue
        # vitrine = doc de maior quality_score; o outro vira só fonte de edições
        if doc.get("quality_score", 0) > atual.get("quality_score", 0):
            vitrine, extra = doc, atual
            grupos[chave] = vitrine
        else:
            vitrine, extra = atual, doc
        vistas = {_assinatura_edicao(e) for e in _edicoes_do_doc(vitrine)}
        merged = list(vitrine.get("edicoes") or _edicoes_do_doc(vitrine))
        for e in _edicoes_do_doc(extra):
            a = _assinatura_edicao(e)
            if a not in vistas:
                vistas.add(a)
                merged.append(e)
        vitrine["edicoes"] = merged
        if not vitrine.get("capa_url") and extra.get("capa_url"):
            vitrine["capa_url"] = extra["capa_url"]
        vitrine["tem_pt"] = vitrine.get("tem_pt") or extra.get("tem_pt")

    saida = []
    for chave in ordem:
        obra = grupos[chave]
        edicoes = obra.get("edicoes")
        if edicoes is None:
            edicoes = _edicoes_do_doc(obra)
            obra["edicoes"] = edicoes
        obra["edicoes_encontradas"] = len(edicoes)
        if not chave.startswith("uniq:"):
            obra["chave_obra"] = chave        # o front agrupa por esta chave canônica
        saida.append(obra)
    return saida


def _filtrar_relevancia(obras: list, q: str) -> list:
    """Corta ruído: mantém quem casa no título OU no autor.
    Se sobrar vazio, devolve tudo (nunca deixa o usuário na mão)."""
    titulo_q, autor_q = _split_q(q)
    tokens = [t for t in _match_norm(autor_q or titulo_q).split() if len(t) >= 3]
    titulo_tokens = [t for t in _match_norm(titulo_q).split() if len(t) >= 3]

    def relevante(o):
        if _relevancia(o.get("titulo", ""), titulo_q) <= 2:
            return True
        alvo_autor = _match_norm(" ".join(o.get("_autores") or []) + " " + (o.get("autor") or ""))
        if any(t in alvo_autor for t in tokens):
            return True
        # rede de segurança: metade ou mais dos tokens do título batem no título do resultado
        if titulo_tokens:
            alvo_titulo = _match_norm(o.get("titulo", ""))
            hits = sum(1 for t in titulo_tokens if t in alvo_titulo)
            if hits >= (len(titulo_tokens) + 1) // 2:
                return True
        return False

    filtrados = [o for o in obras if relevante(o)]
    return filtrados or obras


def _deve_consultar_ol(q: str, obras_gb: list) -> bool:
    if normalizar_isbn(q):
        return False
    if not obras_gb:
        return True
    titulo_q, autor_q = _split_q(q)
    if autor_q:
        return True
    tokens = [t for t in _query_norm(titulo_q).split() if t]
    return 1 <= len(tokens) <= 5


# ─── orquestração ─────────────────────────────────────────
def buscar_titulo_v2(q: str) -> list:
    # Espinha: Google Books (BR-first, capa + ISBN, agrupado em obras sem segunda chamada).
    obras_gb = gbooks_buscar(q, limite=18)
    obras_ol = ol_buscar(q) if _deve_consultar_ol(q, obras_gb) else []
    obras = obras_gb + obras_ol

    # Fallback: Open Library quando GB volta vazio (clássicos mal catalogados).
    if not obras:
        obras = ol_buscar(q)

    # ME e Wikidata fora do hot path — ver flag ME_ATIVO em models.py:
    #   if ME_ATIVO: from fontes import me_buscar; obras = me_buscar(q) + obras
    #   from fontes import wikidata_buscar_obra; wiki = wikidata_buscar_obra(q); ...

    obras = _filtrar_relevancia(obras, q)
    obras = ordenar_por_qualidade(obras, q)
    obras = deduplicar_docs(obras)
    obras = _merge_obras_canonico(obras)
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
        "chave_obra": chave_obra_canonica(titulo, autor),
    }
    return quality_score(doc, titulo)

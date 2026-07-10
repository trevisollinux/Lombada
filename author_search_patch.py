"""Correções isoladas para a busca de autores.

O catálogo normaliza a consulta em Python, mas o pré-filtro SQL antigo comparava
essa versão sem acentos com colunas ainda acentuadas. Assim, ``Dostoievski`` não
casava com ``Dostoiévski`` e grande parte do catálogo local nem chegava ao
ranqueamento. Este módulo mantém a mesma resposta da busca original, trocando
apenas o funil SQL e o limite de resultados quando a consulta é dominada por
autores.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode

import busca as busca_module
import main as m


_SQL_ACCENT_REPLACEMENTS = (
    ("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"), ("ä", "a"),
    ("Á", "a"), ("À", "a"), ("Ã", "a"), ("Â", "a"), ("Ä", "a"),
    ("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
    ("É", "e"), ("È", "e"), ("Ê", "e"), ("Ë", "e"),
    ("í", "i"), ("ì", "i"), ("î", "i"), ("ï", "i"),
    ("Í", "i"), ("Ì", "i"), ("Î", "i"), ("Ï", "i"),
    ("ó", "o"), ("ò", "o"), ("õ", "o"), ("ô", "o"), ("ö", "o"),
    ("Ó", "o"), ("Ò", "o"), ("Õ", "o"), ("Ô", "o"), ("Ö", "o"),
    ("ú", "u"), ("ù", "u"), ("û", "u"), ("ü", "u"),
    ("Ú", "u"), ("Ù", "u"), ("Û", "u"), ("Ü", "u"),
    ("ç", "c"), ("Ç", "c"), ("ñ", "n"), ("Ñ", "n"),
    ("ý", "y"), ("ÿ", "y"), ("Ý", "y"),
)
_METADATA_SUFFIX = re.compile(
    r"\s+(?:autor|author|tradutor|translator|editora|publisher)\s*:",
    re.IGNORECASE,
)
_METADATA_PREFIX = re.compile(r"^(?:autor|author)\s*:\s*", re.IGNORECASE)


def sanitize_search_query(value: str | None) -> str:
    """Remove metadados que algumas fontes antigas colaram no campo de autor."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = _METADATA_PREFIX.sub("", text)
    match = _METADATA_SUFFIX.search(text)
    if match:
        text = text[: match.start()].strip()
    return text


def _sql_texto_normalizado(coluna):
    """Fold de acentos portátil entre SQLite (testes) e PostgreSQL (produção)."""
    expr = m.func.coalesce(coluna, "")
    for origem, destino in _SQL_ACCENT_REPLACEMENTS:
        expr = m.func.replace(expr, origem, destino)
    return m.func.lower(expr)


def buscar_catalogo_local(
    q: str,
    s: m.Session,
    editora: str = "",
    genero: str = "",
    literatura: dict | None = None,
) -> list[dict]:
    q = sanitize_search_query(q)
    q_norm = m._normalizar_busca(q)
    editora_norm = m._normalizar_busca(editora)
    isbn = m.normalizar_isbn(q or "")
    genero = m.normalizar_genero(genero)
    if not q_norm and not editora_norm and not genero and not literatura:
        return []

    busca_textual = bool(q_norm or isbn)
    candidato_limit = 500
    stmt = m.select(m.Obra, m.Edicao).join(m.Edicao, m.Edicao.obra_id == m.Obra.id)

    filtros = []
    if isbn:
        filtros.append(m.func.lower(m.func.coalesce(m.Edicao.isbn, "")).like(f"%{isbn.lower()}%"))
    elif q_norm:
        like = f"%{q_norm}%"
        filtros.append(
            _sql_texto_normalizado(m.Obra.titulo).like(like)
            | _sql_texto_normalizado(m.Obra.autor).like(like)
            | _sql_texto_normalizado(m.Edicao.editora).like(like)
            | _sql_texto_normalizado(m.Edicao.tradutor).like(like)
            | m.func.lower(m.func.coalesce(m.Edicao.isbn, "")).like(like)
        )
    if editora_norm:
        formas_editora = m._formas_texto_sql([editora])
        filtros.append(m.or_(*[_sql_texto_normalizado(m.Edicao.editora).like(f"%{m._normalizar_busca(f)}%") for f in formas_editora]))
    if literatura:
        formas_pais = m._formas_texto_sql(m._literatura_paises_raw(literatura))
        regiao_raw = literatura.get("regiao") if not literatura.get("pais") else ""
        formas_regiao = m._formas_texto_sql([regiao_raw]) if regiao_raw else set()
        lit_filtros = []
        if formas_pais:
            paises = {m._normalizar_busca(f) for f in formas_pais}
            lit_filtros.append(_sql_texto_normalizado(m.Obra.literatura_pais).in_(paises))
            lit_filtros.append(_sql_texto_normalizado(m.Obra.autor_pais).in_(paises))
        if formas_regiao:
            regioes = {m._normalizar_busca(f) for f in formas_regiao}
            lit_filtros.append(_sql_texto_normalizado(m.Obra.literatura_regiao).in_(regioes))
        if lit_filtros:
            sem_origem_catalogada = m.and_(
                m.or_(m.Obra.literatura_pais.is_(None), m.Obra.literatura_pais == ""),
                m.or_(m.Obra.literatura_regiao.is_(None), m.Obra.literatura_regiao == ""),
                m.or_(m.Obra.autor_pais.is_(None), m.Obra.autor_pais == ""),
            )
            filtros.append(m.or_(m.or_(*lit_filtros), sem_origem_catalogada))
    for filtro in filtros:
        stmt = stmt.where(filtro)
    stmt = stmt.order_by(m.Edicao.id.desc()).limit(candidato_limit)
    rows = s.exec(stmt).all()

    ed_ids = [ed.id for _, ed in rows if ed.id is not None]
    social_por_edicao: dict[int, dict] = {}
    if ed_ids:
        leituras_rows = s.exec(
            m.select(m.Leitura.edicao_id, m.Leitura.status, m.Leitura.nota, m.Leitura.publico, m.Leitura.relato)
            .where(m.Leitura.edicao_id.in_(ed_ids))
        ).all()
        for ed_id, status, nota, publico, relato in leituras_rows:
            stats = social_por_edicao.setdefault(
                ed_id,
                {"leituras": 0, "criticas": 0, "lendo": 0, "notas": []},
            )
            stats["leituras"] += 1
            if publico and (relato or "").strip():
                stats["criticas"] += 1
            if status == "Lendo":
                stats["lendo"] += 1
            if nota is not None:
                stats["notas"].append(float(nota))
    leituras = {ed_id: stats["leituras"] for ed_id, stats in social_por_edicao.items()}

    por_obra: dict[str, dict] = {}
    for obra, ed in rows:
        leituras_count = int(leituras.get(ed.id, 0))
        score, match = m._score_local(obra, ed, q_norm, isbn, editora_norm, leituras_count)
        searchable = " ".join(
            [
                m._normalizar_busca(obra.titulo),
                m._normalizar_busca(obra.autor),
                m._normalizar_busca(ed.isbn),
                m._normalizar_busca(ed.editora),
                m._normalizar_busca(ed.tradutor),
            ]
        )
        if q_norm and q_norm not in searchable and not (isbn and m.normalizar_isbn(ed.isbn or "") == isbn):
            continue
        if editora_norm and m._normalizar_busca(ed.editora) != editora_norm:
            continue

        genero_compat = None
        if genero:
            generos_da_obra = m.generos_obra(obra)
            genero_compat = (genero in generos_da_obra) if generos_da_obra else None
            if genero_compat is False:
                continue
            if genero_compat:
                score += 40

        lit_compat = None
        if literatura:
            lit_compat = m._compat_literatura(
                literatura,
                getattr(obra, "literatura_pais", "") or "",
                getattr(obra, "literatura_regiao", "") or "",
                getattr(obra, "autor_pais", "") or "",
            )
            if lit_compat is False:
                continue
            if lit_compat:
                score += 40
        if score <= 0:
            continue

        chave = m._chave_canonica_obra_busca(obra)
        bucket = por_obra.setdefault(
            chave,
            {
                "obras": {},
                "items": [],
                "score": 0,
                "match": {"titulo": False, "autor": False, "editora": False, "isbn": False},
                "literatura_match": False,
                "genero_match": False,
            },
        )
        bucket["obras"][obra.id] = obra
        bucket["items"].append((score, leituras_count, obra, ed, match))
        bucket["score"] = max(bucket["score"], score)
        bucket["literatura_match"] = bucket["literatura_match"] or bool(lit_compat)
        bucket["genero_match"] = bucket["genero_match"] or bool(genero_compat)
        for key, value in match.items():
            bucket["match"][key] = bucket["match"][key] or value

    docs = []
    for bucket in por_obra.values():
        def ed_sort(item):
            score, leituras_count, _obra, ed, _match = item
            editora_hit = editora_norm and editora_norm in m._normalizar_busca(ed.editora)
            return (
                bool(editora_hit),
                bool(ed.capa_url),
                bool(ed.isbn),
                m._idioma_portugues(ed.idioma),
                ed.ano or 0,
                ed.id or 0,
                score,
                leituras_count,
            )

        items = sorted(bucket["items"], key=ed_sort, reverse=True)
        _best_score, best_leituras, obra, ed, best_match = items[0]
        obras_stats = {
            item_obra.id: {
                "obra": item_obra,
                "edicoes": 0,
                "capas": 0,
                "isbns": 0,
                "leituras": 0,
                "score": 0,
            }
            for _score, _leituras, item_obra, _item_ed, _match in items
        }
        for item_score, item_leituras, item_obra, item_ed, _match in items:
            stats = obras_stats[item_obra.id]
            stats["edicoes"] += 1
            stats["capas"] += 1 if item_ed.capa_url else 0
            stats["isbns"] += 1 if item_ed.isbn else 0
            stats["leituras"] += item_leituras
            stats["score"] = max(stats["score"], item_score)

        def obra_principal_sort(stats):
            principal = stats["obra"]
            titulo_score = m._titulo_exibicao_score(principal.titulo, principal.autor)
            return (
                titulo_score[0],
                titulo_score[1],
                0 if principal.autor else 1,
                -stats["edicoes"],
                -stats["capas"],
                -stats["isbns"],
                -stats["leituras"],
                -(principal.id or 0),
            )

        obra_principal = sorted(obras_stats.values(), key=obra_principal_sort)[0]["obra"]
        edicoes_docs = []
        assinaturas_edicoes = set()
        for _score, item_leituras, item_obra, item_ed, _match in items:
            assinatura = (
                m._titulo_canonico_busca(item_obra.titulo, item_obra.autor),
                m._normalizar_busca(item_ed.editora),
                item_ed.ano or "",
                m.normalizar_isbn(item_ed.isbn or ""),
                item_ed.ol_edition_key or "",
            )
            if assinatura in assinaturas_edicoes:
                continue
            assinaturas_edicoes.add(assinatura)
            edicoes_docs.append(m._edicao_doc(item_obra, item_ed, item_leituras))

        edicoes = edicoes_docs[:5]
        ed_doc = m._edicao_doc(obra, ed, best_leituras)
        social = {"leituras": 0, "criticas": 0, "lendo": 0, "notas": []}
        for ed_id in {item_ed.id for _s, _l, _o, item_ed, _m in items if item_ed.id is not None}:
            stats = social_por_edicao.get(ed_id)
            if not stats:
                continue
            social["leituras"] += stats["leituras"]
            social["criticas"] += stats["criticas"]
            social["lendo"] += stats["lendo"]
            social["notas"].extend(stats["notas"])

        doc = {
            "work_key": obra_principal.ol_work_key,
            "titulo": obra_principal.titulo,
            "autor": obra_principal.autor,
            "descricao": getattr(obra_principal, "descricao", "") or "",
            "generos": m.generos_obra(obra_principal),
            "idioma_original": obra_principal.idioma_original,
            "ano": obra_principal.ano,
            "tem_pt": m._idioma_portugues(ed.idioma),
            "capa_url": ed.capa_url,
            "isbn_match": best_match["isbn"],
            "edicao_isbn": ed_doc,
            "edicoes": edicoes,
            "edicoes_encontradas": len(edicoes_docs),
            "chave_obra": m.chave_obra_canonica(obra_principal.titulo, obra_principal.autor),
            "leituras_count": social["leituras"],
            "criticas_publicas": social["criticas"],
            "lendo_agora_count": social["lendo"],
            "nota_media": round(sum(social["notas"]) / len(social["notas"]), 2) if social["notas"] else None,
            "_fonte": "local",
            "_ranking_score": bucket["score"],
            "_match": bucket["match"],
        }
        for campo in ("autor_pais", "autor_nacionalidade", "literatura_pais", "literatura_regiao"):
            valor = (getattr(obra_principal, campo, "") or "").strip()
            if valor:
                doc[campo] = valor
        if literatura:
            doc["_literatura_match"] = bucket["literatura_match"]
        if genero:
            doc["_genero_match"] = bucket["genero_match"]
        docs.append(doc)

    ordenados = sorted(
        docs,
        key=lambda d: (
            d.get("_ranking_score") or 0,
            d.get("edicao_isbn", {}).get("leituras_count") or 0,
        ),
        reverse=True,
    )
    if not busca_textual:
        return ordenados[:30]
    autor_hits = sum(1 for d in ordenados if (d.get("_match") or {}).get("autor"))
    titulo_hits = sum(1 for d in ordenados if (d.get("_match") or {}).get("titulo"))
    return ordenados[: 30 if autor_hits > titulo_hits else 15]


class SearchQuerySanitizerMiddleware:
    """Limpa apenas o parâmetro ``q`` da rota de busca, preservando os filtros."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/api/buscar":
            pairs = parse_qsl(scope.get("query_string", b"").decode("utf-8"), keep_blank_values=True)
            changed = False
            cleaned = []
            for key, value in pairs:
                if key == "q":
                    new_value = sanitize_search_query(value)
                    changed = changed or new_value != value
                    value = new_value
                cleaned.append((key, value))
            if changed:
                scope = dict(scope)
                scope["query_string"] = urlencode(cleaned, doseq=True).encode("utf-8")
        await self.app(scope, receive, send)


def install() -> None:
    m._buscar_catalogo_local = buscar_catalogo_local
    # Invalida respostas antigas (por exemplo, os cinco resultados de Dostoievski)
    # sem apagar registros manualmente do banco.
    busca_module._CACHE_SCHEMA_VERSION = max(getattr(busca_module, "_CACHE_SCHEMA_VERSION", 0), 3)

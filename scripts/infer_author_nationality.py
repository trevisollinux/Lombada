#!/usr/bin/env python3
"""
Infere a nacionalidade dos autores do catálogo e preenche os metadados de
origem das obras (autor_pais / autor_nacionalidade / literatura_pais /
literatura_regiao) usando a Wikidata.

Motivação: os filtros de literatura da busca ("brasileira", "russa", …) só
afunilam obras que têm o país catalogado. Como esses campos vêm quase sempre
vazios, o filtro-só de origem devolve pouca coisa. Este script preenche o país
a partir da cidadania do autor (P27 na Wikidata), melhorando TODOS os filtros
de origem de uma vez, não só o brasileiro.

Conservador de propósito (o modelo pede "só preencher com dado confiável"):
- só grava quando acha uma entidade que é humano (P31 = Q5) e cuja cidadania
  (P27) casa com um dos países das literaturas canônicas do app;
- prefere candidatos com ocupação de escritor/poeta/etc. (P106);
- autores com país já preenchido são pulados (a menos de NATIONALITY_OVERWRITE);
- resultados por autor são cacheados em memória (o catálogo repete muito autor).

Config por variáveis de ambiente:
- DATABASE_URL        conexão do catálogo (SQLite/Postgres — a mesma do app).
- NATIONALITY_LIMIT   máx. de obras a processar nesta rodada (default 500).
- NATIONALITY_OVERWRITE  "true" reprocessa obras que já têm autor_pais (default false).
- NATIONALITY_DRY_RUN "true" não grava nada, só mostra o que faria (default false).
- NATIONALITY_SLEEP   segundos entre chamadas à Wikidata (default 0.34).
- WIKIDATA_LANGS      idiomas de busca, separados por vírgula (default "pt,en").
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import engine, Obra  # noqa: E402
# LITERATURAS_CANONICAS é a fonte única de verdade país→região. Importar de main
# roda o setup do app (igual aos testes), o que é aceitável num script pontual.
from main import LITERATURAS_CANONICAS  # noqa: E402


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_UA = {"User-Agent": "Lombada/2.0 (catalogo; github.com/trevisollinux/lombada)"}
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Propriedades e classes da Wikidata usadas aqui.
_P_INSTANCIA = "P31"        # instance of
_P_CIDADANIA = "P27"        # country of citizenship
_P_OCUPACAO = "P106"        # occupation
_Q_HUMANO = "Q5"
_Q_OCUPACOES_ESCRITA = {
    "Q36180",    # writer
    "Q49757",    # poet
    "Q6625963",  # novelist
    "Q214917",   # playwright
    "Q4853732",  # children's writer
    "Q11774202", # essayist
    "Q12144794", # short story writer
    "Q18814623", # autobiographer
    "Q1930187",  # journalist
    "Q3579035",  # screenwriter
    "Q182436",   # translator
}

# QID da Wikidata → país canônico do app. Inclui estados históricos comuns em
# literatura clássica (ex.: Império Russo/URSS para autores russos), para não
# perder Dostoiévski, Kafka, etc. Só mapeamos países que têm literatura canônica.
_WIKIDATA_QID_PAIS = {
    # Brasil
    "Q155": "Brasil", "Q217230": "Brasil",
    # Rússia (+ Império Russo, URSS, RSFS da Rússia)
    "Q159": "Rússia", "Q34266": "Rússia", "Q15180": "Rússia", "Q2184": "Rússia",
    # França (+ Reino da França, 3ª República)
    "Q142": "França", "Q70972": "França", "Q70802": "França", "Q71084": "França",
    # Argentina
    "Q414": "Argentina",
    # Japão (+ Império do Japão)
    "Q17": "Japão", "Q188712": "Japão",
    # Reino Unido (+ estados predecessores e nações constituintes)
    "Q145": "Reino Unido", "Q174193": "Reino Unido", "Q161885": "Reino Unido",
    "Q179876": "Reino Unido", "Q21": "Reino Unido", "Q22": "Reino Unido",
    "Q25": "Reino Unido", "Q26": "Reino Unido",
    # Estados Unidos
    "Q30": "Estados Unidos",
    # Alemanha (+ Império Alemão, Weimar, RDA/RFA, Reino da Prússia)
    "Q183": "Alemanha", "Q43287": "Alemanha", "Q41304": "Alemanha",
    "Q7318": "Alemanha", "Q16957": "Alemanha", "Q713750": "Alemanha",
    "Q27306": "Alemanha",
    # Itália (+ Reino da Itália)
    "Q38": "Itália", "Q172579": "Itália",
    # Portugal (+ Reino de Portugal)
    "Q45": "Portugal", "Q207272": "Portugal",
    # Espanha (+ Reino da Espanha / franquismo)
    "Q29": "Espanha", "Q29999": "Espanha", "Q102876": "Espanha",
}


def _pais_para_regiao() -> dict[str, str]:
    """país canônico → região, a partir da lista canônica do app."""
    mapa: dict[str, str] = {}
    for lit in LITERATURAS_CANONICAS:
        pais = (lit.get("pais") or "").strip()
        if pais:
            mapa[pais] = lit.get("regiao") or ""
    return mapa


def _pais_para_label() -> dict[str, str]:
    """país canônico → label da literatura (ex.: Brasil → 'brasileira')."""
    mapa: dict[str, str] = {}
    for lit in LITERATURAS_CANONICAS:
        pais = (lit.get("pais") or "").strip()
        if pais and lit.get("label"):
            mapa.setdefault(pais, lit["label"])
    return mapa


_PAIS_REGIAO = _pais_para_regiao()
_PAIS_LABEL = _pais_para_label()


def getenv_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default)).strip()))
    except ValueError:
        return default


def getenv_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y"}


def getenv_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default)).strip()))
    except ValueError:
        return default


def getenv_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _claim_qids(claims: dict, prop: str) -> list[str]:
    """QIDs alvo de uma propriedade (ignora snaks sem valor)."""
    qids: list[str] = []
    for claim in claims.get(prop, []) or []:
        snak = (claim or {}).get("mainsnak") or {}
        if snak.get("snaktype") != "value":
            continue
        value = ((snak.get("datavalue") or {}).get("value") or {})
        qid = value.get("id") if isinstance(value, dict) else None
        if qid:
            qids.append(qid)
    return qids


def _buscar_candidatos(client: httpx.Client, nome: str, langs: list[str]) -> list[str]:
    """QIDs candidatos para o nome do autor, tentando cada idioma até achar."""
    for lang in langs:
        try:
            r = client.get(WIKIDATA_API, params={
                "action": "wbsearchentities", "search": nome,
                "language": lang, "uselang": lang, "type": "item",
                "format": "json", "limit": 7,
            })
            r.raise_for_status()
            resultados = r.json().get("search") or []
        except Exception:
            resultados = []
        qids = [item.get("id") for item in resultados if item.get("id")]
        if qids:
            return qids
    return []


def _pais_do_autor(client: httpx.Client, nome: str, langs: list[str]) -> str:
    """País canônico do autor via Wikidata, ou '' se não der pra afirmar."""
    candidatos = _buscar_candidatos(client, nome, langs)
    if not candidatos:
        return ""
    try:
        r = client.get(WIKIDATA_API, params={
            "action": "wbgetentities", "ids": "|".join(candidatos[:7]),
            "props": "claims", "format": "json",
        })
        r.raise_for_status()
        entidades = r.json().get("entities") or {}
    except Exception:
        return ""

    fallback = ""  # humano com país, mesmo sem ocupação de escritor
    for qid in candidatos:            # respeita a ordem de relevância da busca
        claims = (entidades.get(qid) or {}).get("claims") or {}
        if _Q_HUMANO not in _claim_qids(claims, _P_INSTANCIA):
            continue
        paises = [_WIKIDATA_QID_PAIS[q] for q in _claim_qids(claims, _P_CIDADANIA)
                  if q in _WIKIDATA_QID_PAIS]
        if not paises:
            continue
        ocupacoes = set(_claim_qids(claims, _P_OCUPACAO))
        if ocupacoes & _Q_OCUPACOES_ESCRITA:
            return paises[0]          # escritor com país canônico: melhor evidência
        if not fallback:
            fallback = paises[0]
    return fallback


def _obras_alvo(s: Session, limite: int, overwrite: bool) -> list[Obra]:
    stmt = select(Obra).where(Obra.autor != "", Obra.autor.is_not(None))
    if not overwrite:
        stmt = stmt.where((Obra.autor_pais == "") | (Obra.autor_pais.is_(None)))
    stmt = stmt.order_by(Obra.id).limit(limite)
    return list(s.exec(stmt).all())


def main() -> int:
    limite = getenv_int("NATIONALITY_LIMIT", 500, minimum=1)
    overwrite = getenv_bool("NATIONALITY_OVERWRITE", False)
    dry_run = getenv_bool("NATIONALITY_DRY_RUN", False)
    pausa = getenv_float("NATIONALITY_SLEEP", 0.34, minimum=0.0)
    langs = getenv_list("WIKIDATA_LANGS", "pt,en")

    cache: dict[str, str] = {}
    atualizadas = pulos = achados = 0

    with Session(engine) as s:
        obras = _obras_alvo(s, limite, overwrite)
        print(f"obras a processar: {len(obras)} (overwrite={overwrite}, dry_run={dry_run})")
        with httpx.Client(timeout=_TIMEOUT, headers=_UA) as client:
            for obra in obras:
                nome = (obra.autor or "").strip()
                chave = nome.lower()
                if chave in cache:
                    pais = cache[chave]
                else:
                    pais = _pais_do_autor(client, nome, langs)
                    cache[chave] = pais
                    if pausa:
                        time.sleep(pausa)
                if not pais:
                    pulos += 1
                    continue
                achados += 1
                regiao = _PAIS_REGIAO.get(pais, "")
                label = _PAIS_LABEL.get(pais, "")
                print(f"  #{obra.id} {nome!r} → {pais}"
                      + (f" / {regiao}" if regiao else "")
                      + (f" [{obra.autor_pais}→]" if obra.autor_pais else ""))
                if dry_run:
                    continue
                obra.autor_pais = pais
                obra.autor_nacionalidade = label or obra.autor_nacionalidade
                obra.literatura_pais = pais
                obra.literatura_regiao = regiao
                s.add(obra)
                atualizadas += 1
            if not dry_run and atualizadas:
                s.commit()

    print(f"\nautores com país encontrado: {achados}  "
          f"| obras atualizadas: {atualizadas}  | sem país confiável: {pulos}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ninterrompido.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Erro na inferência de nacionalidade: {exc}", file=sys.stderr)
        raise SystemExit(1)

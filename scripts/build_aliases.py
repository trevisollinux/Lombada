#!/usr/bin/env python3
"""
Cresce data/aliases.json "aos poucos" a partir do catálogo.

Varre os autores de Obra, agrupa grafias parecidas (sobrenome dobrado +
similaridade) e PROPÕE novas variantes para os rótulos canônicos já
conhecidos — ou novos clusters quando vários autores parecidos não casam
com nenhum alias. Pega typos ("Dotoievski"), transliterações que o fold
não cobre e nomes em cirílico.

Uso:
  python scripts/build_aliases.py            # dry-run: imprime e grava data/aliases.proposed.json
  python scripts/build_aliases.py --apply    # funde as propostas em data/aliases.json

Env:
  DATABASE_URL   banco do catálogo (default: sqlite:///lombada.db, igual ao app).
  ALIAS_MIN_SIM  similaridade mínima p/ agrupar (default 0.86).
  ALIAS_MIN_LEN  tamanho mínimo do sobrenome considerado (default 5).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))

from fontes import (  # noqa: E402
    _sem_acento, _romanizar, _fold_sobrenome, _alias_de_tokens, _AUTOR_ALIASES,
)

ALIASES_PATH = AQUI / "data" / "aliases.json"
PROPOSED_PATH = AQUI / "data" / "aliases.proposed.json"
MIN_SIM = float(os.getenv("ALIAS_MIN_SIM", "0.86"))
MIN_LEN = int(os.getenv("ALIAS_MIN_LEN", "5"))


def _sobrenome_cru(autor: str) -> str:
    """Sobrenome dobrado SEM aplicar aliases (pra poder descobrir grafias novas)."""
    norm = _romanizar(_sem_acento(autor or ""))
    if not norm:
        return ""
    if "," in norm:
        cand = norm.split(",", 1)[0]
        return _fold_sobrenome((cand.split() or [""])[-1])
    toks = [t for t in re.split(r"[^a-z]+", norm) if t]
    return _fold_sobrenome(toks[-1] if toks else "")


def _autores_do_catalogo() -> dict[str, int]:
    """{autor_original: frequência} a partir da tabela Obra."""
    try:
        from sqlmodel import select, Session
        from models import engine, Obra
    except Exception as e:
        print(f"[aliases] não consegui importar o modelo do banco: {e}")
        return {}
    freq: dict[str, int] = defaultdict(int)
    try:
        with Session(engine) as s:
            for autor in s.exec(select(Obra.autor)).all():
                autor = (autor or "").strip() if isinstance(autor, str) else (autor[0] if autor else "")
                autor = (autor or "").strip()
                if autor and autor != "—":
                    freq[autor] += 1
    except Exception as e:
        print(f"[aliases] banco indisponível ({e}); rode com DATABASE_URL apontando pro catálogo.")
        return {}
    return dict(freq)


def _folds_por_canon() -> dict[str, set[str]]:
    return {canon: {_fold_sobrenome(v) for v in variantes}
            for canon, variantes in _AUTOR_ALIASES.items()}


def propor(autores: dict[str, int]) -> dict[str, set[str]]:
    """Retorna {canon: {sobrenomes_crus_novos}} a propor."""
    folds_canon = _folds_por_canon()

    # agrega sobrenomes crus → (frequência, exemplo de grafia original)
    crus: dict[str, dict] = {}
    for autor, n in autores.items():
        sob = _sobrenome_cru(autor)
        if len(sob) < MIN_LEN:
            continue
        b = crus.setdefault(sob, {"freq": 0, "exemplo": autor})
        b["freq"] += n
        if n > autores.get(b["exemplo"], 0):
            b["exemplo"] = autor

    propostas: dict[str, set[str]] = defaultdict(set)
    orfaos: list[str] = []
    for sob, info in crus.items():
        if _alias_de_tokens([sob]):          # já resolve pra um canon conhecido
            continue
        # tenta encaixar num canon existente por similaridade
        melhor, melhor_sim = None, 0.0
        for canon, folds in folds_canon.items():
            sim = max((SequenceMatcher(None, sob, f).ratio() for f in folds), default=0.0)
            if sim > melhor_sim:
                melhor, melhor_sim = canon, sim
        if melhor and melhor_sim >= MIN_SIM:
            propostas[melhor].add(sob)
        else:
            orfaos.append(sob)

    # clusters entre órfãos parecidos (autores novos com várias grafias)
    usados: set[str] = set()
    for i, a in enumerate(orfaos):
        if a in usados:
            continue
        grupo = {a}
        for b in orfaos[i + 1:]:
            if b in usados:
                continue
            if SequenceMatcher(None, a, b).ratio() >= MIN_SIM:
                grupo.add(b)
        if len(grupo) >= 2:
            canon = max(grupo, key=lambda x: crus[x]["freq"])
            propostas[canon] |= (grupo - {canon})
            usados |= grupo
    return {k: v for k, v in propostas.items() if v}


def aplicar(propostas: dict[str, set[str]]) -> None:
    dados = json.loads(ALIASES_PATH.read_text(encoding="utf-8")) if ALIASES_PATH.exists() else {}
    autores = dados.setdefault("autores", {})
    for canon, novos in propostas.items():
        lista = autores.setdefault(canon, [])
        existentes = {x.lower() for x in lista}
        for v in sorted(novos):
            if v not in existentes:
                lista.append(v)
        autores[canon] = sorted(dict.fromkeys(lista))
    ALIASES_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[aliases] {ALIASES_PATH} atualizado.")


def main() -> None:
    aplicar_flag = "--apply" in sys.argv
    autores = _autores_do_catalogo()
    if not autores:
        print("[aliases] nenhum autor lido do catálogo — nada a fazer.")
        return
    print(f"[aliases] {len(autores)} autores distintos no catálogo.")
    propostas = propor(autores)
    if not propostas:
        print("[aliases] nenhuma proposta nova (catálogo já consistente com os aliases).")
        return
    print("[aliases] propostas (revise antes de aplicar):")
    for canon, novos in sorted(propostas.items()):
        print(f"  {canon}: +{', '.join(sorted(novos))}")
    saida = {"autores": {k: sorted(v) for k, v in propostas.items()}}
    PROPOSED_PATH.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[aliases] propostas gravadas em {PROPOSED_PATH}")
    if aplicar_flag:
        aplicar(propostas)
    else:
        print("[aliases] dry-run. Rode de novo com --apply pra fundir em data/aliases.json.")


if __name__ == "__main__":
    main()

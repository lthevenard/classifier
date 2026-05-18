"""Heuristicas textuais para identificar estrutura normativa em materias do DOU."""

from __future__ import annotations

import re


_LEGAL_STRUCTURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("artigo", re.compile(r'^[^"]?Art(\s)?\.?\s', re.MULTILINE)),
    ("inciso", re.compile(r'^[^"]?(I|V|X|L|C)+\s', re.MULTILINE)),
    ("paragrafo", re.compile(r'^[^"]?\u00a7', re.MULTILINE)),
    (
        "paragrafo unico",
        re.compile(
            r'^[^"]?(par[a\u00e1]grafo)\s+([u\u00fa]nico)|P\.U\.',
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    ("alinea", re.compile(r'^[^"]?[a-z](\s)?\)', re.MULTILINE)),
)


def find_legal_structure(texto: str) -> str | None:
    """Retorna o primeiro marcador textual de estrutura legal encontrado.

    A heuristica foi incorporada a partir do script exploratorio
    `docs/projeto/arquivados/helpers.py`. Ela procura marcadores como
    artigos, incisos, paragrafos e alineas no inicio de linhas do texto.
    """

    for structure_name, pattern in _LEGAL_STRUCTURE_PATTERNS:
        if pattern.search(texto) is not None:
            return structure_name
    return None


def has_legal_structure(texto: str) -> bool:
    return find_legal_structure(texto) is not None


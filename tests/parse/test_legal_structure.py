from dou_classifier.parse.legal_structure import (
    find_legal_structure,
    has_legal_structure,
)


def test_find_legal_structure_detects_article_on_later_line():
    text = "PORTARIA TESTE\nArt. 1 Fica aprovado o regulamento."

    assert find_legal_structure(text) == "artigo"
    assert has_legal_structure(text)


def test_find_legal_structure_detects_paragraph_marker():
    assert find_legal_structure("Texto\n§ 1 O prazo e de 30 dias.") == "paragrafo"


def test_find_legal_structure_returns_none_without_marker():
    assert find_legal_structure("Despacho de mero expediente.") is None
    assert not has_legal_structure("Despacho de mero expediente.")


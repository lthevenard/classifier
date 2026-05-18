"""Script exploratorio arquivado.

A funcao `find_legal_structure` foi incorporada em
`src/dou_classifier/parse/legal_structure.py` sem as dependencias externas
que eram usadas por outras rotinas deste arquivo.
"""

import  elasticsearch
from elasticsearch import helpers as es_helpers
import urllib3
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import re

def find_legal_structure(texto: str) -> str:
    artigo = re.compile(r"^[^\"]?Art(\s)?\.?\s")
    inciso = re.compile(r"^[^\"]?(I|V|X|L|C)+\s")
    paragrafo = re.compile(r"^[^\"]?§")
    parag_unico = re.compile(r"^[^\"]?(par[áa]grafo)\s([úu]nico)|P\.U\.", re.IGNORECASE)
    alinea = re.compile(r"^[^\"]?[a-z](\s)?\)")

    if re.search(artigo, texto) is not None:
        return "artigo"
    elif re.search(inciso, texto) is not None:
        return "inciso"
    elif re.search(paragrafo, texto) is not None:
        return "paragrafo"
    elif re.search(parag_unico, texto) is not None:
        return "paragrafo unico"
    elif re.search(alinea, texto) is not None:
        return "alinea"

def remove_stopwords(text):
    stop_words = set(stopwords.words('portuguese'))
    stop_words.update(["art", "artigo", "paragrafo", "parágrafo", "inciso", "alinea", "alínea", "único", "unica", "única"])
    agencias = ["ANEEL", "ANVISA", "ANS", "ANTT", "ANA", "ANAC", "CVM", "ANTAQ", "ANP", "ANATEL", "ANM", "ANCINE", "BACEN"] 
    stop_words.update([agencia.lower() for agencia in agencias])
    word_tokens = word_tokenize(text)
    filtered_sentence = [w for w in word_tokens if not w in stop_words]
    return " ".join(filtered_sentence)

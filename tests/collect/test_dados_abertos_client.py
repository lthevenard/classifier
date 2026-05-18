from datetime import date

import pytest

from dou_classifier.collect.dados_abertos_client import (
    DadosAbertosClient,
    DadosAbertosResource,
    InvalidDadosAbertosSectionError,
    normalize_dados_abertos_section,
    normalize_dados_abertos_sections,
    parse_resource_code,
    resource_from_api,
)


class FakeResponse:
    def __init__(self, status_code, payload, url="https://dados.gov.br/api/test"):
        self.status_code = status_code
        self._payload = payload
        self.url = url

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requests.append(
            {"url": url, "params": params, "headers": headers, "timeout": timeout}
        )
        return self.responses.pop(0)


def test_normalize_dados_abertos_section_accepts_inlabs_aliases():
    assert normalize_dados_abertos_section("DO1") == "S01"
    assert normalize_dados_abertos_section("DO1E") == "S01"
    assert normalize_dados_abertos_sections(["DO1", "DO1E", "S02"]) == ["S01", "S02"]


def test_normalize_dados_abertos_section_rejects_unknown_section():
    with pytest.raises(InvalidDadosAbertosSectionError):
        normalize_dados_abertos_section("DO4")


def test_parse_resource_code_from_portal_filename():
    assert parse_resource_code("https://example.test/S01052025/file") == (
        "S01",
        date(2025, 5, 1),
    )


def test_resource_from_api_uses_url_code_and_dataset_metadata():
    resource = resource_from_api(
        {
            "id": "resource-id",
            "name": "Publicacoes da Secao 1 - Maio de 2025",
            "format": "zip+xml",
            "url": "https://www.in.gov.br/documents/20181/1/S01052025/uuid",
        },
        {"name": "diario-oficial-da-uniao-materias-publicadas-em-2025"},
    )

    assert resource == DadosAbertosResource(
        month=date(2025, 5, 1),
        section="S01",
        url="https://www.in.gov.br/documents/20181/1/S01052025/uuid",
        name="Publicacoes da Secao 1 - Maio de 2025",
        resource_id="resource-id",
        dataset_name="diario-oficial-da-uniao-materias-publicadas-em-2025",
        format="zip+xml",
    )


def test_client_finds_monthly_resource_from_year_dataset():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "data": {
                        "name": "diario-oficial-da-uniao-materias-publicadas-em-2025",
                        "resources": [
                            {
                                "id": "jan-s1",
                                "name": "Publicacoes da Secao 1 - Janeiro de 2025",
                                "format": "zip+xml",
                                "url": "https://www.in.gov.br/documents/20181/1/S01012025/uuid",
                            }
                        ],
                    }
                },
            )
        ]
    )
    client = DadosAbertosClient(session=session)

    resource = client.find_resource(date(2025, 1, 1), "DO1")

    assert resource.code == "S01012025"
    assert resource.url.endswith("/S01012025/uuid")
    assert session.requests[0]["headers"]["Accept"] == "application/json"


def test_client_sends_token_with_official_header_name():
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "data": {
                        "name": "diario-oficial-da-uniao-materias-publicadas-em-2025",
                        "resources": [],
                    }
                },
            )
        ]
    )
    client = DadosAbertosClient(session=session, token="Bearer abc")

    client.get_dataset("diario-oficial-da-uniao-materias-publicadas-em-2025")

    assert session.requests[0]["headers"]["chave-api-dados-abertos"] == "abc"

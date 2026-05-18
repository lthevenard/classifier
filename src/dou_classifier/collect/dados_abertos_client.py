"""Cliente para o catalogo do Portal Brasileiro de Dados Abertos."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urljoin

import requests
from requests.exceptions import JSONDecodeError


DEFAULT_DADOS_GOV_BR_API_BASE = "https://dados.gov.br/dados/api/publico"
DEFAULT_DADOS_GOV_BR_TOKEN_ENV = "DADOS_GOV_BR_API_TOKEN"
DADOS_GOV_BR_TOKEN_HEADER = "chave-api-dados-abertos"
ALLOWED_DADOS_ABERTOS_SECTIONS = {"S01", "S02", "S03"}
SECTION_ALIASES = {
    "1": "S01",
    "01": "S01",
    "DO1": "S01",
    "DO1E": "S01",
    "S1": "S01",
    "S01": "S01",
    "SECAO1": "S01",
    "SECAO01": "S01",
    "SECAO 1": "S01",
    "SECAO 01": "S01",
    "2": "S02",
    "02": "S02",
    "DO2": "S02",
    "S2": "S02",
    "S02": "S02",
    "SECAO2": "S02",
    "SECAO02": "S02",
    "SECAO 2": "S02",
    "SECAO 02": "S02",
    "3": "S03",
    "03": "S03",
    "DO3": "S03",
    "S3": "S03",
    "S03": "S03",
    "SECAO3": "S03",
    "SECAO03": "S03",
    "SECAO 3": "S03",
    "SECAO 03": "S03",
}

RESOURCE_CODE_RE = re.compile(r"\b(S0[123])(\d{2})(\d{4})\b", re.IGNORECASE)
MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


class DadosAbertosError(RuntimeError):
    """Erro base do cliente do Portal de Dados Abertos."""


class DadosAbertosAuthenticationError(DadosAbertosError):
    """Erro levantado quando a API exige token do Portal."""


class DadosAbertosDatasetNotFoundError(DadosAbertosError):
    """Erro levantado quando o conjunto anual do DOU nao e encontrado."""


class DadosAbertosResourceNotFoundError(DadosAbertosError):
    """Erro levantado quando o recurso mensal/secao nao e encontrado."""


class InvalidDadosAbertosSectionError(ValueError):
    """Erro levantado quando a secao solicitada nao e suportada."""


@dataclass(frozen=True)
class DadosAbertosResource:
    month: date
    section: str
    url: str
    name: str
    resource_id: str | None
    dataset_name: str | None
    format: str | None

    @property
    def code(self) -> str:
        return f"{self.section}{self.month:%m%Y}"


def normalize_dados_abertos_section(section: str) -> str:
    key = strip_accents(" ".join(section.strip().upper().split()))
    normalized = SECTION_ALIASES.get(key)
    if normalized is None:
        allowed = ", ".join(sorted(ALLOWED_DADOS_ABERTOS_SECTIONS))
        raise InvalidDadosAbertosSectionError(
            f"Secao invalida para o Portal de Dados Abertos: {section!r}. "
            f"Use uma de: {allowed}."
        )
    return normalized


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_dados_abertos_sections(sections: list[str]) -> list[str]:
    normalized: list[str] = []
    for section in sections:
        value = normalize_dados_abertos_section(section)
        if value not in normalized:
            normalized.append(value)
    return normalized


def dataset_slug_candidates(year: int) -> list[str]:
    candidates = [f"diario-oficial-da-uniao-materias-publicadas-em-{year}"]
    if year == 2017:
        candidates.append("diario-oficial-da-uniao")
    return candidates


class DadosAbertosClient:
    """Cliente para localizar recursos mensais do DOU no catalogo dados.gov.br."""

    def __init__(
        self,
        api_base_url: str = DEFAULT_DADOS_GOV_BR_API_BASE,
        token: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/") + "/"
        self.token = token
        self.session = session or requests.Session()
        self._year_cache: dict[int, dict[str, Any]] = {}

    def find_resource(self, month: date, section: str, timeout: int = 60) -> DadosAbertosResource:
        normalized_section = normalize_dados_abertos_section(section)
        dataset = self.find_year_dataset(month.year, timeout=timeout)
        resources = resources_from_dataset(dataset)
        for resource in resources:
            parsed = resource_from_api(resource, dataset)
            if parsed and parsed.month == month and parsed.section == normalized_section:
                return parsed

        raise DadosAbertosResourceNotFoundError(
            f"Nao encontrei recurso {normalized_section}{month:%m%Y} no catalogo."
        )

    def find_year_dataset(self, year: int, timeout: int = 60) -> dict[str, Any]:
        if year in self._year_cache:
            return self._year_cache[year]

        for slug in dataset_slug_candidates(year):
            try:
                dataset = self.get_dataset(slug, timeout=timeout)
                self._year_cache[year] = dataset
                return dataset
            except DadosAbertosDatasetNotFoundError:
                continue

        for item in self.search_datasets("Diario Oficial da Uniao", timeout=timeout):
            title = str(item.get("title") or item.get("titulo") or "")
            name = str(item.get("name") or item.get("nome") or "")
            if str(year) in title or str(year) in name:
                identifiers = [
                    str(item.get("id") or ""),
                    name,
                ]
                for slug in [identifier for identifier in identifiers if identifier]:
                    try:
                        dataset = self.get_dataset(slug, timeout=timeout)
                        self._year_cache[year] = dataset
                        return dataset
                    except DadosAbertosDatasetNotFoundError:
                        continue

        raise DadosAbertosDatasetNotFoundError(
            f"Nao encontrei conjunto de dados do DOU para {year}."
        )

    def get_dataset(self, slug: str, timeout: int = 60) -> dict[str, Any]:
        paths = [
            f"conjuntos-dados/{slug}",
        ]
        last_error: DadosAbertosDatasetNotFoundError | None = None
        for path in paths:
            try:
                data = self._get_json(path, timeout=timeout)
            except DadosAbertosDatasetNotFoundError as exc:
                last_error = exc
                continue
            return unwrap_dataset_payload(data)

        if last_error is not None:
            raise last_error
        raise DadosAbertosDatasetNotFoundError(f"Conjunto de dados nao encontrado: {slug}")

    def search_datasets(
        self,
        query: str,
        timeout: int = 60,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            params = {
                "nomeConjuntoDados": query,
                "pagina": page,
            }
            data = self._get_json("conjuntos-dados", params=params, timeout=timeout)
            page_items = unwrap_search_payload(data)
            if not page_items:
                break
            items.extend(page_items)
        return items

    def _get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> Any:
        headers = {"Accept": "application/json", "User-Agent": "dou-classifier/0.1"}
        if self.token:
            headers[DADOS_GOV_BR_TOKEN_HEADER] = self.token.removeprefix("Bearer ").strip()

        response = self.session.get(
            urljoin(self.api_base_url, path),
            params=params,
            headers=headers,
            timeout=timeout,
        )

        if response.status_code == 401:
            raise DadosAbertosAuthenticationError(
                "A API do Portal de Dados Abertos exigiu token no header "
                f"{DADOS_GOV_BR_TOKEN_HEADER}. "
                f"Configure {DEFAULT_DADOS_GOV_BR_TOKEN_ENV} ou informe --api-token-env."
            )
        if response.status_code == 404:
            raise DadosAbertosDatasetNotFoundError(
                f"Recurso do catalogo nao encontrado: {response.url}"
            )
        response.raise_for_status()

        try:
            data = response.json()
        except JSONDecodeError as exc:
            raise DadosAbertosDatasetNotFoundError(
                f"Resposta nao JSON do catalogo: {response.url}"
            ) from exc
        if isinstance(data, dict) and data.get("success") is False:
            error = data.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else None
            raise DadosAbertosDatasetNotFoundError(
                message or f"Resposta sem sucesso do catalogo: {response.url}"
            )
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            raise DadosAbertosError(f"Resposta JSON inesperada do catalogo: {response.url}")
        return data


def unwrap_dataset_payload(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("result", "conjuntoDados", "conjunto_dados", "data"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return data


def unwrap_search_payload(data: dict[str, Any]) -> list[dict[str, Any]]:
    current: Any = data
    for key in ("result", "data", "content", "items", "results"):
        if isinstance(current, dict) and key in current:
            current = current[key]
            if isinstance(current, list):
                return [item for item in current if isinstance(item, dict)]

    if isinstance(current, list):
        return [item for item in current if isinstance(item, dict)]
    return []


def resources_from_dataset(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("resources", "recursos"):
        value = dataset.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    for key in ("conjuntoDados", "conjunto_dados", "data", "result"):
        value = dataset.get(key)
        if isinstance(value, dict):
            resources = resources_from_dataset(value)
            if resources:
                return resources
    return []


def resource_from_api(
    resource: dict[str, Any],
    dataset: dict[str, Any],
) -> DadosAbertosResource | None:
    url = resource_text(resource, "url", "link", "linkAcesso", "link_acesso")
    name = resource_text(resource, "name", "nome", "title", "titulo")
    code_text = " ".join(part for part in (url, name) if part)
    parsed = parse_resource_code(code_text)
    if parsed is None or not url:
        return None

    section, month = parsed
    dataset_name = resource_text(dataset, "name", "nome", "title", "titulo")
    return DadosAbertosResource(
        month=month,
        section=section,
        url=url,
        name=name or f"{section}{month:%m%Y}",
        resource_id=resource_text(resource, "id"),
        dataset_name=dataset_name,
        format=resource_text(resource, "format", "formato"),
    )


def resource_text(resource: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = resource.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def parse_resource_code(value: str) -> tuple[str, date] | None:
    match = RESOURCE_CODE_RE.search(value)
    if match:
        section = match.group(1).upper()
        month = int(match.group(2))
        year = int(match.group(3))
        try:
            return section, date(year, month, 1)
        except ValueError:
            return None

    normalized_value = strip_accents(value.lower())
    name_match = re.search(r"secao\s+([123])", normalized_value, flags=re.IGNORECASE)
    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", value)
    if not name_match or not year_match:
        return None

    month = next(
        (
            month_number
            for month_name, month_number in MONTHS_PT.items()
            if month_name in normalized_value
        ),
        None,
    )
    if month is None:
        return None

    return f"S0{name_match.group(1)}", date(int(year_match.group(1)), month, 1)

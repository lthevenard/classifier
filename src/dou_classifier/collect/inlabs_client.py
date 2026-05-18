"""Cliente HTTP para o servico oficial INLABS da Imprensa Nacional."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import requests


LOGIN_URL = "https://inlabs.in.gov.br/logar.php"
DOWNLOAD_BASE_URL = "https://inlabs.in.gov.br/index.php"
ORIGIN_HEADER = "736372697074"
ALLOWED_XML_SECTIONS = {"DO1", "DO1E"}


class InlabsError(RuntimeError):
    """Erro base do cliente INLABS."""


class InlabsAuthenticationError(InlabsError):
    """Erro de autenticacao no INLABS."""


class InvalidSectionError(ValueError):
    """Erro levantado quando a secao solicitada nao e suportada."""


@dataclass(frozen=True)
class InlabsResource:
    publication_date: date
    section: str
    filename: str
    url: str


def normalize_section(section: str) -> str:
    normalized = section.strip().upper()
    if normalized not in ALLOWED_XML_SECTIONS:
        allowed = ", ".join(sorted(ALLOWED_XML_SECTIONS))
        raise InvalidSectionError(f"Secao invalida: {section!r}. Use uma de: {allowed}.")
    return normalized


def build_resource(
    publication_date: date,
    section: str,
    download_base_url: str = DOWNLOAD_BASE_URL,
) -> InlabsResource:
    normalized_section = normalize_section(section)
    date_text = publication_date.isoformat()
    filename = f"{date_text}-{normalized_section}.zip"
    url = f"{download_base_url}?p={date_text}&dl={filename}"
    return InlabsResource(
        publication_date=publication_date,
        section=normalized_section,
        filename=filename,
        url=url,
    )


class InlabsClient:
    """Sessao autenticada para baixar ZIPs XML do INLABS."""

    def __init__(
        self,
        session: requests.Session | None = None,
        login_url: str = LOGIN_URL,
        download_base_url: str = DOWNLOAD_BASE_URL,
    ) -> None:
        self.session = session or requests.Session()
        self.login_url = login_url
        self.download_base_url = download_base_url

    def login(self, email: str, password: str, timeout: int = 60) -> None:
        payload = {"email": email, "password": password}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "origem": ORIGIN_HEADER,
        }
        response = self.session.post(
            self.login_url,
            data=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()

        if not self.is_authenticated:
            raise InlabsAuthenticationError(
                "Falha ao autenticar no INLABS: cookie de sessao nao foi recebido."
            )

    @property
    def is_authenticated(self) -> bool:
        return bool(self.session.cookies.get("inlabs_session_cookie"))

    def resource_for(self, publication_date: date, section: str) -> InlabsResource:
        return build_resource(publication_date, section, self.download_base_url)

    def get_zip(
        self,
        publication_date: date,
        section: str,
        timeout: int = 120,
    ) -> requests.Response:
        resource = self.resource_for(publication_date, section)
        headers = {"origem": ORIGIN_HEADER}
        response = self.session.get(
            resource.url,
            headers=headers,
            timeout=timeout,
            stream=True,
            allow_redirects=True,
        )
        return response

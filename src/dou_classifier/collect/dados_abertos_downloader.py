"""Download e extracao dos ZIPs mensais do DOU catalogados no dados.gov.br."""

from __future__ import annotations

import time
import zipfile
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from dou_classifier.collect.checksums import sha256_file
from dou_classifier.collect.dados_abertos_client import DadosAbertosResource
from dou_classifier.collect.extract import extract_xml_files
from dou_classifier.collect.manifest import DownloadRecord, append_record, utc_now
from dou_classifier.collect.paths import (
    extracted_dados_abertos_dir,
    raw_dados_abertos_zip_path,
)


CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class DadosAbertosCollectionResult:
    month: date
    section: str
    result: str
    local_path: Path
    status_code: int | None
    message: str | None = None
    extracted_files: int | None = None


def download_dados_abertos_resource(
    resource: DadosAbertosResource,
    output_dir: Path,
    manifest_path: Path,
    force: bool = False,
    extract: bool = True,
    max_retries: int = 3,
    timeout: int = 120,
    sleep_seconds: float = 0.0,
    retry_backoff: float = 5.0,
    session: requests.Session | None = None,
) -> DadosAbertosCollectionResult:
    """Baixa um ZIP mensal do Portal de Dados Abertos e registra manifesto."""

    target_path = raw_dados_abertos_zip_path(output_dir, resource.month, resource.section)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and not force and zipfile.is_zipfile(target_path):
        file_size = target_path.stat().st_size
        file_hash = sha256_file(target_path)
        extracted_count = _extract_if_requested(
            output_dir=output_dir,
            month=resource.month,
            section=resource.section,
            zip_path=target_path,
            extract=extract,
            force=False,
        )
        append_record(
            manifest_path,
            DownloadRecord(
                publication_date=resource.month,
                section=resource.section,
                url=resource.url,
                local_path=str(target_path),
                status_code=None,
                bytes=file_size,
                sha256=file_hash,
                attempted_at=utc_now(),
                attempt=0,
                result="already_exists",
                message="Arquivo mensal local valido ja existia.",
                extracted_files=extracted_count,
            ),
        )
        return DadosAbertosCollectionResult(
            month=resource.month,
            section=resource.section,
            result="already_exists",
            local_path=target_path,
            status_code=None,
            message="Arquivo mensal local valido ja existia.",
            extracted_files=extracted_count,
        )

    http = session or requests.Session()
    attempts = max(1, max_retries)
    last_error: str | None = None

    for attempt in range(1, attempts + 1):
        response: requests.Response | None = None
        try:
            response = http.get(
                resource.url,
                headers={"User-Agent": "dou-classifier/0.1"},
                stream=True,
                timeout=timeout,
                allow_redirects=True,
            )
            result = _handle_response(
                response=response,
                resource=resource,
                output_dir=output_dir,
                target_path=target_path,
                manifest_path=manifest_path,
                attempt=attempt,
                extract=extract,
                force=force,
            )
            if result.result in {"downloaded", "not_found"}:
                return result
            last_error = result.message
            retry_after = _retry_after_seconds(response)
        except (requests.RequestException, OSError, zipfile.BadZipFile) as exc:
            last_error = str(exc)
            retry_after = None
            append_record(
                manifest_path,
                DownloadRecord(
                    publication_date=resource.month,
                    section=resource.section,
                    url=resource.url,
                    local_path=str(target_path),
                    status_code=getattr(response, "status_code", None),
                    bytes=None,
                    sha256=None,
                    attempted_at=utc_now(),
                    attempt=attempt,
                    result="failed",
                    message=last_error,
                    extracted_files=None,
                ),
            )

        if attempt < attempts:
            delay = _retry_delay_seconds(
                attempt=attempt,
                base_delay=retry_backoff,
                minimum_delay=sleep_seconds,
                retry_after=retry_after,
            )
            if delay > 0:
                time.sleep(delay)

    return DadosAbertosCollectionResult(
        month=resource.month,
        section=resource.section,
        result="failed",
        local_path=target_path,
        status_code=None,
        message=last_error,
        extracted_files=None,
    )


def _handle_response(
    response: requests.Response,
    resource: DadosAbertosResource,
    output_dir: Path,
    target_path: Path,
    manifest_path: Path,
    attempt: int,
    extract: bool,
    force: bool,
) -> DadosAbertosCollectionResult:
    status_code = response.status_code

    if status_code == 404:
        append_record(
            manifest_path,
            DownloadRecord(
                publication_date=resource.month,
                section=resource.section,
                url=resource.url,
                local_path=str(target_path),
                status_code=status_code,
                bytes=None,
                sha256=None,
                attempted_at=utc_now(),
                attempt=attempt,
                result="not_found",
                message="Arquivo mensal nao encontrado na URL catalogada.",
                extracted_files=None,
            ),
        )
        return DadosAbertosCollectionResult(
            month=resource.month,
            section=resource.section,
            result="not_found",
            local_path=target_path,
            status_code=status_code,
            message="Arquivo mensal nao encontrado na URL catalogada.",
        )

    if status_code != 200:
        message = f"Resposta HTTP inesperada: {status_code}."
        append_record(
            manifest_path,
            DownloadRecord(
                publication_date=resource.month,
                section=resource.section,
                url=resource.url,
                local_path=str(target_path),
                status_code=status_code,
                bytes=None,
                sha256=None,
                attempted_at=utc_now(),
                attempt=attempt,
                result="failed",
                message=message,
                extracted_files=None,
            ),
        )
        return DadosAbertosCollectionResult(
            month=resource.month,
            section=resource.section,
            result="failed",
            local_path=target_path,
            status_code=status_code,
            message=message,
        )

    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with temp_path.open("wb") as file_obj:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                file_obj.write(chunk)

    if not zipfile.is_zipfile(temp_path):
        temp_path.unlink(missing_ok=True)
        message = "Resposta HTTP 200 nao continha um ZIP valido."
        append_record(
            manifest_path,
            DownloadRecord(
                publication_date=resource.month,
                section=resource.section,
                url=resource.url,
                local_path=str(target_path),
                status_code=status_code,
                bytes=None,
                sha256=None,
                attempted_at=utc_now(),
                attempt=attempt,
                result="failed",
                message=message,
                extracted_files=None,
            ),
        )
        return DadosAbertosCollectionResult(
            month=resource.month,
            section=resource.section,
            result="failed",
            local_path=target_path,
            status_code=status_code,
            message=message,
        )

    temp_path.replace(target_path)
    file_size = target_path.stat().st_size
    file_hash = sha256_file(target_path)
    extracted_count = _extract_if_requested(
        output_dir=output_dir,
        month=resource.month,
        section=resource.section,
        zip_path=target_path,
        extract=extract,
        force=force,
    )
    append_record(
        manifest_path,
        DownloadRecord(
            publication_date=resource.month,
            section=resource.section,
            url=resource.url,
            local_path=str(target_path),
            status_code=status_code,
            bytes=file_size,
            sha256=file_hash,
            attempted_at=utc_now(),
            attempt=attempt,
            result="downloaded",
            message=f"Arquivo mensal baixado com sucesso: {resource.name}.",
            extracted_files=extracted_count,
        ),
    )
    return DadosAbertosCollectionResult(
        month=resource.month,
        section=resource.section,
        result="downloaded",
        local_path=target_path,
        status_code=status_code,
        message="Arquivo mensal baixado com sucesso.",
        extracted_files=extracted_count,
    )


def _extract_if_requested(
    output_dir: Path,
    month: date,
    section: str,
    zip_path: Path,
    extract: bool,
    force: bool,
) -> int | None:
    if not extract:
        return None

    return extract_xml_files(
        zip_path=zip_path,
        target_dir=extracted_dados_abertos_dir(output_dir, month, section),
        force=force,
    )


def _retry_after_seconds(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    return max(0.0, retry_at.timestamp() - time.time())


def _retry_delay_seconds(
    attempt: int,
    base_delay: float,
    minimum_delay: float,
    retry_after: float | None,
) -> float:
    backoff_delay = max(0.0, base_delay) * (2 ** max(0, attempt - 1))
    delay = max(0.0, minimum_delay, backoff_delay)
    if retry_after is not None:
        delay = max(delay, retry_after)
    return delay

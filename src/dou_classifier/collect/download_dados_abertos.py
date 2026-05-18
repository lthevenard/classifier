"""CLI para baixar XMLs mensais do DOU pelo Portal de Dados Abertos."""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from pathlib import Path

from dou_classifier.collect.dados_abertos_client import (
    DEFAULT_DADOS_GOV_BR_API_BASE,
    DEFAULT_DADOS_GOV_BR_TOKEN_ENV,
    DadosAbertosAuthenticationError,
    DadosAbertosClient,
    DadosAbertosDatasetNotFoundError,
    DadosAbertosResourceNotFoundError,
    normalize_dados_abertos_sections,
)
from dou_classifier.collect.dados_abertos_downloader import (
    download_dados_abertos_resource,
)
from dou_classifier.collect.date_ranges import iter_months, parse_date
from dou_classifier.collect.paths import default_dados_abertos_manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Baixa arquivos XML mensais do DOU catalogados no Portal de Dados Abertos."
    )
    parser.add_argument("--start-date", required=True, help="Data inicial: YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Data final: YYYY-MM-DD.")
    parser.add_argument(
        "--sections",
        nargs="+",
        default=["S01"],
        help=(
            "Secoes mensais do Portal. Use S01 para a Secao 1. "
            "Aliases como DO1 e DO1E sao normalizados para S01."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Diretorio raiz para dados brutos, extraidos e manifesto.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help=(
            "Caminho do manifesto JSONL. Padrao: "
            "<output-dir>/manifests/dados_abertos_downloads.jsonl."
        ),
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_DADOS_GOV_BR_API_BASE,
        help="Base da API do catalogo do Portal de Dados Abertos.",
    )
    parser.add_argument(
        "--api-token-env",
        default=DEFAULT_DADOS_GOV_BR_TOKEN_ENV,
        help="Variavel de ambiente que contem o token Bearer do dados.gov.br.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Baixa novamente arquivos existentes e reextrai XMLs.",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Nao extrai os XMLs dos ZIPs baixados.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Pausa em segundos entre downloads mensais.",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=5.0,
        help="Pausa base, em segundos, para retentativas com backoff exponencial.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Numero maximo de tentativas por arquivo.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout HTTP por requisicao, em segundos.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Localiza os recursos no catalogo, mas nao baixa os ZIPs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)
        months = list(iter_months(start_date, end_date))
        sections = normalize_dados_abertos_sections(args.sections)
    except ValueError as exc:
        parser.error(str(exc))

    manifest_path = args.manifest_path or default_dados_abertos_manifest_path(args.output_dir)
    token = os.getenv(args.api_token_env)
    client = DadosAbertosClient(api_base_url=args.api_base_url, token=token)
    extract = not args.no_extract
    summary: Counter[str] = Counter()

    try:
        resources = [
            client.find_resource(month=month, section=section, timeout=args.timeout)
            for month in months
            for section in sections
        ]
    except DadosAbertosAuthenticationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (DadosAbertosDatasetNotFoundError, DadosAbertosResourceNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.dry_run:
        for resource in resources:
            print(f"{resource.code}: {resource.name} -> {resource.url}")
        return 0

    for index, resource in enumerate(resources):
        result = download_dados_abertos_resource(
            resource=resource,
            output_dir=args.output_dir,
            manifest_path=manifest_path,
            force=args.force,
            extract=extract,
            max_retries=args.max_retries,
            timeout=args.timeout,
            sleep_seconds=args.sleep,
            retry_backoff=args.retry_backoff,
        )
        summary[result.result] += 1
        suffix = ""
        if result.extracted_files is not None:
            suffix = f", xmls_extraidos={result.extracted_files}"
        print(
            f"{resource.month:%Y-%m} {resource.section}: "
            f"{result.result} -> {result.local_path}{suffix}"
        )

        is_last_request = index == len(resources) - 1
        if args.sleep > 0 and not is_last_request:
            time.sleep(args.sleep)

    print("Resumo:")
    for result_name, count in sorted(summary.items()):
        print(f"  {result_name}: {count}")
    print(f"Manifesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

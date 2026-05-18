"""CLI para baixar XMLs da Secao 1 do DOU via INLABS."""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

from dou_classifier.collect.date_ranges import iter_dates, parse_date
from dou_classifier.collect.downloader import download_one
from dou_classifier.collect.inlabs_client import InlabsClient, normalize_section
from dou_classifier.collect.paths import default_manifest_path, raw_zip_path
from dou_classifier.config import (
    DEFAULT_EMAIL_ENV,
    DEFAULT_PASSWORD_ENV,
    MissingCredentialsError,
    read_inlabs_credentials,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Baixa arquivos XML do DOU Secao 1 a partir do INLABS."
    )
    parser.add_argument("--start-date", required=True, help="Data inicial: YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Data final: YYYY-MM-DD.")
    parser.add_argument(
        "--sections",
        nargs="+",
        default=["DO1"],
        help="Secoes XML do INLABS. Use DO1 e, se necessario, DO1E.",
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
        help="Caminho do manifesto JSONL. Padrao: <output-dir>/manifests/downloads.jsonl.",
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
        help="Pausa em segundos entre requisicoes.",
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
        "--email-env",
        default=DEFAULT_EMAIL_ENV,
        help="Variavel de ambiente que contem o email do INLABS.",
    )
    parser.add_argument(
        "--password-env",
        default=DEFAULT_PASSWORD_ENV,
        help="Variavel de ambiente que contem a senha do INLABS.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra quais arquivos seriam coletados, sem autenticar nem baixar.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)
        sections = [normalize_section(section) for section in args.sections]
        dates = list(iter_dates(start_date, end_date))
    except ValueError as exc:
        parser.error(str(exc))

    output_dir = args.output_dir
    manifest_path = args.manifest_path or default_manifest_path(output_dir)

    if args.dry_run:
        for publication_date in dates:
            for section in sections:
                print(raw_zip_path(output_dir, publication_date, section))
        return 0

    try:
        credentials = read_inlabs_credentials(args.email_env, args.password_env)
    except MissingCredentialsError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    client = InlabsClient()
    try:
        client.login(credentials.email, credentials.password, timeout=args.timeout)
    except Exception as exc:  # noqa: BLE001 - CLI deve transformar erro em saida clara.
        print(f"Falha ao autenticar no INLABS: {exc}", file=sys.stderr)
        return 2

    summary: Counter[str] = Counter()
    extract = not args.no_extract

    for index, publication_date in enumerate(dates):
        for section in sections:
            result = download_one(
                client=client,
                publication_date=publication_date,
                section=section,
                output_dir=output_dir,
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
                f"{publication_date.isoformat()} {section}: "
                f"{result.result} -> {result.local_path}{suffix}"
            )

            is_last_request = (
                index == len(dates) - 1 and section == sections[-1]
            )
            if args.sleep > 0 and not is_last_request:
                time.sleep(args.sleep)

    print("Resumo:")
    for result_name, count in sorted(summary.items()):
        print(f"  {result_name}: {count}")
    print(f"Manifesto: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

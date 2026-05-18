"""Convencoes de caminho para dados baixados e extraidos."""

from __future__ import annotations

from datetime import date
from pathlib import Path


def inlabs_filename(publication_date: date, section: str) -> str:
    return f"{publication_date.isoformat()}-{section.upper()}.zip"


def raw_zip_path(output_dir: Path, publication_date: date, section: str) -> Path:
    return (
        output_dir
        / "raw"
        / "inlabs"
        / f"{publication_date:%Y}"
        / f"{publication_date:%m}"
        / inlabs_filename(publication_date, section)
    )


def extracted_dir(output_dir: Path, publication_date: date, section: str) -> Path:
    return (
        output_dir
        / "extracted"
        / "inlabs"
        / f"{publication_date:%Y}"
        / f"{publication_date:%m}"
        / f"{publication_date.isoformat()}-{section.upper()}"
    )


def default_manifest_path(output_dir: Path) -> Path:
    return output_dir / "manifests" / "downloads.jsonl"


def dados_abertos_filename(month: date, section: str) -> str:
    return f"{section.upper()}{month:%m%Y}.zip"


def raw_dados_abertos_zip_path(output_dir: Path, month: date, section: str) -> Path:
    return (
        output_dir
        / "raw"
        / "dados_abertos"
        / f"{month:%Y}"
        / f"{month:%m}"
        / dados_abertos_filename(month, section)
    )


def extracted_dados_abertos_dir(output_dir: Path, month: date, section: str) -> Path:
    stem = dados_abertos_filename(month, section).removesuffix(".zip")
    return (
        output_dir
        / "extracted"
        / "dados_abertos"
        / f"{month:%Y}"
        / f"{month:%m}"
        / stem
    )


def default_dados_abertos_manifest_path(output_dir: Path) -> Path:
    return output_dir / "manifests" / "dados_abertos_downloads.jsonl"

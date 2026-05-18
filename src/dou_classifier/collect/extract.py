"""Extracao segura dos XMLs contidos nos ZIPs do INLABS."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


class UnsafeZipMemberError(RuntimeError):
    """Erro levantado quando um ZIP tenta extrair arquivos fora do destino."""


def is_within_directory(base_dir: Path, candidate: Path) -> bool:
    base_resolved = base_dir.resolve()
    candidate_resolved = candidate.resolve()
    return base_resolved == candidate_resolved or base_resolved in candidate_resolved.parents


def extract_xml_files(zip_path: Path, target_dir: Path, force: bool = False) -> int:
    """Extrai apenas arquivos XML do ZIP, preservando nomes internos seguros."""

    if target_dir.exists() and force:
        shutil.rmtree(target_dir)

    existing_xmls = list(target_dir.rglob("*.xml")) if target_dir.exists() else []
    if existing_xmls and not force:
        return len(existing_xmls)

    target_dir.mkdir(parents=True, exist_ok=True)
    extracted_count = 0

    with zipfile.ZipFile(zip_path) as zip_obj:
        for member in zip_obj.infolist():
            if member.is_dir() or not member.filename.lower().endswith(".xml"):
                continue

            output_path = target_dir / member.filename
            if not is_within_directory(target_dir, output_path):
                raise UnsafeZipMemberError(f"Entrada insegura no ZIP: {member.filename}")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with zip_obj.open(member) as source, output_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            extracted_count += 1

    return extracted_count

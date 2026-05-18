"""Manifesto append-only das tentativas de coleta."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DownloadRecord:
    publication_date: date
    section: str
    url: str
    local_path: str
    status_code: int | None
    bytes: int | None
    sha256: str | None
    attempted_at: datetime
    attempt: int
    result: str
    message: str | None = None
    extracted_files: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["publication_date"] = self.publication_date.isoformat()
        data["attempted_at"] = self.attempted_at.isoformat()
        return data


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def append_record(manifest_path: Path, record: DownloadRecord) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(record.to_json_dict(), ensure_ascii=True))
        file_obj.write("\n")


def read_records(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []

    records: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records

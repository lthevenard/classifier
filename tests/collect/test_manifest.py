from datetime import date

from dou_classifier.collect.manifest import DownloadRecord, append_record, read_records, utc_now


def test_append_and_read_manifest_record(tmp_path):
    manifest_path = tmp_path / "manifests" / "downloads.jsonl"
    record = DownloadRecord(
        publication_date=date(2025, 5, 16),
        section="DO1",
        url="https://example.test/file.zip",
        local_path="data/raw/inlabs/2025/05/2025-05-16-DO1.zip",
        status_code=200,
        bytes=123,
        sha256="abc",
        attempted_at=utc_now(),
        attempt=1,
        result="downloaded",
        message="ok",
        extracted_files=10,
    )

    append_record(manifest_path, record)

    records = read_records(manifest_path)
    assert len(records) == 1
    assert records[0]["publication_date"] == "2025-05-16"
    assert records[0]["result"] == "downloaded"
    assert records[0]["extracted_files"] == 10

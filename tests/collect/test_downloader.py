from datetime import date
from io import BytesIO
import zipfile

from dou_classifier.collect.downloader import download_one
from dou_classifier.collect.inlabs_client import build_resource
from dou_classifier.collect.manifest import read_records


class FakeResponse:
    def __init__(self, status_code, content=b"", headers=None, url=""):
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}
        self.url = url

    def iter_content(self, chunk_size):
        for index in range(0, len(self._content), chunk_size):
            yield self._content[index : index + chunk_size]


class FakeClient:
    def __init__(self, response):
        if isinstance(response, list):
            self.responses = response
        else:
            self.responses = [response]

    def resource_for(self, publication_date, section):
        return build_resource(publication_date, section)

    def get_zip(self, publication_date, section, timeout):
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def build_zip_bytes():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_obj:
        zip_obj.writestr("materia.xml", "<xml />")
    return buffer.getvalue()


def test_download_one_saves_zip_extracts_xml_and_records_manifest(tmp_path):
    client = FakeClient(FakeResponse(200, build_zip_bytes()))
    manifest_path = tmp_path / "data" / "manifests" / "downloads.jsonl"

    result = download_one(
        client=client,
        publication_date=date(2025, 5, 16),
        section="DO1",
        output_dir=tmp_path / "data",
        manifest_path=manifest_path,
        max_retries=1,
    )

    assert result.result == "downloaded"
    assert result.local_path.exists()
    assert (
        tmp_path
        / "data"
        / "extracted"
        / "inlabs"
        / "2025"
        / "05"
        / "2025-05-16-DO1"
        / "materia.xml"
    ).exists()

    records = read_records(manifest_path)
    assert records[0]["result"] == "downloaded"
    assert records[0]["status_code"] == 200
    assert records[0]["extracted_files"] == 1
    assert records[0]["sha256"]


def test_download_one_records_not_found_without_creating_zip(tmp_path):
    client = FakeClient(FakeResponse(404))
    manifest_path = tmp_path / "data" / "manifests" / "downloads.jsonl"

    result = download_one(
        client=client,
        publication_date=date(2025, 5, 17),
        section="DO1",
        output_dir=tmp_path / "data",
        manifest_path=manifest_path,
        max_retries=1,
    )

    assert result.result == "not_found"
    assert not result.local_path.exists()

    records = read_records(manifest_path)
    assert records[0]["result"] == "not_found"
    assert records[0]["status_code"] == 404


def test_download_one_respects_retry_after_before_retrying(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("dou_classifier.collect.downloader.time.sleep", sleeps.append)
    client = FakeClient(
        [
            FakeResponse(429, headers={"Retry-After": "7"}),
            FakeResponse(404),
        ]
    )
    manifest_path = tmp_path / "data" / "manifests" / "downloads.jsonl"

    result = download_one(
        client=client,
        publication_date=date(2025, 5, 17),
        section="DO1",
        output_dir=tmp_path / "data",
        manifest_path=manifest_path,
        max_retries=2,
        sleep_seconds=0,
        retry_backoff=0,
    )

    assert result.result == "not_found"
    assert sleeps == [7.0]

    records = read_records(manifest_path)
    assert [record["status_code"] for record in records] == [429, 404]


def test_download_one_treats_empty_index_redirect_as_not_found(tmp_path):
    client = FakeClient(
        FakeResponse(
            200,
            b"<!DOCTYPE html>",
            headers={"content-type": "text/html; charset=utf-8"},
            url="https://inlabs.in.gov.br/index.php?p=",
        )
    )
    manifest_path = tmp_path / "data" / "manifests" / "downloads.jsonl"

    result = download_one(
        client=client,
        publication_date=date(2025, 1, 2),
        section="DO1",
        output_dir=tmp_path / "data",
        manifest_path=manifest_path,
        max_retries=3,
    )

    assert result.result == "not_found"
    assert not result.local_path.exists()

    records = read_records(manifest_path)
    assert len(records) == 1
    assert records[0]["result"] == "not_found"
    assert records[0]["status_code"] == 200

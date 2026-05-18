from datetime import date
from io import BytesIO
import zipfile

from dou_classifier.collect.dados_abertos_client import DadosAbertosResource
from dou_classifier.collect.dados_abertos_downloader import download_dados_abertos_resource
from dou_classifier.collect.manifest import read_records


class FakeResponse:
    def __init__(self, status_code, content=b"", headers=None):
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}

    def iter_content(self, chunk_size):
        for index in range(0, len(self._content), chunk_size):
            yield self._content[index : index + chunk_size]


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, url, headers=None, stream=True, timeout=None, allow_redirects=True):
        return self.response


def build_zip_bytes():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_obj:
        zip_obj.writestr("materia.xml", "<xml />")
    return buffer.getvalue()


def build_resource():
    return DadosAbertosResource(
        month=date(2025, 1, 1),
        section="S01",
        url="https://www.in.gov.br/documents/20181/1/S01012025/uuid",
        name="Publicacoes da Secao 1 - Janeiro de 2025",
        resource_id="jan-s1",
        dataset_name="diario-oficial-da-uniao-materias-publicadas-em-2025",
        format="zip+xml",
    )


def test_download_dados_abertos_resource_saves_zip_extracts_xml_and_records_manifest(tmp_path):
    manifest_path = tmp_path / "data" / "manifests" / "dados_abertos_downloads.jsonl"
    session = FakeSession(FakeResponse(200, build_zip_bytes()))

    result = download_dados_abertos_resource(
        resource=build_resource(),
        output_dir=tmp_path / "data",
        manifest_path=manifest_path,
        session=session,
        max_retries=1,
    )

    assert result.result == "downloaded"
    assert (
        tmp_path
        / "data"
        / "raw"
        / "dados_abertos"
        / "2025"
        / "01"
        / "S01012025.zip"
    ).exists()
    assert (
        tmp_path
        / "data"
        / "extracted"
        / "dados_abertos"
        / "2025"
        / "01"
        / "S01012025"
        / "materia.xml"
    ).exists()

    records = read_records(manifest_path)
    assert records[0]["publication_date"] == "2025-01-01"
    assert records[0]["section"] == "S01"
    assert records[0]["result"] == "downloaded"
    assert records[0]["sha256"]


def test_download_dados_abertos_resource_records_404_as_not_found(tmp_path):
    manifest_path = tmp_path / "data" / "manifests" / "dados_abertos_downloads.jsonl"
    session = FakeSession(FakeResponse(404))

    result = download_dados_abertos_resource(
        resource=build_resource(),
        output_dir=tmp_path / "data",
        manifest_path=manifest_path,
        session=session,
        max_retries=1,
    )

    assert result.result == "not_found"
    assert not result.local_path.exists()
    assert read_records(manifest_path)[0]["result"] == "not_found"

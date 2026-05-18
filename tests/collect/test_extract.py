import zipfile

import pytest

from dou_classifier.collect.extract import UnsafeZipMemberError, extract_xml_files


def test_extract_xml_files_extracts_only_xml(tmp_path):
    zip_path = tmp_path / "sample.zip"
    target_dir = tmp_path / "out"

    with zipfile.ZipFile(zip_path, "w") as zip_obj:
        zip_obj.writestr("materia1.xml", "<xml />")
        zip_obj.writestr("notes.txt", "ignore me")
        zip_obj.writestr("nested/materia2.XML", "<xml />")

    count = extract_xml_files(zip_path, target_dir)

    assert count == 2
    assert (target_dir / "materia1.xml").exists()
    assert (target_dir / "nested" / "materia2.XML").exists()
    assert not (target_dir / "notes.txt").exists()


def test_extract_xml_files_blocks_path_traversal(tmp_path):
    zip_path = tmp_path / "unsafe.zip"

    with zipfile.ZipFile(zip_path, "w") as zip_obj:
        zip_obj.writestr("../outside.xml", "<xml />")

    with pytest.raises(UnsafeZipMemberError):
        extract_xml_files(zip_path, tmp_path / "out")

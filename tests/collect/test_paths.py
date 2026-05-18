from datetime import date
from pathlib import Path

from dou_classifier.collect.paths import extracted_dir, raw_zip_path
from dou_classifier.collect.paths import (
    extracted_dados_abertos_dir,
    raw_dados_abertos_zip_path,
)


def test_raw_zip_path_uses_year_month_partition():
    assert raw_zip_path(Path("data"), date(2025, 5, 16), "DO1") == Path(
        "data/raw/inlabs/2025/05/2025-05-16-DO1.zip"
    )


def test_extracted_dir_uses_same_partitioning():
    assert extracted_dir(Path("data"), date(2025, 5, 16), "DO1") == Path(
        "data/extracted/inlabs/2025/05/2025-05-16-DO1"
    )


def test_raw_dados_abertos_zip_path_uses_monthly_filename():
    assert raw_dados_abertos_zip_path(Path("data"), date(2025, 5, 1), "S01") == Path(
        "data/raw/dados_abertos/2025/05/S01052025.zip"
    )


def test_extracted_dados_abertos_dir_uses_monthly_filename_stem():
    assert extracted_dados_abertos_dir(Path("data"), date(2025, 5, 1), "S01") == Path(
        "data/extracted/dados_abertos/2025/05/S01052025"
    )

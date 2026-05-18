from datetime import date

import pytest

from dou_classifier.collect.date_ranges import iter_dates, iter_months, parse_date, parse_month


def test_parse_date_accepts_iso_date():
    assert parse_date("2025-05-16") == date(2025, 5, 16)


def test_parse_date_rejects_other_formats():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_date("16/05/2025")


def test_iter_dates_is_inclusive():
    assert list(iter_dates(date(2025, 5, 1), date(2025, 5, 3))) == [
        date(2025, 5, 1),
        date(2025, 5, 2),
        date(2025, 5, 3),
    ]


def test_iter_dates_rejects_inverted_range():
    with pytest.raises(ValueError, match="final"):
        list(iter_dates(date(2025, 5, 3), date(2025, 5, 1)))


def test_parse_month_accepts_year_month():
    assert parse_month("2025-05") == date(2025, 5, 1)


def test_iter_months_is_inclusive_and_uses_month_start():
    assert list(iter_months(date(2025, 1, 15), date(2025, 3, 1))) == [
        date(2025, 1, 1),
        date(2025, 2, 1),
        date(2025, 3, 1),
    ]

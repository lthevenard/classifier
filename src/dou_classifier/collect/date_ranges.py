"""Utilitarios de datas para percorrer periodos de publicacao."""

from __future__ import annotations

from datetime import date, timedelta


def parse_date(value: str) -> date:
    """Converte uma string YYYY-MM-DD em date, com erro amigavel."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Data invalida: {value!r}. Use o formato YYYY-MM-DD.") from exc


def iter_dates(start_date: date, end_date: date):
    """Itera datas inclusive entre inicio e fim."""

    if end_date < start_date:
        raise ValueError("A data final nao pode ser anterior a data inicial.")

    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def parse_month(value: str) -> date:
    """Converte uma string YYYY-MM em date no primeiro dia do mes."""

    try:
        year_text, month_text = value.split("-", maxsplit=1)
        return date(int(year_text), int(month_text), 1)
    except ValueError as exc:
        raise ValueError(f"Mes invalido: {value!r}. Use o formato YYYY-MM.") from exc


def month_start(value: date) -> date:
    """Retorna o primeiro dia do mes da data informada."""

    return date(value.year, value.month, 1)


def add_month(value: date) -> date:
    """Retorna o primeiro dia do mes seguinte."""

    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def iter_months(start_date: date, end_date: date):
    """Itera meses inclusive entre as datas informadas."""

    if end_date < start_date:
        raise ValueError("A data final nao pode ser anterior a data inicial.")

    current = month_start(start_date)
    last = month_start(end_date)
    while current <= last:
        yield current
        current = add_month(current)

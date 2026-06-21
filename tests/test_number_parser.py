from decimal import Decimal

import pytest

from fri_checks.number_parser import parse_financial_number


def test_parse_comma_separated_amount():
    result = parse_financial_number("1,162,538,155.64")

    assert result.status == "ok"
    assert result.value == Decimal("1162538155.64")


def test_parse_percentage_records_percent_sign():
    result = parse_financial_number("13.80%")

    assert result.value == Decimal("13.80")
    assert result.is_percent is True
    assert "percent_sign_stripped" in result.notes


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-100.25", Decimal("-100.25")),
        ("(100.25)", Decimal("-100.25")),
        ("（100.25）", Decimal("-100.25")),
    ],
)
def test_parse_negative_values(raw: str, expected: Decimal):
    result = parse_financial_number(raw)

    assert result.status == "ok"
    assert result.value == expected


@pytest.mark.parametrize("raw", ["—", "--", "-", "不适用", "无", ""])
def test_parse_non_applicable_markers(raw: str):
    result = parse_financial_number(raw)

    assert result.status == "not_applicable"
    assert result.value is None


def test_parse_invalid_string():
    result = parse_financial_number("增加很多")

    assert result.status == "parse_failed"
    assert result.value is None

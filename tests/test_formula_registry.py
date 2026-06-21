from decimal import Decimal

from fri_checks.formula_registry import calculate_growth_rate


def test_calculate_normal_growth_rate():
    result = calculate_growth_rate(
        Decimal("1162538155.64"),
        Decimal("1021540066.21"),
    )

    assert result.status == "ok"
    assert result.value == Decimal("13.80")


def test_growth_rate_previous_zero_is_not_applicable():
    result = calculate_growth_rate(Decimal("100"), Decimal("0"))

    assert result.status == "not_applicable"
    assert result.value is None


def test_growth_rate_uses_absolute_negative_previous_value():
    result = calculate_growth_rate(Decimal("-50"), Decimal("-100"))

    assert result.status == "ok"
    assert result.value == Decimal("50.00")


def test_growth_rate_quantizes_to_two_decimal_places():
    result = calculate_growth_rate(Decimal("2"), Decimal("3"))

    assert result.value == Decimal("-33.33")

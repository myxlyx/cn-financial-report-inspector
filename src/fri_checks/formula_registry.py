"""Formula registry for deterministic financial calculations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Callable

from fri_checks.schema import FormulaResult

TWO_DECIMAL_PLACES = Decimal("0.01")


def calculate_growth_rate(
    current: Decimal | None,
    previous: Decimal | None,
) -> FormulaResult:
    if current is None or previous is None:
        return FormulaResult(
            formula_type="growth_rate",
            value=None,
            status="parse_failed",
            notes=["current_or_previous_missing"],
        )
    if previous == 0:
        return FormulaResult(
            formula_type="growth_rate",
            value=None,
            status="not_applicable",
            notes=["previous_value_zero"],
        )

    try:
        with localcontext() as context:
            context.prec = 50
            value = ((current - previous) / abs(previous) * Decimal("100")).quantize(
                TWO_DECIMAL_PLACES,
                rounding=ROUND_HALF_UP,
            )
    except (InvalidOperation, ZeroDivisionError):
        return FormulaResult(
            formula_type="growth_rate",
            value=None,
            status="parse_failed",
            notes=["formula_calculation_failed"],
        )

    return FormulaResult(
        formula_type="growth_rate",
        value=value,
        status="ok",
    )


FormulaFunction = Callable[[Decimal | None, Decimal | None], FormulaResult]
FORMULA_REGISTRY: dict[str, FormulaFunction] = {
    "growth_rate": calculate_growth_rate,
}


def evaluate_formula(
    formula_type: str,
    current: Decimal | None,
    previous: Decimal | None,
) -> FormulaResult:
    formula = FORMULA_REGISTRY.get(formula_type)
    if formula is None:
        return FormulaResult(
            formula_type=formula_type,
            value=None,
            status="parse_failed",
            notes=["unknown_formula"],
        )
    return formula(current, previous)

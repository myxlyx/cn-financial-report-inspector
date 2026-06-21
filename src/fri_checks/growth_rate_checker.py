"""Execute deterministic growth-rate consistency checks."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fri_checks.formula_registry import TWO_DECIMAL_PLACES, evaluate_formula
from fri_checks.number_parser import parse_financial_number
from fri_checks.schema import CheckResult, CheckTask, NumberParseResult

DEFAULT_TOLERANCE = Decimal("0.05")


def check_growth_rate_task(
    task: CheckTask,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> CheckResult:
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    current = parse_financial_number(task.current_value_raw)
    previous = parse_financial_number(task.previous_value_raw)
    reported = parse_financial_number(task.reported_growth_rate_raw)
    notes = list(task.notes)
    notes.extend(_parse_notes("current", current))
    notes.extend(_parse_notes("previous", previous))
    notes.extend(_parse_notes("reported", reported))

    parse_results = (current, previous, reported)
    if any(result.status == "not_applicable" for result in parse_results):
        return _result(
            task,
            current,
            previous,
            reported,
            tolerance,
            status="not_applicable",
            review_required=False,
            notes=notes,
        )
    if any(result.status == "parse_failed" for result in parse_results):
        return _result(
            task,
            current,
            previous,
            reported,
            tolerance,
            status="parse_failed",
            review_required=True,
            notes=notes,
        )

    formula = evaluate_formula(task.formula_type, current.value, previous.value)
    notes.extend(f"formula:{note}" for note in formula.notes)
    if formula.status != "ok":
        return _result(
            task,
            current,
            previous,
            reported,
            tolerance,
            status=formula.status,
            review_required=formula.status == "parse_failed",
            computed=formula.value,
            notes=notes,
        )

    assert reported.value is not None
    assert formula.value is not None
    difference = abs(reported.value - formula.value).quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )
    is_consistent = difference <= tolerance
    return _result(
        task,
        current,
        previous,
        reported,
        tolerance,
        status="ok" if is_consistent else "mismatch",
        review_required=not is_consistent,
        computed=formula.value,
        difference=difference,
        is_consistent=is_consistent,
        notes=notes,
    )


def check_growth_rate_tasks(
    tasks: list[CheckTask],
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> list[CheckResult]:
    return [check_growth_rate_task(task, tolerance=tolerance) for task in tasks]


def _result(
    task: CheckTask,
    current: NumberParseResult,
    previous: NumberParseResult,
    reported: NumberParseResult,
    tolerance: Decimal,
    status: str,
    review_required: bool,
    computed: Decimal | None = None,
    difference: Decimal | None = None,
    is_consistent: bool | None = None,
    notes: list[str] | None = None,
) -> CheckResult:
    return CheckResult(
        check_type="growth_rate_consistency",
        report_id=task.report_id,
        table_id=task.table_id,
        page=task.page,
        row_index=task.row_index,
        item_name=task.item_name,
        formula_type=task.formula_type,
        current_cell=task.current_cell,
        previous_cell=task.previous_cell,
        reported_cell=task.reported_cell,
        current_value_raw=task.current_value_raw,
        previous_value_raw=task.previous_value_raw,
        reported_growth_rate_raw=task.reported_growth_rate_raw,
        current_value=current.value,
        previous_value=previous.value,
        reported_growth_rate=reported.value,
        computed_growth_rate=computed,
        difference=difference,
        tolerance=tolerance,
        is_consistent=is_consistent,
        review_required=review_required,
        status=status,  # type: ignore[arg-type]
        mapping_source=task.mapping_source,
        confidence=task.confidence,
        notes=notes or [],
    )


def _parse_notes(prefix: str, result: NumberParseResult) -> list[str]:
    return [f"{prefix}:{note}" for note in result.notes]

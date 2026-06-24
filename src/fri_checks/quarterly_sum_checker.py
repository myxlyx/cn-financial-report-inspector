"""Execute deterministic quarterly sum consistency checks."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fri_checks.formula_registry import TWO_DECIMAL_PLACES
from fri_checks.number_parser import parse_financial_number
from fri_checks.schema import (
    NumberParseResult,
    QuarterlyCheckResult,
    QuarterlyCheckTask,
)

DEFAULT_ABSOLUTE_TOLERANCE = Decimal("1.00")


def check_quarterly_sum_task(
    task: QuarterlyCheckTask,
    absolute_tolerance: Decimal = DEFAULT_ABSOLUTE_TOLERANCE,
) -> QuarterlyCheckResult:
    if absolute_tolerance < 0:
        raise ValueError("absolute_tolerance must be non-negative")

    annual = parse_financial_number(task.annual_value_raw)
    q1 = parse_financial_number(task.q1_raw)
    q2 = parse_financial_number(task.q2_raw)
    q3 = parse_financial_number(task.q3_raw)
    q4 = parse_financial_number(task.q4_raw)
    notes = list(task.notes)
    notes.extend(_parse_notes("annual", annual))
    notes.extend(_parse_notes("q1", q1))
    notes.extend(_parse_notes("q2", q2))
    notes.extend(_parse_notes("q3", q3))
    notes.extend(_parse_notes("q4", q4))

    parse_results = (annual, q1, q2, q3, q4)
    if any(result.status == "not_applicable" for result in parse_results):
        return _result(
            task=task,
            annual=annual,
            q1=q1,
            q2=q2,
            q3=q3,
            q4=q4,
            absolute_tolerance=absolute_tolerance,
            status="not_applicable",
            review_required=False,
            notes=notes,
        )
    if any(result.status == "parse_failed" for result in parse_results):
        return _result(
            task=task,
            annual=annual,
            q1=q1,
            q2=q2,
            q3=q3,
            q4=q4,
            absolute_tolerance=absolute_tolerance,
            status="parse_failed",
            review_required=True,
            notes=notes,
        )

    assert annual.value is not None
    assert q1.value is not None
    assert q2.value is not None
    assert q3.value is not None
    assert q4.value is not None
    quarterly_sum = (q1.value + q2.value + q3.value + q4.value).quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )
    difference = (quarterly_sum - annual.value).quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )
    absolute_difference = abs(difference)
    is_consistent = absolute_difference == 0 or absolute_difference < absolute_tolerance
    return _result(
        task=task,
        annual=annual,
        q1=q1,
        q2=q2,
        q3=q3,
        q4=q4,
        absolute_tolerance=absolute_tolerance,
        status="ok" if is_consistent else "mismatch",
        review_required=not is_consistent,
        computed_quarterly_sum=quarterly_sum,
        difference=difference,
        notes=notes,
    )


def check_quarterly_sum_tasks(
    tasks: list[QuarterlyCheckTask],
    absolute_tolerance: Decimal = DEFAULT_ABSOLUTE_TOLERANCE,
) -> list[QuarterlyCheckResult]:
    return [
        check_quarterly_sum_task(task, absolute_tolerance=absolute_tolerance)
        for task in tasks
    ]


def _result(
    task: QuarterlyCheckTask,
    annual: NumberParseResult,
    q1: NumberParseResult,
    q2: NumberParseResult,
    q3: NumberParseResult,
    q4: NumberParseResult,
    absolute_tolerance: Decimal,
    status: str,
    review_required: bool,
    computed_quarterly_sum: Decimal | None = None,
    difference: Decimal | None = None,
    notes: list[str] | None = None,
) -> QuarterlyCheckResult:
    return QuarterlyCheckResult(
        record_type="quarterly_sum_check",
        report_id=task.report_id,
        check_type="quarterly_sum_consistency",
        table_id=task.table_id,
        page=task.page,
        row_index=task.row_index,
        item_name=task.item_name,
        annual_value_raw=task.annual_value_raw,
        q1_raw=task.q1_raw,
        q2_raw=task.q2_raw,
        q3_raw=task.q3_raw,
        q4_raw=task.q4_raw,
        annual_value=annual.value,
        q1_value=q1.value,
        q2_value=q2.value,
        q3_value=q3.value,
        q4_value=q4.value,
        computed_quarterly_sum=computed_quarterly_sum,
        difference=difference,
        absolute_tolerance=absolute_tolerance,
        status=status,  # type: ignore[arg-type]
        review_required=review_required,
        annual_reference=task.annual_reference,
        evidence={
            "q1_cell": task.q1_cell,
            "q2_cell": task.q2_cell,
            "q3_cell": task.q3_cell,
            "q4_cell": task.q4_cell,
            "q1_cell_coord": [task.row_index, task.q1_cell],
            "q2_cell_coord": [task.row_index, task.q2_cell],
            "q3_cell_coord": [task.row_index, task.q3_cell],
            "q4_cell_coord": [task.row_index, task.q4_cell],
        },
        mapping_source=task.mapping_source,
        confidence=task.confidence,
        notes=notes or [],
    )


def _parse_notes(prefix: str, result: NumberParseResult) -> list[str]:
    return [f"{prefix}:{note}" for note in result.notes]

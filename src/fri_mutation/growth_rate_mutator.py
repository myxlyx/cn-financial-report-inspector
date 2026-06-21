"""Deterministic mutations of reported growth-rate table cells."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from fri_checks.growth_rate_checker import DEFAULT_TOLERANCE
from fri_checks.number_parser import parse_financial_number
from fri_mutation.schema import MutationCandidate, MutationStrategy

TWO_DECIMAL_PLACES = Decimal("0.01")


class MutationNotApplicable(ValueError):
    """Raised when a requested strategy cannot create a detectable mutation."""


def select_mutation_candidates(checks: Iterable[dict[str, Any]]) -> list[MutationCandidate]:
    candidates: list[MutationCandidate] = []
    for check in checks:
        if check.get("status") != "ok":
            continue
        if check.get("is_consistent") is not True:
            continue
        if check.get("review_required") is not False:
            continue

        table_id = check.get("table_id")
        row_index = check.get("row_index")
        reported_cell = check.get("reported_cell")
        reported_raw = check.get("reported_growth_rate_raw")
        computed_raw = check.get("computed_growth_rate")
        if not isinstance(table_id, str) or not table_id:
            continue
        if not _valid_index(row_index) or not _valid_index(reported_cell):
            continue
        if reported_raw is None or computed_raw is None:
            continue

        reported = parse_financial_number(reported_raw)
        computed = parse_financial_number(computed_raw)
        if reported.status != "ok" or computed.status != "ok":
            continue

        page = check.get("page")
        candidates.append(
            MutationCandidate(
                source_report_id=str(check.get("report_id", "")),
                table_id=table_id,
                page=int(page) if isinstance(page, int) and not isinstance(page, bool) else 0,
                row_index=row_index,
                item_name=str(check.get("item_name", "")),
                reported_cell=reported_cell,
                reported_growth_rate_raw=str(reported_raw),
                computed_growth_rate=str(computed_raw),
                reported_cell_coord=[row_index, reported_cell],
            )
        )
    return candidates


def mutate_reported_growth_rate(
    raw_value: object,
    strategy: MutationStrategy,
    computed_growth_rate: object,
    delta: Decimal = Decimal("5.00"),
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> str:
    reported = parse_financial_number(raw_value)
    computed = parse_financial_number(computed_growth_rate)
    if reported.status != "ok" or reported.value is None:
        raise MutationNotApplicable("reported growth rate is not parseable")
    if computed.status != "ok" or computed.value is None:
        raise MutationNotApplicable("computed growth rate is not available")

    if strategy == "add_delta":
        mutated = reported.value + delta
        if abs(mutated - computed.value) <= tolerance:
            adjustment = max(abs(delta), tolerance + TWO_DECIMAL_PLACES)
            direction = Decimal("-1") if delta < 0 else Decimal("1")
            mutated = computed.value + direction * adjustment
    elif strategy == "replace_with_zero":
        mutated = Decimal("0")
    elif strategy == "swap_sign":
        mutated = -reported.value
    else:
        raise ValueError(f"Unsupported mutation strategy: {strategy}")

    mutated = mutated.quantize(TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    if abs(mutated - computed.value) <= tolerance:
        raise MutationNotApplicable(
            f"strategy {strategy} would remain within checker tolerance"
        )

    suffix = "%" if reported.is_percent else ""
    return f"{format(mutated, 'f')}{suffix}"


def mutate_table(
    table: dict[str, Any],
    candidate: MutationCandidate,
    strategy: MutationStrategy,
    delta: Decimal = Decimal("5.00"),
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> tuple[dict[str, Any], str, str]:
    data = table.get("data")
    if not isinstance(data, list) or candidate.row_index >= len(data):
        raise MutationNotApplicable("target row is missing from table data")
    row = data[candidate.row_index]
    if not isinstance(row, list) or candidate.reported_cell >= len(row):
        raise MutationNotApplicable("target reported cell is missing from table data")

    mutated_table = deepcopy(table)
    mutated_data = mutated_table["data"]
    original_raw = str(mutated_data[candidate.row_index][candidate.reported_cell])
    mutated_raw = mutate_reported_growth_rate(
        original_raw,
        strategy=strategy,
        computed_growth_rate=candidate.computed_growth_rate,
        delta=delta,
        tolerance=tolerance,
    )
    mutated_data[candidate.row_index][candidate.reported_cell] = mutated_raw
    return mutated_table, original_raw, mutated_raw


def _valid_index(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0

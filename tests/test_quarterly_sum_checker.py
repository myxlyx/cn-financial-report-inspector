from decimal import Decimal

from fri_checks.quarterly_sum_checker import check_quarterly_sum_task
from fri_checks.schema import QuarterlyCheckTask


def _task(
    annual: str = "100",
    q1: str = "10",
    q2: str = "20",
    q3: str = "30",
    q4: str = "40",
) -> QuarterlyCheckTask:
    return QuarterlyCheckTask(
        report_id="sample-report",
        table_id="table_002",
        page=12,
        row_index=1,
        item_name="营业收入",
        annual_value_raw=annual,
        q1_raw=q1,
        q2_raw=q2,
        q3_raw=q3,
        q4_raw=q4,
        q1_cell=1,
        q2_cell=2,
        q3_cell=3,
        q4_cell=4,
        annual_reference={
            "source": "growth_rate_checks",
            "table_id": "table_annual",
            "page": 10,
            "row_index": 1,
        },
        confidence=0.95,
    )


def test_quarterly_sum_check_is_ok_when_sum_matches_annual_value():
    result = check_quarterly_sum_task(_task())

    assert result.status == "ok"
    assert result.review_required is False
    assert result.computed_quarterly_sum == Decimal("100.00")
    assert result.difference == Decimal("0.00")
    assert result.evidence["q1_cell_coord"] == [1, 1]


def test_quarterly_sum_check_reports_mismatch():
    result = check_quarterly_sum_task(_task(annual="101"))

    assert result.status == "mismatch"
    assert result.review_required is True
    assert result.computed_quarterly_sum == Decimal("100.00")
    assert result.difference == Decimal("-1.00")


def test_quarterly_sum_check_handles_negative_values():
    result = check_quarterly_sum_task(
        _task(annual="-100", q1="-10", q2="-20", q3="-30", q4="-40")
    )

    assert result.status == "ok"
    assert result.review_required is False
    assert result.computed_quarterly_sum == Decimal("-100.00")
    assert result.difference == Decimal("0.00")


def test_quarterly_sum_check_missing_annual_reference_is_not_applicable():
    task = _task(annual="")
    task.notes.append("missing_annual_reference")

    result = check_quarterly_sum_task(task)

    assert result.status == "not_applicable"
    assert result.review_required is False
    assert "missing_annual_reference" in result.notes

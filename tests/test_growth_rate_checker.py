from decimal import Decimal

from fri_checks.growth_rate_checker import check_growth_rate_task
from fri_checks.schema import CheckTask
from fri_checks.semantic_mapper import RuleBasedAnnualKeyMetricsMapper


def _task(reported: str = "20.00", previous: str = "100") -> CheckTask:
    return CheckTask(
        report_id="sample-report",
        table_id="table_009",
        page=10,
        row_index=1,
        item_name="营业收入",
        formula_type="growth_rate",
        current_cell=1,
        previous_cell=2,
        reported_cell=3,
        current_value_raw="120",
        previous_value_raw=previous,
        reported_growth_rate_raw=reported,
        confidence=0.95,
    )


def test_correct_reported_growth_rate_is_ok():
    result = check_growth_rate_task(_task())

    assert result.status == "ok"
    assert result.is_consistent is True
    assert result.review_required is False
    assert result.computed_growth_rate == Decimal("20.00")


def test_wrong_reported_growth_rate_is_mismatch():
    result = check_growth_rate_task(_task(reported="25.00"))

    assert result.status == "mismatch"
    assert result.is_consistent is False
    assert result.review_required is True
    assert result.difference == Decimal("5.00")


def test_previous_zero_is_not_applicable():
    result = check_growth_rate_task(_task(previous="0"))

    assert result.status == "not_applicable"
    assert result.is_consistent is None
    assert result.review_required is False


def test_blank_item_header_mapping_produces_an_ok_check():
    table = {
        "table_id": "table_004",
        "page": 11,
        "section_candidate": "六、主要会计数据和财务指标",
        "data": [
            ["", "2025 年", "2024 年", "本年比上年增减", "2023 年"],
            ["营业收入（元）", "120", "100", "20.00%", "90"],
        ],
    }

    mapping = RuleBasedAnnualKeyMetricsMapper().map_table(table)
    result = check_growth_rate_task(mapping.tasks[0])

    assert result.status == "ok"
    assert result.is_consistent is True


def test_sparse_table_mapping_produces_an_ok_check():
    table = {
        "table_id": "table_006",
        "page": 8,
        "section_candidate": "五、主要会计数据和财务指标",
        "data": [
            [
                "",
                "",
                "",
                "",
                "2025 年",
                "",
                "",
                "2024 年",
                "",
                "",
                "本年比上年增减",
                "",
                "",
                "2023 年",
                "",
            ],
            [
                "",
                "营业收入（元）",
                "",
                "195,606,041.08",
                "",
                "",
                "228,058,101.90",
                "",
                "",
                "-14.23%",
                "",
                "",
                "213,034,939.81",
                "",
                "",
            ],
        ],
    }

    mapping = RuleBasedAnnualKeyMetricsMapper().map_table(table)
    result = check_growth_rate_task(mapping.tasks[0])

    assert result.status == "ok"
    assert result.is_consistent is True

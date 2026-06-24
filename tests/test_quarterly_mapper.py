from fri_checks.quarterly_mapper import (
    RuleBasedQuarterlyMetricsMapper,
    normalize_item_key,
)
from fri_checks.schema import QuarterlyAnnualReference


def _annual_refs() -> dict[str, QuarterlyAnnualReference]:
    return {
        normalize_item_key("营业收入"): QuarterlyAnnualReference(
            report_id="sample-report",
            item_name="营业收入",
            annual_value_raw="100",
            source_table_id="table_annual",
            source_page=10,
            source_row_index=1,
        )
    }


def test_quarterly_mapper_maps_normal_table():
    table = {
        "table_id": "table_002",
        "page": 12,
        "section_candidate": "分季度主要财务指标",
        "data": [
            ["", "第一季度", "第二季度", "第三季度", "第四季度"],
            ["营业收入", "10", "20", "30", "40"],
        ],
    }

    result = RuleBasedQuarterlyMetricsMapper().map_table(
        table,
        annual_references=_annual_refs(),
        report_id="sample-report",
    )

    columns = {column.role: column.index for column in result.mapped_columns}
    assert result.is_candidate is True
    assert result.status == "ok"
    assert columns == {"item": 0, "q1": 1, "q2": 2, "q3": 3, "q4": 4}
    assert len(result.tasks) == 1
    assert result.tasks[0].item_name == "营业收入"
    assert result.tasks[0].annual_value_raw == "100"


def test_quarterly_mapper_detects_structure_without_clean_title():
    table = {
        "table_id": "table_003",
        "page": 12,
        "section_candidate": "其他说明",
        "data": [
            ["", "第一季度", "第二季度", "第三季度", "第四季度"],
            ["营业收入", "10", "20", "30", "40"],
            ["归属于上市公司股东的净利润", "1", "2", "3", "4"],
        ],
    }

    result = RuleBasedQuarterlyMetricsMapper().map_table(
        table,
        annual_references=_annual_refs(),
        report_id="sample-report",
    )

    assert result.is_candidate is True
    assert result.status == "ok"
    assert "four_quarter_columns_detected" in result.notes


def test_quarterly_mapper_normalizes_sparse_columns():
    table = {
        "table_id": "table_004",
        "page": 12,
        "section_candidate": "分季度主要财务指标",
        "data": [
            ["", "", "第一季度", "", "第二季度", "", "第三季度", "", "第四季度", ""],
            ["", "营业收入", "", "10", "", "20", "", "30", "", "40"],
        ],
    }

    result = RuleBasedQuarterlyMetricsMapper().map_table(
        table,
        annual_references=_annual_refs(),
        report_id="sample-report",
    )

    assert result.status == "ok"
    assert "sparse_columns_normalized" in result.notes
    task = result.tasks[0]
    assert task.q1_raw == "10"
    assert task.q2_raw == "20"
    assert task.q3_raw == "30"
    assert task.q4_raw == "40"
    assert task.q1_cell == 3
    assert task.q4_cell == 9


def test_quarterly_mapper_marks_missing_annual_reference():
    table = {
        "table_id": "table_005",
        "page": 12,
        "section_candidate": "分季度主要财务指标",
        "data": [
            ["", "第一季度", "第二季度", "第三季度", "第四季度"],
            ["营业收入", "10", "20", "30", "40"],
        ],
    }

    result = RuleBasedQuarterlyMetricsMapper().map_table(
        table,
        annual_references={},
        report_id="sample-report",
    )

    assert result.status == "ok"
    assert result.tasks[0].annual_value_raw == ""
    assert "missing_annual_reference" in result.tasks[0].notes


def test_quarterly_mapper_skips_multi_year_quarterly_comparison_table():
    table = {
        "table_id": "table_006",
        "page": 18,
        "section_candidate": "季度经营对比",
        "data": [
            [
                "",
                "2025 年度第一季度",
                "2025 年度第二季度",
                "2024 年度第三季度",
                "2024 年度第四季度",
            ],
            ["营业收入", "10", "20", "30", "40"],
            ["归属于上市公司股东的净利润", "1", "2", "3", "4"],
        ],
    }

    result = RuleBasedQuarterlyMetricsMapper().map_table(
        table,
        annual_references=_annual_refs(),
        report_id="sample-report",
    )

    assert result.is_candidate is False
    assert result.status == "skipped"
    assert "multi_year_quarterly_comparison" in result.notes

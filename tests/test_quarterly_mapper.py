from fri_checks.quarterly_mapper import (
    RuleBasedQuarterlyMetricsMapper,
    normalize_item_key,
)
from fri_checks.schema import QuarterlyAnnualReference


def _annual_refs() -> dict[str, QuarterlyAnnualReference]:
    values = {
        "营业收入": "100",
        "归属于上市公司股东的净利润": "-4127752783.80",
        "归属于上市公司股东的扣除非经常性损益的净利润": "-3309573012.45",
        "经营活动产生的现金流量净额": "1341256459.78",
    }
    return {
        normalize_item_key(item): QuarterlyAnnualReference(
            report_id="sample-report",
            item_name=item,
            annual_value_raw=value,
            source_table_id="table_annual",
            source_page=10,
            source_row_index=index,
        )
        for index, (item, value) in enumerate(values.items(), start=1)
    } | {
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


def test_quarterly_mapper_maps_fuxing_standard_quarterly_table_with_noisy_context():
    table = {
        "table_id": "table_010",
        "page": 8,
        "title_candidate": "项目",
        "section_candidate": "2025 年",
        "data": [
            ["", "第一季度", "第二季度", "第三季度", "第四季度"],
            [
                "营业收入",
                "344,468,125.63",
                "388,232,841.20",
                "283,432,802.53",
                "2,818,833,318.56",
            ],
            [
                "归属于上市公司股东的净利润",
                "-96,066,594.05",
                "-561,661,641.10",
                "-209,264,899.88",
                "-3,260,759,648.77",
            ],
            [
                "归属于上市公司股东的扣除非经常性损益的净利润",
                "-101,046,034.90",
                "-528,095,216.81",
                "-138,867,989.12",
                "-2,541,563,771.62",
            ],
            [
                "经营活动产生的现金流量净额",
                "274,609,247.01",
                "408,983,474.92",
                "-465,934,431.02",
                "1,123,598,168.87",
            ],
        ],
    }

    result = RuleBasedQuarterlyMetricsMapper().map_table(
        table,
        annual_references=_annual_refs(),
        report_id="sample-report",
    )

    assert result.status == "ok"
    assert len(result.tasks) == 4
    assert "multi_year_quarterly_comparison" not in result.notes
    assert result.confidence >= 0.5


def test_quarterly_mapper_skips_true_multi_year_quarterly_comparison_table():
    table = {
        "table_id": "table_006",
        "page": 18,
        "section_candidate": "季度经营对比",
        "data": [
            ["", "2025年度", "", "", "", "2024年度", "", "", ""],
            [
                "",
                "第一季度",
                "第二季度",
                "第三季度",
                "第四季度",
                "第一季度",
                "第二季度",
                "第三季度",
                "第四季度",
            ],
            ["营业收入", "10", "20", "30", "40", "9", "19", "29", "39"],
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

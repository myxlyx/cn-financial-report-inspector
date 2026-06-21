from fri_checks.semantic_mapper import RuleBasedAnnualKeyMetricsMapper


def _fake_table() -> dict:
    return {
        "table_id": "table_009",
        "page": 10,
        "title_candidate": "单位：元",
        "section_candidate": "七、近三年主要会计数据和财务指标",
        "data": [
            [
                "主要会计数据",
                "2025年",
                "2024年",
                "本期比上年同期增减(%)",
                "2023年",
            ],
            [
                "营业收入",
                "1,162,538,155.64",
                "1,021,540,066.21",
                "13.80",
                "1,069,077,575.35",
            ],
        ],
    }


def test_rule_mapper_recognizes_and_maps_annual_key_metrics_table():
    result = RuleBasedAnnualKeyMetricsMapper().map_table(
        _fake_table(), report_id="sample-report"
    )

    columns = {column.role: column.index for column in result.mapped_columns}
    assert result.is_candidate is True
    assert result.status == "ok"
    assert columns == {
        "item": 0,
        "current": 1,
        "previous": 2,
        "reported_growth_rate": 3,
    }
    assert len(result.tasks) == 1
    assert result.tasks[0].item_name == "营业收入"
    assert result.tasks[0].mapping_source == "rule_based"


def test_rule_mapper_skips_percentage_point_change_rows():
    table = _fake_table()
    table["data"].append(
        ["加权平均净资产收益率（%）", "2.636", "2.408", "增加0.228个百分点", "4.743"]
    )

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    assert len(result.tasks) == 1
    assert any(
        "percentage_point_change_not_supported" in row.notes
        for row in result.mapped_rows
    )


def test_rule_mapper_can_detect_candidate_from_headers_without_section_title():
    table = _fake_table()
    table["section_candidate"] = ""

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    assert result.is_candidate is True
    assert result.status == "ok"


def test_rule_mapper_does_not_treat_unrelated_section_fragment_as_candidate():
    table = {
        "table_id": "table_010",
        "page": 10,
        "section_candidate": "五、主要会计数据和财务指标",
        "data": [["签字会计师姓名", "张三"]],
    }

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    assert result.is_candidate is False
    assert result.status == "skipped"

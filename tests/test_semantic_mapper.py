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


def test_rule_mapper_infers_blank_item_header():
    table = {
        "table_id": "table_004",
        "page": 11,
        "section_candidate": "六、主要会计数据和财务指标",
        "data": [
            ["", "2025 年", "2024 年", "本年比上年增减", "2023 年"],
            [
                "营业收入（元）",
                "143,751,044,503.13",
                "128,166,392,637.76",
                "12.16%",
                "119,623,887,693.45",
            ],
        ],
    }

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    columns = {column.role: column.index for column in result.mapped_columns}
    assert result.is_candidate is True
    assert result.status == "ok"
    assert columns["item"] == 0
    assert len(result.tasks) == 1


def test_rule_mapper_accepts_strong_structure_with_noisy_context():
    table = {
        "table_id": "table_008",
        "page": 7,
        "section_candidate": "无关的公司历史说明",
        "title_candidate": "管理及租赁",
        "data": [
            ["", "2025 年", "2024 年", "本年比上年增减", "2023 年"],
            ["营业收入（元）", "80", "100", "-20.00%", "90"],
            [
                "归属于上市公司股东的净利润（元）",
                "20",
                "10",
                "100.00%",
                "8",
            ],
        ],
    }

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    assert result.is_candidate is True
    assert result.status == "ok"
    assert len(result.tasks) == 2
    assert "structured_growth_header" in result.notes


def test_rule_mapper_rejects_two_year_operating_table_without_key_metrics_context():
    table = {
        "table_id": "table_009",
        "page": 18,
        "section_candidate": "2025 年",
        "title_candidate": "单位：元",
        "data": [
            ["", "2025 年", "2024 年", "同比增减"],
            ["营业收入合计", "80", "100", "-20.00%"],
            ["经营活动产生的现金流量净额", "20", "10", "100.00%"],
        ],
    }

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    assert result.is_candidate is False
    assert result.status == "skipped"


def test_rule_mapper_normalizes_sparse_columns_and_preserves_source_coordinates():
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

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    assert result.status == "ok"
    assert "sparse_columns_normalized" in result.notes
    task = result.tasks[0]
    assert task.current_cell == 3
    assert task.previous_cell == 6
    assert task.reported_cell == 9
    assert task.current_value_raw == "195,606,041.08"


def test_rule_mapper_merges_split_item_name_continuations():
    table = {
        "table_id": "table_006",
        "page": 8,
        "section_candidate": "五、主要会计数据和财务指标",
        "data": [
            ["", "2025 年", "2024 年", "本年比上年增减", "2023 年"],
            ["归属于上市公司股东", "20", "10", "100.00%", "8"],
            ["的净利润（元）", "", "", "", ""],
        ],
    }

    result = RuleBasedAnnualKeyMetricsMapper().map_table(table)

    assert result.status == "ok"
    assert len(result.tasks) == 1
    assert result.tasks[0].row_index == 1
    assert "归属于上市公司股东的净利润" in result.tasks[0].item_name

from decimal import Decimal

import pytest

from fri_mutation.growth_rate_mutator import (
    mutate_reported_growth_rate,
    mutate_table,
    select_mutation_candidates,
)


@pytest.mark.parametrize(
    ("strategy", "raw", "computed", "expected"),
    [
        ("add_delta", "13.80", "13.80", "18.80"),
        ("replace_with_zero", "13.80", "13.80", "0.00"),
        ("swap_sign", "13.80", "13.80", "-13.80"),
        ("swap_sign", "-25.77", "-25.77", "25.77"),
    ],
)
def test_growth_rate_mutation_strategies(
    strategy: str, raw: str, computed: str, expected: str
):
    mutated = mutate_reported_growth_rate(
        raw,
        strategy=strategy,  # type: ignore[arg-type]
        computed_growth_rate=computed,
        delta=Decimal("5.00"),
    )

    assert mutated == expected


def test_candidate_selection_only_keeps_valid_successful_checks():
    valid = {
        "report_id": "sample-report",
        "table_id": "table_001",
        "page": 1,
        "row_index": 1,
        "item_name": "营业收入",
        "reported_cell": 3,
        "reported_growth_rate_raw": "20.00",
        "computed_growth_rate": "20.00",
        "status": "ok",
        "is_consistent": True,
        "review_required": False,
    }
    checks = [
        valid,
        {**valid, "status": "mismatch"},
        {**valid, "status": "not_applicable"},
        {**valid, "status": "parse_failed"},
        {**valid, "reported_cell": None},
        {**valid, "computed_growth_rate": None},
    ]

    candidates = select_mutation_candidates(checks)

    assert len(candidates) == 1
    assert candidates[0].table_id == "table_001"
    assert candidates[0].reported_cell_coord == [1, 3]


def test_mutate_table_changes_only_reported_growth_rate_cell():
    table = {
        "table_id": "table_001",
        "data": [
            ["主要会计数据", "2025年", "2024年", "同比增减", "2023年"],
            ["营业收入", "120", "100", "20.00", "90"],
        ],
    }
    candidate = select_mutation_candidates(
        [
            {
                "report_id": "sample-report",
                "table_id": "table_001",
                "page": 1,
                "row_index": 1,
                "item_name": "营业收入",
                "reported_cell": 3,
                "reported_growth_rate_raw": "20.00",
                "computed_growth_rate": "20.00",
                "status": "ok",
                "is_consistent": True,
                "review_required": False,
            }
        ]
    )[0]

    mutated, original_raw, mutated_raw = mutate_table(
        table, candidate, strategy="add_delta"
    )

    assert original_raw == "20.00"
    assert mutated_raw == "25.00"
    assert mutated["data"][1] == ["营业收入", "120", "100", "25.00", "90"]
    assert table["data"][1] == ["营业收入", "120", "100", "20.00", "90"]

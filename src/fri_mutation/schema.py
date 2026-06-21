"""Dataclasses for growth-rate mutation samples."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

MutationStrategy = Literal["add_delta", "replace_with_zero", "swap_sign"]


@dataclass
class MutationCandidate:
    source_report_id: str
    table_id: str
    page: int
    row_index: int
    item_name: str
    reported_cell: int
    reported_growth_rate_raw: str
    computed_growth_rate: str
    reported_cell_coord: list[int]


@dataclass
class MutationLabel:
    mutation_id: str
    source_report_id: str
    mutation_type: str
    strategy: MutationStrategy
    target: dict[str, Any]
    original: dict[str, Any]
    mutated: dict[str, Any]
    expected_detection: dict[str, Any]
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MutationSummary:
    source_report_id: str
    mutations_count: int
    mutation_ids: list[str] = field(default_factory=list)
    validation_detected_count: int = 0
    skipped_candidates_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

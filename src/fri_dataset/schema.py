"""Dataclasses for reproducible dataset manifest records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class SerializableDataclass:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetManifest(SerializableDataclass):
    dataset_name: str
    version: str
    batch_name: str
    task: str
    language: str
    document_type: str
    source_dir: str
    parsed_dir: str
    mutated_dir: str
    batch_report: str
    created_at: str
    reports_count: int
    original_checks_count: int
    mutation_samples_count: int
    notes: list[str] = field(default_factory=list)


@dataclass
class ReportManifestRecord(SerializableDataclass):
    record_type: str
    batch_name: str
    report_id: str
    source_pdf: str
    source_pdf_sha256: str
    pdf_type: str
    page_count: int
    text_pages: int
    tables_count: int
    quality_level: str | None
    recommended_for_dataset: bool | None
    growth_rate_checks_count: int
    ok_count: int
    mismatch_count: int
    not_applicable_count: int
    mapping_failed_count: int
    review_required_count: int
    has_mapping_diagnostics: bool
    parse_warnings_count: int
    problem_flags: list[str] = field(default_factory=list)


@dataclass
class CheckManifestRecord(SerializableDataclass):
    record_type: str
    batch_name: str
    sample_id: str
    report_id: str
    source_pdf: str
    check_type: str
    formula_type: str
    table_id: str
    page: int
    row_index: int
    item_name: str
    current_value_raw: str
    previous_value_raw: str
    reported_growth_rate_raw: str
    current_value: str | None
    previous_value: str | None
    reported_growth_rate: str | None
    computed_growth_rate: str | None
    difference: str | None
    tolerance: str | None
    status: str
    is_consistent: bool | None
    review_required: bool
    mapping_source: str
    confidence: float
    is_mutated: bool
    label: str
    evidence: dict[str, Any]
    notes: list[str] = field(default_factory=list)


@dataclass
class MutationManifestRecord(SerializableDataclass):
    record_type: str
    batch_name: str
    sample_id: str
    mutation_id: str
    source_report_id: str
    source_pdf: str
    mutated_report_dir: str
    mutation_type: str
    strategy: str
    table_id: str
    page: int
    row_index: int
    item_name: str
    reported_cell: int
    reported_cell_coord: list[int]
    original_reported_growth_rate_raw: str
    mutated_reported_growth_rate_raw: str
    computed_growth_rate: str | None
    expected_status: str
    expected_review_required: bool
    expected_should_detect: bool
    detected: bool
    detected_status: str | None
    detected_review_required: bool | None
    is_mutated: bool
    label: str

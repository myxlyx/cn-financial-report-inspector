"""Shared dataclasses for deterministic financial checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Literal

CheckStatus = Literal[
    "ok",
    "mismatch",
    "not_applicable",
    "parse_failed",
    "mapping_failed",
    "skipped",
]


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


class SerializableDataclass:
    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass
class NumberParseResult(SerializableDataclass):
    raw: str
    value: Decimal | None
    status: Literal["ok", "not_applicable", "parse_failed"]
    is_percent: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class FormulaResult(SerializableDataclass):
    formula_type: str
    value: Decimal | None
    status: Literal["ok", "not_applicable", "parse_failed"]
    notes: list[str] = field(default_factory=list)


@dataclass
class MappedColumn(SerializableDataclass):
    role: str
    index: int
    header: str
    confidence: float


@dataclass
class MappedRow(SerializableDataclass):
    row_index: int
    item_name: str
    cells: list[str]
    recognized_item: str | None
    confidence: float
    notes: list[str] = field(default_factory=list)


@dataclass
class CheckTask(SerializableDataclass):
    report_id: str
    table_id: str
    page: int
    row_index: int
    item_name: str
    formula_type: str
    current_cell: int
    previous_cell: int
    reported_cell: int
    current_value_raw: str
    previous_value_raw: str
    reported_growth_rate_raw: str
    mapping_source: str = "rule_based"
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class CheckResult(SerializableDataclass):
    check_type: str
    report_id: str
    table_id: str
    page: int
    row_index: int
    item_name: str
    formula_type: str
    current_cell: int
    previous_cell: int
    reported_cell: int
    current_value_raw: str
    previous_value_raw: str
    reported_growth_rate_raw: str
    current_value: Decimal | None
    previous_value: Decimal | None
    reported_growth_rate: Decimal | None
    computed_growth_rate: Decimal | None
    difference: Decimal | None
    tolerance: Decimal
    is_consistent: bool | None
    review_required: bool
    status: CheckStatus
    mapping_source: str
    confidence: float
    notes: list[str] = field(default_factory=list)


@dataclass
class MappingResult(SerializableDataclass):
    report_id: str
    table_id: str
    page: int
    is_candidate: bool
    status: CheckStatus
    mapped_columns: list[MappedColumn] = field(default_factory=list)
    mapped_rows: list[MappedRow] = field(default_factory=list)
    tasks: list[CheckTask] = field(default_factory=list)
    mapping_source: str = "rule_based"
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class CheckSummary(SerializableDataclass):
    report_id: str
    checks_count: int
    ok_count: int
    mismatch_count: int
    review_required_count: int
    not_applicable_count: int
    parse_failed_count: int
    mapping_failed_count: int
    tables_scanned: int
    candidate_tables: int


@dataclass
class QuarterlyAnnualReference(SerializableDataclass):
    report_id: str
    item_name: str
    annual_value_raw: str
    source_table_id: str
    source_page: int
    source_row_index: int
    unit: str | None = None
    value_scale: Decimal = Decimal("1")


@dataclass
class QuarterlyCheckTask(SerializableDataclass):
    report_id: str
    table_id: str
    page: int
    row_index: int
    item_name: str
    annual_value_raw: str
    q1_raw: str
    q2_raw: str
    q3_raw: str
    q4_raw: str
    q1_cell: int
    q2_cell: int
    q3_cell: int
    q4_cell: int
    annual_reference: dict[str, Any]
    annual_value_scale: Decimal = Decimal("1")
    quarterly_value_scale: Decimal = Decimal("1")
    mapping_source: str = "rule_based"
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class QuarterlyCheckResult(SerializableDataclass):
    record_type: str
    report_id: str
    check_type: str
    table_id: str
    page: int
    row_index: int
    item_name: str
    annual_value_raw: str
    q1_raw: str
    q2_raw: str
    q3_raw: str
    q4_raw: str
    annual_value: Decimal | None
    q1_value: Decimal | None
    q2_value: Decimal | None
    q3_value: Decimal | None
    q4_value: Decimal | None
    computed_quarterly_sum: Decimal | None
    difference: Decimal | None
    absolute_tolerance: Decimal
    status: CheckStatus
    review_required: bool
    annual_reference: dict[str, Any]
    evidence: dict[str, Any]
    mapping_source: str
    confidence: float
    notes: list[str] = field(default_factory=list)


@dataclass
class QuarterlyMappingResult(SerializableDataclass):
    report_id: str
    table_id: str
    page: int
    is_candidate: bool
    status: CheckStatus
    mapped_columns: list[MappedColumn] = field(default_factory=list)
    mapped_rows: list[MappedRow] = field(default_factory=list)
    tasks: list[QuarterlyCheckTask] = field(default_factory=list)
    mapping_source: str = "rule_based"
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class QuarterlyCheckSummary(SerializableDataclass):
    report_id: str
    candidate_tables: int
    checks_count: int
    ok_count: int
    mismatch_count: int
    not_applicable_count: int
    parse_failed_count: int
    mapping_failed_count: int
    review_required_count: int
    duplicate_skipped_count: int = 0
    warnings: list[str] = field(default_factory=list)

"""Rule-based mapping for quarterly key financial metric tables."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from fri_checks.schema import (
    MappedColumn,
    MappedRow,
    QuarterlyAnnualReference,
    QuarterlyCheckTask,
    QuarterlyMappingResult,
)

QUARTERLY_CONTEXT_KEYWORDS = (
    "分季度主要财务指标",
    "分季度主要会计数据",
    "主要财务指标分季度情况",
    "分季度财务指标",
)
QUARTER_HEADERS = {
    "q1": ("第一季度", "一季度", "第1季度", "1季度", "q1"),
    "q2": ("第二季度", "二季度", "第2季度", "2季度", "q2"),
    "q3": ("第三季度", "三季度", "第3季度", "3季度", "q3"),
    "q4": ("第四季度", "四季度", "第4季度", "4季度", "q4"),
}
TARGET_ITEM_ALIASES = (
    (
        "归属于上市公司股东的扣除非经常性损益的净利润",
        "归属于上市公司股东的扣除非经常性损益的净利润",
    ),
    ("归属于上市公司股东的净利润", "归属于上市公司股东的净利润"),
    ("经营活动产生的现金流量净额", "经营活动产生的现金流量净额"),
    ("营业收入", "营业收入"),
)
METRIC_FRAGMENTS = (
    "营业收入",
    "归属于上市公司股东",
    "扣除非经常性损益",
    "经营活动产生的现金",
)


@dataclass
class _NormalizedTable:
    rows: list[list[str]]
    source_columns: list[int]
    notes: list[str] = field(default_factory=list)


class BaseQuarterlyMapper(ABC):
    @abstractmethod
    def map_table(
        self,
        table: dict[str, Any],
        annual_references: dict[str, QuarterlyAnnualReference],
        report_id: str = "",
    ) -> QuarterlyMappingResult:
        """Map one extracted table into quarterly sum check tasks."""


class RuleBasedQuarterlyMetricsMapper(BaseQuarterlyMapper):
    mapping_source = "rule_based"

    def map_table(
        self,
        table: dict[str, Any],
        annual_references: dict[str, QuarterlyAnnualReference],
        report_id: str = "",
    ) -> QuarterlyMappingResult:
        table_id = str(table.get("table_id", ""))
        page = _safe_int(table.get("page"))
        normalized_table = _normalize_table(_coerce_rows(table.get("data")))
        rows = normalized_table.rows
        candidate_score, candidate_notes = self._candidate_score(table, rows)
        candidate_notes.extend(normalized_table.notes)
        if candidate_score < 0.5:
            return QuarterlyMappingResult(
                report_id=report_id,
                table_id=table_id,
                page=page,
                is_candidate=False,
                status="skipped",
                confidence=candidate_score,
                notes=candidate_notes,
            )

        header_index, columns = self._find_header(rows)
        required_roles = {"item", "q1", "q2", "q3", "q4"}
        mapped_roles = {column.role for column in columns}
        if header_index is None or not required_roles.issubset(mapped_roles):
            missing = sorted(required_roles - mapped_roles)
            return QuarterlyMappingResult(
                report_id=report_id,
                table_id=table_id,
                page=page,
                is_candidate=True,
                status="mapping_failed",
                mapped_columns=columns,
                confidence=round(candidate_score * 0.6, 2),
                notes=candidate_notes + [f"missing_columns:{','.join(missing)}"],
            )

        by_role = {column.role: column for column in columns}
        rows = _merge_item_continuations(rows, header_index, by_role)
        mapped_rows: list[MappedRow] = []
        tasks: list[QuarterlyCheckTask] = []
        for row_index, row in enumerate(rows[header_index + 1 :], start=header_index + 1):
            mapped_row, task = self._map_row(
                row=row,
                row_index=row_index,
                report_id=report_id,
                table_id=table_id,
                page=page,
                columns=by_role,
                source_columns=normalized_table.source_columns,
                annual_references=annual_references,
            )
            if mapped_row is not None:
                mapped_rows.append(mapped_row)
            if task is not None:
                tasks.append(task)

        if not tasks:
            return QuarterlyMappingResult(
                report_id=report_id,
                table_id=table_id,
                page=page,
                is_candidate=True,
                status="mapping_failed",
                mapped_columns=columns,
                mapped_rows=mapped_rows,
                confidence=round(candidate_score * 0.7, 2),
                notes=candidate_notes + ["no_supported_rows"],
            )

        confidence = min(candidate_score, min(column.confidence for column in columns))
        return QuarterlyMappingResult(
            report_id=report_id,
            table_id=table_id,
            page=page,
            is_candidate=True,
            status="ok",
            mapped_columns=columns,
            mapped_rows=mapped_rows,
            tasks=tasks,
            confidence=round(confidence, 2),
            notes=candidate_notes,
        )

    def _candidate_score(
        self,
        table: dict[str, Any],
        rows: list[list[str]],
    ) -> tuple[float, list[str]]:
        context = _normalize_text(
            str(table.get("section_candidate", "")) + str(table.get("title_candidate", ""))
        )
        score = 0.0
        notes: list[str] = []

        if any(keyword in context for keyword in QUARTERLY_CONTEXT_KEYWORDS):
            score += 0.5
            notes.append("quarterly_metrics_context")

        structural = _find_structural_header(rows)
        if structural is not None:
            header_index = structural
            score += 0.45
            notes.append("four_quarter_columns_detected")
            metric_count = _count_metric_rows(rows[header_index + 1 : header_index + 12])
            if metric_count >= 2:
                score += 0.25
                notes.append("multiple_quarterly_metrics_detected")
            elif metric_count == 1:
                score += 0.15
                notes.append("quarterly_metric_detected")

        return min(score, 0.99), notes

    def _find_header(
        self,
        rows: list[list[str]],
    ) -> tuple[int | None, list[MappedColumn]]:
        best_index: int | None = None
        best_columns: list[MappedColumn] = []
        best_strength = -1
        for row_index, row in enumerate(rows[:8]):
            following_rows = rows[row_index + 1 : row_index + 12]
            candidates = [(row_index, row)]
            if row_index + 1 < min(len(rows), 8):
                candidates.append((row_index + 1, _merge_header_rows(row, rows[row_index + 1])))

            for header_end_index, header_row in candidates:
                columns = _map_header_columns(header_row, following_rows)
                roles = {column.role for column in columns}
                quarter_roles = {"q1", "q2", "q3", "q4"}
                strength = len(roles) + 3 * int(quarter_roles.issubset(roles))
                if strength > best_strength:
                    best_index = header_end_index
                    best_columns = columns
                    best_strength = strength
                if {"item", *quarter_roles}.issubset(roles):
                    return header_end_index, columns
        return best_index, best_columns

    def _map_row(
        self,
        row: list[str],
        row_index: int,
        report_id: str,
        table_id: str,
        page: int,
        columns: dict[str, MappedColumn],
        source_columns: list[int],
        annual_references: dict[str, QuarterlyAnnualReference],
    ) -> tuple[MappedRow | None, QuarterlyCheckTask | None]:
        item = _cell(row, columns["item"].index)
        item_name = _clean_item_name(item)
        if not item_name:
            return None, None

        recognized_item = recognize_quarterly_item(item_name)
        row_confidence = 0.95 if recognized_item else 0.7
        notes: list[str] = []
        if recognized_item is None:
            notes.append("unsupported_item")
            return MappedRow(row_index, item_name, row, None, row_confidence, notes), None

        reference = annual_references.get(normalize_item_key(recognized_item))
        if reference is None:
            notes.append("missing_annual_reference")
            annual_value_raw = ""
            annual_reference = {
                "source": "growth_rate_checks",
                "table_id": "",
                "page": 0,
                "row_index": -1,
            }
        else:
            annual_value_raw = reference.annual_value_raw
            annual_reference = {
                "source": "growth_rate_checks",
                "table_id": reference.source_table_id,
                "page": reference.source_page,
                "row_index": reference.source_row_index,
            }

        mapped_row = MappedRow(
            row_index=row_index,
            item_name=item_name,
            cells=row,
            recognized_item=recognized_item,
            confidence=row_confidence,
            notes=notes,
        )
        task = QuarterlyCheckTask(
            report_id=report_id,
            table_id=table_id,
            page=page,
            row_index=row_index,
            item_name=recognized_item,
            annual_value_raw=annual_value_raw,
            q1_raw=_cell(row, columns["q1"].index),
            q2_raw=_cell(row, columns["q2"].index),
            q3_raw=_cell(row, columns["q3"].index),
            q4_raw=_cell(row, columns["q4"].index),
            q1_cell=_source_column(source_columns, columns["q1"].index),
            q2_cell=_source_column(source_columns, columns["q2"].index),
            q3_cell=_source_column(source_columns, columns["q3"].index),
            q4_cell=_source_column(source_columns, columns["q4"].index),
            annual_reference=annual_reference,
            confidence=row_confidence,
            notes=notes.copy(),
        )
        return mapped_row, task


def normalize_item_key(value: str) -> str:
    return _strip_unit_suffix(_normalize_text(value))


def recognize_quarterly_item(item_name: str) -> str | None:
    normalized = normalize_item_key(item_name)
    for alias, canonical in TARGET_ITEM_ALIASES:
        if alias in normalized:
            return canonical
    return None


def _normalize_table(rows: list[list[str]]) -> _NormalizedTable:
    if not rows:
        return _NormalizedTable([], [])

    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    layout = _find_quarterly_layout(padded)
    if layout is None:
        return _NormalizedTable(padded, list(range(width)))

    header_index, item_column, anchors, value_columns = layout
    source_columns = [item_column, *value_columns]
    normalized_rows: list[list[str]] = []
    for row_index, row in enumerate(padded):
        if row_index == header_index:
            normalized_rows.append([row[item_column], *(row[index] for index in anchors)])
        else:
            normalized_rows.append([row[item_column], *(row[index] for index in value_columns)])

    expected = [item_column, *anchors]
    notes = [] if source_columns == expected else ["sparse_columns_normalized"]
    return _NormalizedTable(normalized_rows, source_columns, notes)


def _find_quarterly_layout(
    rows: list[list[str]],
) -> tuple[int, int, list[int], list[int]] | None:
    width = len(rows[0]) if rows else 0
    for header_index, row in enumerate(rows[:8]):
        quarter_columns = _quarter_columns(row)
        if set(quarter_columns) != {"q1", "q2", "q3", "q4"}:
            continue
        anchors = [quarter_columns[role] for role in ("q1", "q2", "q3", "q4")]
        following = rows[header_index + 1 : header_index + 15]
        item_column = _infer_item_column(following)
        if item_column is None:
            continue

        value_columns = _choose_value_columns(following, item_column, anchors, width)
        return header_index, item_column, anchors, value_columns
    return None


def _choose_value_columns(
    rows: list[list[str]],
    item_column: int,
    anchors: list[int],
    width: int,
) -> list[int]:
    value_columns: list[int] = []
    for index, anchor in enumerate(anchors):
        previous_anchor = anchors[index - 1] if index > 0 else item_column
        next_anchor = anchors[index + 1] if index + 1 < len(anchors) else width
        left_mid = (previous_anchor + anchor) // 2 + 1
        right_mid = (anchor + next_anchor) // 2
        left = max(item_column + 1, min(left_mid, anchor))
        right = min(width - 1, max(right_mid, anchor))
        candidates = list(range(left, right + 1)) or [anchor]
        value_columns.append(_best_value_column(rows, candidates, anchor))
    return value_columns


def _best_value_column(rows: list[list[str]], candidates: list[int], anchor: int) -> int:
    def score(index: int) -> tuple[int, int]:
        numeric = sum(_looks_numeric_cell(_cell(row, index)) for row in rows)
        nonempty = sum(bool(_normalize_text(_cell(row, index))) for row in rows)
        return numeric * 3 + nonempty, -abs(anchor - index)

    return max(candidates, key=score)


def _map_header_columns(
    row: list[str],
    following_rows: list[list[str]] | None = None,
) -> list[MappedColumn]:
    mapped: dict[str, MappedColumn] = {}
    quarter_columns = _quarter_columns(row)
    for role in ("q1", "q2", "q3", "q4"):
        if role in quarter_columns:
            index = quarter_columns[role]
            mapped[role] = MappedColumn(role, index, row[index], 0.98)

    if {"q1", "q2", "q3", "q4"}.issubset(mapped):
        item_index = _infer_item_column(following_rows or [])
        if item_index is not None:
            mapped["item"] = MappedColumn("item", item_index, _cell(row, item_index), 0.9)

    return [mapped[role] for role in ("item", "q1", "q2", "q3", "q4") if role in mapped]


def _find_structural_header(rows: list[list[str]]) -> int | None:
    for row_index, row in enumerate(rows[:8]):
        if set(_quarter_columns(row)) == {"q1", "q2", "q3", "q4"}:
            return row_index
        if row_index + 1 < min(len(rows), 8):
            merged = _merge_header_rows(row, rows[row_index + 1])
            if set(_quarter_columns(merged)) == {"q1", "q2", "q3", "q4"}:
                return row_index + 1
    return None


def _quarter_columns(row: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, cell in enumerate(row):
        normalized = _normalize_text(cell).lower()
        for role, aliases in QUARTER_HEADERS.items():
            if role not in found and any(alias.lower() in normalized for alias in aliases):
                found[role] = index
    return found


def _merge_item_continuations(
    rows: list[list[str]],
    header_index: int,
    columns: dict[str, MappedColumn],
) -> list[list[str]]:
    merged_rows = [row.copy() for row in rows]
    item_index = columns["item"].index
    value_indices = [columns[role].index for role in ("q1", "q2", "q3", "q4")]
    for row_index in range(header_index + 1, len(merged_rows)):
        row = merged_rows[row_index]
        if not _cell(row, item_index) or not any(_cell(row, index) for index in value_indices):
            continue
        continuation_index = row_index + 1
        while continuation_index < len(merged_rows):
            continuation = merged_rows[continuation_index]
            continuation_item = _cell(continuation, item_index)
            if not continuation_item or any(
                _cell(continuation, index) for index in value_indices
            ):
                break
            row[item_index] += continuation_item
            continuation[item_index] = ""
            continuation_index += 1
    return merged_rows


def _infer_item_column(rows: list[list[str]]) -> int | None:
    scores: dict[int, int] = {}
    for row in rows:
        for index, cell in enumerate(row):
            normalized = normalize_item_key(cell)
            if recognize_quarterly_item(normalized) is not None:
                scores[index] = scores.get(index, 0) + 3
            elif any(fragment in normalized for fragment in METRIC_FRAGMENTS):
                scores[index] = scores.get(index, 0) + 1
    if not scores:
        return None
    return max(scores, key=lambda index: (scores[index], -index))


def _count_metric_rows(rows: list[list[str]]) -> int:
    count = 0
    for row in rows:
        combined = normalize_item_key("".join(row))
        if recognize_quarterly_item(combined) is not None or any(
            fragment in combined for fragment in METRIC_FRAGMENTS
        ):
            count += 1
    return count


def _merge_header_rows(first: list[str], second: list[str]) -> list[str]:
    width = max(len(first), len(second))
    return [_cell(first, index) + _cell(second, index) for index in range(width)]


def _looks_numeric_cell(value: object) -> bool:
    text = _normalize_text(value).replace(",", "").replace("%", "")
    text = text.replace("(", "-").replace(")", "")
    return bool(re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text)) or text in {
        "不适用",
        "无",
        "-",
        "--",
        "—",
    }


def _normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    return "".join(text.split()).replace("（", "(").replace("）", ")")


def _strip_unit_suffix(value: str) -> str:
    text = value
    text = re.sub(r"\((?:人民币)?元(?:/股|／股)?\)", "", text)
    text = re.sub(r"\((?:元|万元|亿元|元/股|元／股)\)", "", text)
    return text


def _clean_item_name(value: str) -> str:
    return "".join(value.split())


def _coerce_rows(value: object) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    rows: list[list[str]] = []
    for row in value:
        if isinstance(row, list):
            rows.append(["" if cell is None else str(cell) for cell in row])
    return rows


def _cell(row: list[str], index: int) -> str:
    return row[index] if 0 <= index < len(row) else ""


def _source_column(source_columns: list[int], index: int) -> int:
    return source_columns[index] if 0 <= index < len(source_columns) else index


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

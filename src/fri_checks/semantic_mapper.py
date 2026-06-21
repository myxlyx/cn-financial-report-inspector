"""Rule-based semantic mapping for annual key financial metric tables."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from fri_checks.schema import CheckTask, MappedColumn, MappedRow, MappingResult

ITEM_HEADERS = ("项目", "主要会计数据", "主要财务指标", "指标名称")
CURRENT_PERIOD_ALIASES = ("本年", "本期", "本报告期", "本期数")
PREVIOUS_PERIOD_ALIASES = ("上年", "上期", "上年同期", "上期数")
GROWTH_HEADERS = (
    "本期比上年同期增减",
    "本年比上年增减",
    "本年末比上年末增减",
    "比上年同期增减",
    "同比增减",
    "较上年同期增减",
    "增减比例",
    "变动幅度",
)
KNOWN_ITEM_ALIASES = (
    ("归属于上市公司股东的扣除非经常性损益的净利润", "归属于上市公司股东的扣除非经常性损益的净利润"),
    ("归属于上市公司股东的净利润", "归属于上市公司股东的净利润"),
    ("经营活动产生的现金流量净额", "经营活动产生的现金流量净额"),
    ("归属于上市公司股东的净资产", "归属于上市公司股东的净资产"),
    ("加权平均净资产收益率", "加权平均净资产收益率"),
    ("营业收入", "营业收入"),
    ("利润总额", "利润总额"),
    ("基本每股收益", "基本每股收益"),
    ("稀释每股收益", "稀释每股收益"),
    ("总资产", "总资产"),
    ("资产总额", "总资产"),
)
METRIC_FRAGMENTS = (
    "营业收入",
    "归属于上市公司股东",
    "扣除非经常性损益",
    "经营活动产生的现金",
    "基本每股收益",
    "稀释每股收益",
    "总资产",
    "资产总额",
)
_SUPPORTED_ROE = "加权平均净资产收益率"


@dataclass
class _NormalizedTable:
    rows: list[list[str]]
    source_columns: list[int]
    notes: list[str] = field(default_factory=list)


class BaseSemanticMapper(ABC):
    @abstractmethod
    def map_table(self, table: dict[str, Any], report_id: str = "") -> MappingResult:
        """Map one extracted table into structured calculation tasks."""


class RuleBasedAnnualKeyMetricsMapper(BaseSemanticMapper):
    mapping_source = "rule_based"

    def map_table(self, table: dict[str, Any], report_id: str = "") -> MappingResult:
        table_id = str(table.get("table_id", ""))
        page = _safe_int(table.get("page"))
        normalized_table = _normalize_table(_coerce_rows(table.get("data")))
        rows = normalized_table.rows
        candidate_score, candidate_notes = self._candidate_score(table, rows)
        candidate_notes.extend(normalized_table.notes)
        if candidate_score < 0.5:
            return MappingResult(
                report_id=report_id,
                table_id=table_id,
                page=page,
                is_candidate=False,
                status="skipped",
                confidence=candidate_score,
                notes=candidate_notes,
            )

        header_index, columns = self._find_header(rows)
        required_roles = {"item", "current", "previous", "reported_growth_rate"}
        mapped_roles = {column.role for column in columns}
        if header_index is None or not required_roles.issubset(mapped_roles):
            missing = sorted(required_roles - mapped_roles)
            return MappingResult(
                report_id=report_id,
                table_id=table_id,
                page=page,
                is_candidate=True,
                status="mapping_failed",
                mapped_columns=columns,
                confidence=round(candidate_score * 0.6, 2),
                notes=candidate_notes
                + [f"missing_columns:{','.join(missing)}", "needs_llm_mapping"],
            )

        by_role = {column.role: column for column in columns}
        rows = _merge_item_continuations(rows, header_index, by_role)
        mapped_rows: list[MappedRow] = []
        tasks: list[CheckTask] = []
        for row_index, row in enumerate(rows[header_index + 1 :], start=header_index + 1):
            mapped_row, task = self._map_row(
                row=row,
                row_index=row_index,
                report_id=report_id,
                table_id=table_id,
                page=page,
                columns=by_role,
                source_columns=normalized_table.source_columns,
            )
            if mapped_row is not None:
                mapped_rows.append(mapped_row)
            if task is not None:
                tasks.append(task)

        if not tasks:
            return MappingResult(
                report_id=report_id,
                table_id=table_id,
                page=page,
                is_candidate=True,
                status="mapping_failed",
                mapped_columns=columns,
                mapped_rows=mapped_rows,
                confidence=round(candidate_score * 0.7, 2),
                notes=candidate_notes + ["no_supported_rows", "needs_llm_mapping"],
            )

        confidence = min(candidate_score, min(column.confidence for column in columns))
        return MappingResult(
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
        section = _normalize_text(table.get("section_candidate"))
        title = _normalize_text(table.get("title_candidate"))
        preview = _normalize_text("".join(cell for row in rows[:5] for cell in row))
        section_context = section + title
        score = 0.0
        notes: list[str] = []

        if "近三年主要会计数据和财务指标" in section_context:
            score += 0.45
            notes.append("annual_key_metrics_section")
        elif "主要会计数据和财务指标" in section_context:
            score += 0.4
            notes.append("key_metrics_section")

        if "主要会计数据" in preview or "主要财务指标" in preview:
            score += 0.5
            notes.append("key_metrics_header")

        structural = _find_structural_header(rows)
        if structural is not None:
            header_index, year_count = structural
            score += 0.2
            notes.append("structured_growth_header")
            if year_count >= 3:
                score += 0.3
                notes.append("three_year_columns_detected")

            metric_count = _count_metric_rows(rows[header_index + 1 : header_index + 12])
            if metric_count >= 2:
                score += 0.25
                notes.append("multiple_known_metrics_detected")
            elif metric_count == 1:
                score += 0.1
                notes.append("known_metric_detected")

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
                strength = len(roles) + 2 * int(
                    {"current", "previous", "reported_growth_rate"}.issubset(roles)
                )
                if strength > best_strength:
                    best_index = header_end_index
                    best_columns = columns
                    best_strength = strength
                if len(roles) == 4:
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
    ) -> tuple[MappedRow | None, CheckTask | None]:
        item = _cell(row, columns["item"].index)
        item_name = _clean_item_name(item)
        if not item_name or item_name in ITEM_HEADERS:
            return None, None

        current_raw = _cell(row, columns["current"].index)
        previous_raw = _cell(row, columns["previous"].index)
        reported_raw = _cell(row, columns["reported_growth_rate"].index)
        recognized_item = _recognize_item(item_name)
        row_confidence = 0.95 if recognized_item else 0.7
        notes: list[str] = []

        if _looks_like_repeated_header(current_raw, previous_raw, reported_raw):
            return None, None
        if recognized_item is None:
            notes.append("unsupported_item")
            return (
                MappedRow(row_index, item_name, row, None, row_confidence, notes),
                None,
            )
        if "百分点" in _normalize_text(reported_raw):
            notes.append("percentage_point_change_not_supported")
            return (
                MappedRow(
                    row_index,
                    item_name,
                    row,
                    recognized_item,
                    row_confidence,
                    notes,
                ),
                None,
            )
        if recognized_item == _SUPPORTED_ROE:
            notes.append("return_on_equity_change_not_supported")
            return (
                MappedRow(
                    row_index,
                    item_name,
                    row,
                    recognized_item,
                    row_confidence,
                    notes,
                ),
                None,
            )

        mapped_row = MappedRow(
            row_index=row_index,
            item_name=item_name,
            cells=row,
            recognized_item=recognized_item,
            confidence=row_confidence,
            notes=notes,
        )
        task = CheckTask(
            report_id=report_id,
            table_id=table_id,
            page=page,
            row_index=row_index,
            item_name=item_name,
            formula_type="growth_rate",
            current_cell=_source_column(source_columns, columns["current"].index),
            previous_cell=_source_column(source_columns, columns["previous"].index),
            reported_cell=_source_column(
                source_columns, columns["reported_growth_rate"].index
            ),
            current_value_raw=current_raw,
            previous_value_raw=previous_raw,
            reported_growth_rate_raw=reported_raw,
            confidence=row_confidence,
            notes=notes.copy(),
        )
        return mapped_row, task


def _normalize_table(rows: list[list[str]]) -> _NormalizedTable:
    if not rows:
        return _NormalizedTable([], [])

    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    layout = _find_sparse_layout(padded)
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
    return _NormalizedTable(normalized_rows, source_columns, ["sparse_columns_normalized"])


def _find_sparse_layout(
    rows: list[list[str]],
) -> tuple[int, int, list[int], list[int]] | None:
    width = len(rows[0]) if rows else 0
    for header_index, row in enumerate(rows[:8]):
        anchors = [
            index
            for index, cell in enumerate(row)
            if _year_from_header(cell) is not None or _is_growth_header(cell)
        ]
        year_count = sum(_year_from_header(row[index]) is not None for index in anchors)
        growth_count = sum(_is_growth_header(row[index]) for index in anchors)
        if year_count < 2 or growth_count == 0 or len(anchors) < 3:
            continue

        following = rows[header_index + 1 : header_index + 15]
        item_column = _infer_item_column(following)
        if item_column is None:
            continue
        logical_width = len(anchors) + 1
        if width <= logical_width + 2 and max(_column_gaps([item_column, *anchors])) <= 1:
            continue

        value_columns: list[int] = []
        lower_bound = item_column + 1
        for anchor in anchors:
            candidates = list(range(max(0, lower_bound), anchor + 1))
            if not candidates:
                candidates = [anchor]
            value_columns.append(_best_value_column(following, candidates, anchor))
            lower_bound = anchor + 1
        return header_index, item_column, anchors, value_columns
    return None


def _best_value_column(rows: list[list[str]], candidates: list[int], anchor: int) -> int:
    def score(index: int) -> tuple[int, int]:
        numeric = sum(_looks_numeric_cell(_cell(row, index)) for row in rows)
        nonempty = sum(bool(_normalize_text(_cell(row, index))) for row in rows)
        return numeric * 3 + nonempty, -abs(anchor - index)

    return max(candidates, key=score)


def _map_header_columns(
    row: list[str], following_rows: list[list[str]] | None = None
) -> list[MappedColumn]:
    normalized = [_normalize_text(cell) for cell in row]
    mapped: dict[str, MappedColumn] = {}

    for index, header in enumerate(normalized):
        if any(alias == header or alias in header for alias in ITEM_HEADERS):
            mapped["item"] = MappedColumn("item", index, row[index], 0.95)
            break

    for index, header in enumerate(normalized):
        if _is_growth_header(header):
            mapped["reported_growth_rate"] = MappedColumn(
                "reported_growth_rate", index, row[index], 0.95
            )
            break

    year_columns = [
        (year, index)
        for index, header in enumerate(normalized)
        if (year := _year_from_header(header)) is not None
    ]
    unique_years = sorted({year for year, _ in year_columns}, reverse=True)
    if len(unique_years) >= 2:
        current_year, previous_year = unique_years[:2]
        current_index = next(index for year, index in year_columns if year == current_year)
        previous_index = next(index for year, index in year_columns if year == previous_year)
        mapped["current"] = MappedColumn("current", current_index, row[current_index], 0.98)
        mapped["previous"] = MappedColumn(
            "previous", previous_index, row[previous_index], 0.98
        )
    else:
        growth_index = mapped.get("reported_growth_rate")
        excluded = growth_index.index if growth_index else -1
        current_index = _find_alias_column(normalized, CURRENT_PERIOD_ALIASES, excluded)
        previous_index = _find_alias_column(normalized, PREVIOUS_PERIOD_ALIASES, excluded)
        if current_index is not None:
            mapped["current"] = MappedColumn("current", current_index, row[current_index], 0.85)
        if previous_index is not None:
            mapped["previous"] = MappedColumn(
                "previous", previous_index, row[previous_index], 0.85
            )

    required_value_roles = {"current", "previous", "reported_growth_rate"}
    if "item" not in mapped and required_value_roles.issubset(mapped):
        item_index = _infer_item_column(following_rows or [])
        if item_index is not None:
            mapped["item"] = MappedColumn("item", item_index, _cell(row, item_index), 0.9)

    return [
        mapped[role]
        for role in ("item", "current", "previous", "reported_growth_rate")
        if role in mapped
    ]


def _find_structural_header(rows: list[list[str]]) -> tuple[int, int] | None:
    for row_index, row in enumerate(rows[:8]):
        year_count = len(
            {
                year
                for cell in row
                if (year := _year_from_header(cell)) is not None
            }
        )
        if year_count >= 2 and any(_is_growth_header(cell) for cell in row):
            return row_index, year_count
        if row_index + 1 < min(len(rows), 8):
            merged = _merge_header_rows(row, rows[row_index + 1])
            merged_year_count = len(
                {
                    year
                    for cell in merged
                    if (year := _year_from_header(cell)) is not None
                }
            )
            if merged_year_count >= 2 and any(_is_growth_header(cell) for cell in merged):
                return row_index + 1, merged_year_count
    return None


def _merge_item_continuations(
    rows: list[list[str]],
    header_index: int,
    columns: dict[str, MappedColumn],
) -> list[list[str]]:
    merged_rows = [row.copy() for row in rows]
    item_index = columns["item"].index
    value_indices = [
        columns[role].index
        for role in ("current", "previous", "reported_growth_rate")
    ]
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
            normalized = _normalize_text(cell)
            if _recognize_item(normalized) is not None:
                scores[index] = scores.get(index, 0) + 3
            elif any(fragment in normalized for fragment in METRIC_FRAGMENTS):
                scores[index] = scores.get(index, 0) + 1
    if not scores:
        return None
    return max(scores, key=lambda index: (scores[index], -index))


def _count_metric_rows(rows: list[list[str]]) -> int:
    count = 0
    for row in rows:
        combined = _normalize_text("".join(row))
        if _recognize_item(combined) is not None or any(
            fragment in combined for fragment in METRIC_FRAGMENTS
        ):
            count += 1
    return count


def _find_alias_column(
    headers: list[str], aliases: tuple[str, ...], excluded: int
) -> int | None:
    for index, header in enumerate(headers):
        if index != excluded and any(alias == header or alias in header for alias in aliases):
            return index
    return None


def _merge_header_rows(first: list[str], second: list[str]) -> list[str]:
    width = max(len(first), len(second))
    return [
        _cell(first, index) + _cell(second, index)
        for index in range(width)
    ]


def _year_from_header(value: object) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", _normalize_text(value))
    return int(match.group()) if match else None


def _is_growth_header(value: object) -> bool:
    normalized = _normalize_text(value)
    return any(alias in normalized for alias in GROWTH_HEADERS)


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


def _column_gaps(indices: list[int]) -> list[int]:
    ordered = sorted(set(indices))
    return [right - left - 1 for left, right in zip(ordered, ordered[1:])] or [0]


def _normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    return "".join(text.split()).replace("（", "(").replace("）", ")")


def _clean_item_name(value: str) -> str:
    return "".join(value.split())


def _recognize_item(item_name: str) -> str | None:
    normalized = _normalize_text(item_name)
    for alias, canonical in KNOWN_ITEM_ALIASES:
        if alias in normalized:
            return canonical
    return None


def _looks_like_repeated_header(current: str, previous: str, reported: str) -> bool:
    combined = _normalize_text(current + previous + reported)
    return bool(re.search(r"(?:19|20)\d{2}年", combined)) and "增减" in combined


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

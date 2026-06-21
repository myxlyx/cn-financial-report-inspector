"""Rule-based semantic mapping for annual key financial metric tables."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from fri_checks.schema import CheckTask, MappedColumn, MappedRow, MappingResult

ITEM_HEADERS = ("项目", "主要会计数据", "主要财务指标", "指标名称")
CURRENT_PERIOD_ALIASES = ("本年", "本期", "本报告期", "本期数")
PREVIOUS_PERIOD_ALIASES = ("上年", "上期", "上年同期", "上期数")
GROWTH_HEADERS = (
    "本期比上年同期增减",
    "本年比上年增减",
    "比上年同期增减",
    "同比增减",
    "较上年同期增减",
    "增减比例",
    "变动幅度",
)
KNOWN_ITEMS = (
    "营业收入",
    "利润总额",
    "归属于上市公司股东的净利润",
    "归属于上市公司股东的扣除非经常性损益的净利润",
    "经营活动产生的现金流量净额",
    "归属于上市公司股东的净资产",
    "总资产",
    "基本每股收益",
    "稀释每股收益",
    "加权平均净资产收益率",
)


class BaseSemanticMapper(ABC):
    @abstractmethod
    def map_table(self, table: dict[str, Any], report_id: str = "") -> MappingResult:
        """Map one extracted table into structured calculation tasks."""


class RuleBasedAnnualKeyMetricsMapper(BaseSemanticMapper):
    mapping_source = "rule_based"

    def map_table(self, table: dict[str, Any], report_id: str = "") -> MappingResult:
        table_id = str(table.get("table_id", ""))
        page = _safe_int(table.get("page"))
        rows = _coerce_rows(table.get("data"))
        candidate_score, candidate_notes = self._candidate_score(table, rows)
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

        confidence = min(
            candidate_score,
            min(column.confidence for column in columns),
        )
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
        preview = _normalize_text("".join(cell for row in rows[:3] for cell in row))
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
        if any(header in preview for header in GROWTH_HEADERS):
            score += 0.2
            notes.append("growth_header_detected")
        if len(set(re.findall(r"(?:19|20)\d{2}", preview))) >= 2:
            score += 0.15
            notes.append("multiple_years_detected")
        return min(score, 0.99), notes

    def _find_header(
        self,
        rows: list[list[str]],
    ) -> tuple[int | None, list[MappedColumn]]:
        best_index: int | None = None
        best_columns: list[MappedColumn] = []
        for row_index, row in enumerate(rows[:5]):
            columns = _map_header_columns(row)
            if len(columns) > len(best_columns):
                best_index = row_index
                best_columns = columns
            if len(columns) == 4:
                return row_index, columns
        return best_index, best_columns

    def _map_row(
        self,
        row: list[str],
        row_index: int,
        report_id: str,
        table_id: str,
        page: int,
        columns: dict[str, MappedColumn],
    ) -> tuple[MappedRow | None, CheckTask | None]:
        item = _cell(row, columns["item"].index)
        item_name = _clean_item_name(item)
        if not item_name or item_name in ITEM_HEADERS:
            return None, None

        current_raw = _cell(row, columns["current"].index)
        previous_raw = _cell(row, columns["previous"].index)
        reported_raw = _cell(row, columns["reported_growth_rate"].index)
        recognized_item = _recognize_item(item_name)
        row_confidence = 0.95 if recognized_item else 0.85
        notes: list[str] = []

        if _looks_like_repeated_header(current_raw, previous_raw, reported_raw):
            return None, None
        if "百分点" in _normalize_text(reported_raw):
            notes.append("percentage_point_change_not_supported")
            return (
                MappedRow(
                    row_index=row_index,
                    item_name=item_name,
                    cells=row,
                    recognized_item=recognized_item,
                    confidence=row_confidence,
                    notes=notes,
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
            current_cell=columns["current"].index,
            previous_cell=columns["previous"].index,
            reported_cell=columns["reported_growth_rate"].index,
            current_value_raw=current_raw,
            previous_value_raw=previous_raw,
            reported_growth_rate_raw=reported_raw,
            confidence=row_confidence,
            notes=notes.copy(),
        )
        return mapped_row, task


def _map_header_columns(row: list[str]) -> list[MappedColumn]:
    normalized = [_normalize_text(cell) for cell in row]
    mapped: dict[str, MappedColumn] = {}

    for index, header in enumerate(normalized):
        if any(alias == header or alias in header for alias in ITEM_HEADERS):
            mapped["item"] = MappedColumn("item", index, row[index], 0.95)
            break

    for index, header in enumerate(normalized):
        if any(alias in header for alias in GROWTH_HEADERS):
            mapped["reported_growth_rate"] = MappedColumn(
                "reported_growth_rate", index, row[index], 0.95
            )
            break

    year_columns: list[tuple[int, int]] = []
    for index, header in enumerate(normalized):
        match = re.search(r"(?:19|20)\d{2}", header)
        if match:
            year_columns.append((int(match.group()), index))
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
            mapped["current"] = MappedColumn(
                "current", current_index, row[current_index], 0.85
            )
        if previous_index is not None:
            mapped["previous"] = MappedColumn(
                "previous", previous_index, row[previous_index], 0.85
            )

    return [
        mapped[role]
        for role in ("item", "current", "previous", "reported_growth_rate")
        if role in mapped
    ]


def _find_alias_column(
    headers: list[str], aliases: tuple[str, ...], excluded: int
) -> int | None:
    for index, header in enumerate(headers):
        if index != excluded and any(alias == header or alias in header for alias in aliases):
            return index
    return None


def _normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    return "".join(text.split()).replace("（", "(").replace("）", ")")


def _clean_item_name(value: str) -> str:
    return "".join(value.split())


def _recognize_item(item_name: str) -> str | None:
    for known_item in KNOWN_ITEMS:
        if known_item in item_name:
            return known_item
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


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

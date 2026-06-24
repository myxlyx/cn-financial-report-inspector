"""Run quarterly sum checks over parsed report directories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from fri_checks.number_parser import parse_financial_number
from fri_checks.quarterly_mapper import (
    BaseQuarterlyMapper,
    RuleBasedQuarterlyMetricsMapper,
    detect_table_unit,
    normalize_item_key,
    recognize_quarterly_item,
)
from fri_checks.quarterly_sum_checker import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    check_quarterly_sum_tasks,
)
from fri_checks.schema import (
    QuarterlyAnnualReference,
    QuarterlyCheckTask,
    QuarterlyCheckResult,
    QuarterlyCheckSummary,
    QuarterlyMappingResult,
)

MISSING_GROWTH_CHECKS_MESSAGE = (
    "Missing growth_rate_checks.jsonl. "
    "Please run scripts/run_growth_rate_checks.py first."
)


@dataclass
class _TaskCandidate:
    task: QuarterlyCheckTask
    mapping: QuarterlyMappingResult
    table: dict
    order: int


def run_report_quarterly_sum_checks(
    report_dir: Path,
    absolute_tolerance: Decimal = DEFAULT_ABSOLUTE_TOLERANCE,
    mapper: BaseQuarterlyMapper | None = None,
) -> QuarterlyCheckSummary:
    report_dir = report_dir.resolve()
    metadata = _read_json(report_dir / "metadata.json")
    report_id = str(metadata.get("report_id") or report_dir.name)
    index_path = report_dir / "tables_index.jsonl"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing table index: {index_path}")

    checks_dir = report_dir / "checks"
    growth_checks_path = checks_dir / "growth_rate_checks.jsonl"
    if not growth_checks_path.exists():
        raise FileNotFoundError(f"{MISSING_GROWTH_CHECKS_MESSAGE} Report: {report_id}")

    annual_references = build_annual_reference_map(
        growth_checks_path,
        report_id=report_id,
        report_dir=report_dir,
    )
    quarterly_mapper = mapper or RuleBasedQuarterlyMetricsMapper()
    table_records = list(_read_jsonl(index_path))
    results: list[QuarterlyCheckResult] = []
    task_candidates: list[_TaskCandidate] = []
    mapping_diagnostics: list[dict] = []
    candidate_tables = 0
    mapping_failed_count = 0
    task_order = 0
    warnings: list[str] = []
    if not annual_references:
        warnings.append("no_annual_references_from_growth_rate_checks")

    for table_record in table_records:
        try:
            table = _load_table(report_dir, table_record)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            mapping_failed_count += 1
            mapping_diagnostics.append(
                {
                    "report_id": report_id,
                    "table_id": str(table_record.get("table_id", "")),
                    "page": int(table_record.get("page") or 0),
                    "is_candidate": False,
                    "status": "mapping_failed",
                    "confidence": 0.0,
                    "notes": [f"table_load_failed:{type(exc).__name__}"],
                    "preview_rows": [],
                }
            )
            continue

        mapping = quarterly_mapper.map_table(
            table,
            annual_references=annual_references,
            report_id=report_id,
        )
        mapping_diagnostics.append(_mapping_diagnostic(mapping, table))
        if mapping.is_candidate:
            candidate_tables += 1
        if mapping.status == "mapping_failed":
            mapping_failed_count += 1
            continue
        for task in mapping.tasks:
            task_candidates.append(_TaskCandidate(task, mapping, table, task_order))
            task_order += 1

    selected_tasks, duplicate_diagnostics = _deduplicate_quarterly_tasks(task_candidates)
    mapping_diagnostics.extend(duplicate_diagnostics)
    results.extend(
        check_quarterly_sum_tasks(
            selected_tasks,
            absolute_tolerance=absolute_tolerance,
        )
    )

    checks_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        checks_dir / "quarterly_sum_checks.jsonl",
        (result.to_dict() for result in results),
    )
    _write_jsonl(
        checks_dir / "quarterly_mapping_diagnostics.jsonl",
        mapping_diagnostics,
    )

    summary = QuarterlyCheckSummary(
        report_id=report_id,
        candidate_tables=candidate_tables,
        checks_count=len(results),
        ok_count=sum(result.status == "ok" for result in results),
        mismatch_count=sum(result.status == "mismatch" for result in results),
        not_applicable_count=sum(
            result.status == "not_applicable" for result in results
        ),
        parse_failed_count=sum(result.status == "parse_failed" for result in results),
        mapping_failed_count=mapping_failed_count,
        review_required_count=sum(result.review_required for result in results),
        duplicate_skipped_count=len(duplicate_diagnostics),
        warnings=warnings,
    )
    _write_json(checks_dir / "quarterly_sum_summary.json", summary.to_dict())
    return summary


def run_all_quarterly_sum_checks(
    parsed_dir: Path,
    report_id: str | None = None,
    absolute_tolerance: Decimal = DEFAULT_ABSOLUTE_TOLERANCE,
    mapper: BaseQuarterlyMapper | None = None,
) -> list[QuarterlyCheckSummary]:
    parsed_dir = parsed_dir.resolve()
    report_dirs = _discover_report_dirs(parsed_dir, report_id=report_id)

    summaries: list[QuarterlyCheckSummary] = []
    for report_dir in report_dirs:
        if not report_dir.is_dir():
            raise FileNotFoundError(f"Report directory not found: {report_dir}")
        if not (report_dir / "tables_index.jsonl").exists():
            continue
        summaries.append(
            run_report_quarterly_sum_checks(
                report_dir,
                absolute_tolerance=absolute_tolerance,
                mapper=mapper,
            )
        )
    return summaries


def build_annual_reference_map(
    growth_checks_path: Path,
    report_id: str = "",
    report_dir: Path | None = None,
) -> dict[str, QuarterlyAnnualReference]:
    references: dict[str, QuarterlyAnnualReference] = {}
    unit_cache: dict[str, tuple[str | None, Decimal]] = {}
    for check in _read_jsonl(growth_checks_path):
        item_name = str(check.get("item_name", ""))
        recognized = recognize_quarterly_item(item_name)
        if recognized is None:
            continue
        key = normalize_item_key(recognized)
        if key in references:
            continue
        source_table_id = str(check.get("table_id", ""))
        unit, value_scale = _annual_table_unit(
            report_dir=report_dir,
            table_id=source_table_id,
            cache=unit_cache,
        )
        references[key] = QuarterlyAnnualReference(
            report_id=str(check.get("report_id") or report_id),
            item_name=recognized,
            annual_value_raw=str(check.get("current_value_raw", "")),
            source_table_id=source_table_id,
            source_page=int(check.get("page") or 0),
            source_row_index=int(check.get("row_index") or 0),
            unit=unit,
            value_scale=value_scale,
        )
    return references


def _annual_table_unit(
    report_dir: Path | None,
    table_id: str,
    cache: dict[str, tuple[str | None, Decimal]],
) -> tuple[str | None, Decimal]:
    if not report_dir or not table_id:
        return None, Decimal("1")
    if table_id in cache:
        return cache[table_id]

    path = report_dir / "tables" / f"{table_id}.json"
    try:
        table = _read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        result = (None, Decimal("1"))
    else:
        result = detect_table_unit(table)
    cache[table_id] = result
    return result


def _deduplicate_quarterly_tasks(
    candidates: list[_TaskCandidate],
) -> tuple[list[QuarterlyCheckTask], list[dict]]:
    selected: dict[str, _TaskCandidate] = {}
    duplicate_diagnostics: list[dict] = []

    for candidate in candidates:
        key = normalize_item_key(str(candidate.task.item_name))
        existing = selected.get(key)
        if existing is None:
            selected[key] = candidate
            continue

        if _candidate_rank(candidate) > _candidate_rank(existing):
            duplicate_diagnostics.append(
                _duplicate_diagnostic(
                    skipped=existing,
                    kept=candidate,
                    reason="replaced_by_higher_ranked_candidate",
                )
            )
            selected[key] = candidate
        else:
            duplicate_diagnostics.append(
                _duplicate_diagnostic(
                    skipped=candidate,
                    kept=existing,
                    reason="lower_confidence_candidate",
                )
            )

    ordered = sorted(selected.values(), key=lambda candidate: candidate.order)
    return [candidate.task for candidate in ordered], duplicate_diagnostics


def _candidate_rank(candidate: _TaskCandidate) -> tuple[float, int, int, int, int]:
    context_score = int(
        "quarterly_metrics_context" in candidate.mapping.notes
        or "quarterly_context_keyword" in candidate.mapping.notes
        or "分季度" in _table_context(candidate.table)
    )
    parseable = int(
        all(
            parse_financial_number(value).status == "ok"
            for value in (
                candidate.task.q1_raw,
                candidate.task.q2_raw,
                candidate.task.q3_raw,
                candidate.task.q4_raw,
            )
        )
    )
    return (
        candidate.mapping.confidence,
        context_score,
        len(candidate.mapping.tasks),
        parseable,
        -candidate.order,
    )


def _duplicate_diagnostic(
    skipped: _TaskCandidate,
    kept: _TaskCandidate,
    reason: str,
) -> dict:
    diagnostic = _mapping_diagnostic(skipped.mapping, skipped.table)
    diagnostic.update(
        {
            "status": "skipped",
            "item_name": skipped.task.item_name,
            "row_index": skipped.task.row_index,
            "kept_table_id": kept.task.table_id,
            "kept_row_index": kept.task.row_index,
            "notes": skipped.mapping.notes
            + [
                f"duplicate_quarterly_item:{normalize_item_key(str(skipped.task.item_name))}",
                reason,
            ],
        }
    )
    return diagnostic


def _table_context(table: dict) -> str:
    return str(table.get("section_candidate", "")) + str(table.get("title_candidate", ""))


def _discover_report_dirs(parsed_dir: Path, report_id: str | None) -> list[Path]:
    if not parsed_dir.exists():
        return []

    index_paths = set(parsed_dir.rglob("tables_index.jsonl"))
    direct_index = parsed_dir / "tables_index.jsonl"
    if direct_index.exists():
        index_paths.add(direct_index)
    report_dirs = sorted(path.parent for path in index_paths)
    if report_id:
        matches = [path for path in report_dirs if path.name == report_id]
        if not matches:
            raise FileNotFoundError(
                f"Report directory not found under {parsed_dir}: {report_id}"
            )
        return matches
    return report_dirs


def _load_table(report_dir: Path, record: dict) -> dict:
    json_path = record.get("json_path")
    if json_path:
        candidate = report_dir / str(json_path)
    else:
        table_id = str(record.get("table_id", ""))
        candidate = report_dir / "tables" / f"{table_id}.json"

    if candidate.exists():
        return _read_json(candidate)
    if isinstance(record.get("data"), list):
        return record
    raise FileNotFoundError(f"Missing table JSON: {candidate}")


def _mapping_diagnostic(mapping: QuarterlyMappingResult, table: dict) -> dict:
    data = table.get("data")
    preview_rows = []
    if isinstance(data, list):
        preview_rows = [row for row in data[:3] if isinstance(row, list)]
    return {
        "report_id": mapping.report_id,
        "table_id": mapping.table_id,
        "page": mapping.page,
        "is_candidate": mapping.is_candidate,
        "status": mapping.status,
        "confidence": mapping.confidence,
        "notes": mapping.notes,
        "preview_rows": preview_rows,
    }


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def _read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            yield data


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

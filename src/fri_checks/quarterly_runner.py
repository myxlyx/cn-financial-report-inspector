"""Run quarterly sum checks over parsed report directories."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from fri_checks.quarterly_mapper import (
    BaseQuarterlyMapper,
    RuleBasedQuarterlyMetricsMapper,
    normalize_item_key,
    recognize_quarterly_item,
)
from fri_checks.quarterly_sum_checker import (
    DEFAULT_ABSOLUTE_TOLERANCE,
    check_quarterly_sum_tasks,
)
from fri_checks.schema import (
    QuarterlyAnnualReference,
    QuarterlyCheckResult,
    QuarterlyCheckSummary,
    QuarterlyMappingResult,
)

MISSING_GROWTH_CHECKS_MESSAGE = (
    "Missing growth_rate_checks.jsonl. "
    "Please run scripts/run_growth_rate_checks.py first."
)


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

    annual_references = build_annual_reference_map(growth_checks_path, report_id=report_id)
    quarterly_mapper = mapper or RuleBasedQuarterlyMetricsMapper()
    table_records = list(_read_jsonl(index_path))
    results: list[QuarterlyCheckResult] = []
    mapping_diagnostics: list[dict] = []
    candidate_tables = 0
    mapping_failed_count = 0
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
        results.extend(
            check_quarterly_sum_tasks(
                mapping.tasks,
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
) -> dict[str, QuarterlyAnnualReference]:
    references: dict[str, QuarterlyAnnualReference] = {}
    for check in _read_jsonl(growth_checks_path):
        item_name = str(check.get("item_name", ""))
        recognized = recognize_quarterly_item(item_name)
        if recognized is None:
            continue
        key = normalize_item_key(recognized)
        if key in references:
            continue
        references[key] = QuarterlyAnnualReference(
            report_id=str(check.get("report_id") or report_id),
            item_name=recognized,
            annual_value_raw=str(check.get("current_value_raw", "")),
            source_table_id=str(check.get("table_id", "")),
            source_page=int(check.get("page") or 0),
            source_row_index=int(check.get("row_index") or 0),
        )
    return references


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

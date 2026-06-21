"""Run growth-rate checks over parsed report directories."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from fri_checks.growth_rate_checker import DEFAULT_TOLERANCE, check_growth_rate_tasks
from fri_checks.schema import CheckResult, CheckSummary
from fri_checks.semantic_mapper import (
    BaseSemanticMapper,
    RuleBasedAnnualKeyMetricsMapper,
)


def run_report_checks(
    report_dir: Path,
    tolerance: Decimal = DEFAULT_TOLERANCE,
    mapper: BaseSemanticMapper | None = None,
) -> CheckSummary:
    report_dir = report_dir.resolve()
    metadata = _read_json(report_dir / "metadata.json")
    report_id = str(metadata.get("report_id") or report_dir.name)
    index_path = report_dir / "tables_index.jsonl"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing table index: {index_path}")

    semantic_mapper = mapper or RuleBasedAnnualKeyMetricsMapper()
    table_records = list(_read_jsonl(index_path))
    results: list[CheckResult] = []
    candidate_tables = 0
    mapping_failed_count = 0

    for table_record in table_records:
        try:
            table = _load_table(report_dir, table_record)
        except (OSError, json.JSONDecodeError, ValueError):
            mapping_failed_count += 1
            continue

        mapping = semantic_mapper.map_table(table, report_id=report_id)
        if mapping.is_candidate:
            candidate_tables += 1
        if mapping.status == "mapping_failed":
            mapping_failed_count += 1
            continue
        results.extend(check_growth_rate_tasks(mapping.tasks, tolerance=tolerance))

    checks_dir = report_dir / "checks"
    checks_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        checks_dir / "growth_rate_checks.jsonl",
        (result.to_dict() for result in results),
    )

    summary = CheckSummary(
        report_id=report_id,
        checks_count=len(results),
        ok_count=sum(result.status == "ok" for result in results),
        mismatch_count=sum(result.status == "mismatch" for result in results),
        review_required_count=sum(result.review_required for result in results),
        not_applicable_count=sum(
            result.status == "not_applicable" for result in results
        ),
        parse_failed_count=sum(result.status == "parse_failed" for result in results),
        mapping_failed_count=mapping_failed_count,
        tables_scanned=len(table_records),
        candidate_tables=candidate_tables,
    )
    _write_json(checks_dir / "growth_rate_summary.json", summary.to_dict())
    return summary


def run_all_reports(
    parsed_dir: Path,
    report_id: str | None = None,
    tolerance: Decimal = DEFAULT_TOLERANCE,
    mapper: BaseSemanticMapper | None = None,
) -> list[CheckSummary]:
    parsed_dir = parsed_dir.resolve()
    report_dirs = _discover_report_dirs(parsed_dir, report_id=report_id)

    summaries: list[CheckSummary] = []
    for report_dir in report_dirs:
        if not report_dir.is_dir():
            raise FileNotFoundError(f"Report directory not found: {report_dir}")
        if not (report_dir / "tables_index.jsonl").exists():
            continue
        summaries.append(
            run_report_checks(
                report_dir,
                tolerance=tolerance,
                mapper=mapper,
            )
        )
    return summaries


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

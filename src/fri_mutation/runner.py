"""Generate, label, and validate growth-rate mutation samples."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import shutil
from typing import Any, Iterable

from fri_checks.growth_rate_checker import DEFAULT_TOLERANCE
from fri_checks.runner import run_report_checks
from fri_mutation.growth_rate_mutator import (
    mutate_table,
    select_mutation_candidates,
)
from fri_mutation.schema import (
    MutationCandidate,
    MutationLabel,
    MutationStrategy,
    MutationSummary,
)

MUTATION_TYPE = "growth_rate_reported_value_error"


def generate_report_mutations(
    source_report_dir: Path,
    output_dir: Path,
    max_mutations: int = 3,
    strategy: MutationStrategy = "add_delta",
    delta: Decimal = Decimal("5.00"),
    force: bool = False,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> MutationSummary:
    if max_mutations < 0:
        raise ValueError("max_mutations must be non-negative")

    source_report_dir = source_report_dir.resolve()
    checks_path = source_report_dir / "checks" / "growth_rate_checks.jsonl"
    if not checks_path.exists():
        raise FileNotFoundError(
            f"Missing growth-rate checks: {checks_path}. "
            "Run scripts/run_growth_rate_checks.py first."
        )

    source_metadata = _read_json(source_report_dir / "metadata.json")
    source_quality = _read_json(source_report_dir / "parse_quality.json")
    source_report_id = str(source_metadata.get("report_id") or source_report_dir.name)
    source_index = list(_read_jsonl(source_report_dir / "tables_index.jsonl"))
    candidates = select_mutation_candidates(_read_jsonl(checks_path))

    report_output_dir = output_dir.resolve() / source_report_id
    if report_output_dir.exists():
        if not force:
            raise FileExistsError(
                f"Mutation output already exists: {report_output_dir}. Use --force to replace it."
            )
        shutil.rmtree(report_output_dir)
    report_output_dir.mkdir(parents=True, exist_ok=True)

    mutation_ids: list[str] = []
    mutation_dirs: list[Path] = []
    validation_detected_count = 0
    skipped_candidates_count = 0

    for candidate in candidates:
        if len(mutation_ids) >= max_mutations:
            break
        try:
            table_record = _find_table_record(source_index, candidate.table_id)
            relative_table_path = _table_json_path(table_record, candidate.table_id)
            source_table = _read_json(source_report_dir / relative_table_path)
            mutated_table, original_raw, mutated_raw = mutate_table(
                source_table,
                candidate,
                strategy=strategy,
                delta=delta,
                tolerance=tolerance,
            )
        except (FileNotFoundError, ValueError):
            skipped_candidates_count += 1
            continue

        mutation_id = f"growth_rate_mutation_{len(mutation_ids) + 1:03d}"
        mutation_dir = report_output_dir / mutation_id
        _copy_table_json_files(source_report_dir, mutation_dir)
        _write_json(mutation_dir / relative_table_path, mutated_table)
        _write_mutated_index(
            mutation_dir / "tables_index.jsonl",
            source_index,
            candidate.table_id,
            mutated_table,
        )
        _write_mutated_metadata(
            mutation_dir,
            source_metadata,
            source_quality,
            source_report_id,
            mutation_id,
        )

        run_report_checks(mutation_dir, tolerance=tolerance)
        validation = _validate_detection(mutation_dir, candidate)
        if validation["detected"]:
            validation_detected_count += 1

        label = MutationLabel(
            mutation_id=mutation_id,
            source_report_id=source_report_id,
            mutation_type=MUTATION_TYPE,
            strategy=strategy,
            target={
                "table_id": candidate.table_id,
                "page": candidate.page,
                "row_index": candidate.row_index,
                "item_name": candidate.item_name,
                "reported_cell": candidate.reported_cell,
                "reported_cell_coord": candidate.reported_cell_coord,
            },
            original={
                "reported_growth_rate_raw": original_raw,
                "computed_growth_rate": candidate.computed_growth_rate,
            },
            mutated={"reported_growth_rate_raw": mutated_raw},
            expected_detection={
                "status": "mismatch",
                "review_required": True,
                "should_detect": True,
            },
            validation=validation,
        )
        _write_json(mutation_dir / "mutation_label.json", label.to_dict())
        mutation_ids.append(mutation_id)
        mutation_dirs.append(mutation_dir)

    summary = MutationSummary(
        source_report_id=source_report_id,
        mutations_count=len(mutation_ids),
        mutation_ids=mutation_ids,
        validation_detected_count=validation_detected_count,
        skipped_candidates_count=skipped_candidates_count,
    )
    summary_data = summary.to_dict()
    _write_json(report_output_dir / "mutation_summary.json", summary_data)
    for mutation_dir in mutation_dirs:
        _write_json(mutation_dir / "mutation_summary.json", summary_data)
    return summary


def discover_source_reports(parsed_dir: Path, report_id: str | None = None) -> list[Path]:
    parsed_dir = parsed_dir.resolve()
    if report_id:
        report_dir = parsed_dir / report_id
        if not report_dir.is_dir():
            raise FileNotFoundError(f"Report directory not found: {report_dir}")
        return [report_dir]
    if not parsed_dir.exists():
        return []
    return sorted(
        path
        for path in parsed_dir.iterdir()
        if path.is_dir() and (path / "tables_index.jsonl").exists()
    )


def _copy_table_json_files(source_report_dir: Path, mutation_dir: Path) -> None:
    destination = mutation_dir / "tables"
    destination.mkdir(parents=True, exist_ok=True)
    for source in sorted((source_report_dir / "tables").glob("*.json")):
        shutil.copy2(source, destination / source.name)


def _write_mutated_index(
    path: Path,
    records: list[dict[str, Any]],
    table_id: str,
    mutated_table: dict[str, Any],
) -> None:
    mutated_records = deepcopy(records)
    for record in mutated_records:
        if record.get("table_id") == table_id:
            record["data"] = deepcopy(mutated_table.get("data", []))
            break
    _write_jsonl(path, mutated_records)


def _write_mutated_metadata(
    mutation_dir: Path,
    source_metadata: dict[str, Any],
    source_quality: dict[str, Any],
    source_report_id: str,
    mutation_id: str,
) -> None:
    metadata = deepcopy(source_metadata)
    metadata.update(
        {
            "report_id": mutation_id,
            "source_report_id": source_report_id,
            "is_mutated": True,
            "mutation_id": mutation_id,
            "mutation_type": MUTATION_TYPE,
            "source_pdf_unmodified": True,
            "markdown_path": None,
            "pages_jsonl_path": None,
        }
    )
    quality = deepcopy(source_quality)
    quality.update(
        {
            "report_id": mutation_id,
            "source_report_id": source_report_id,
            "is_mutated": True,
            "mutation_id": mutation_id,
            "mutation_type": MUTATION_TYPE,
        }
    )
    _write_json(mutation_dir / "metadata.json", metadata)
    _write_json(mutation_dir / "parse_quality.json", quality)


def _validate_detection(
    mutation_dir: Path, candidate: MutationCandidate
) -> dict[str, Any]:
    results = list(
        _read_jsonl(mutation_dir / "checks" / "growth_rate_checks.jsonl")
    )
    matched = next(
        (
            result
            for result in results
            if result.get("table_id") == candidate.table_id
            and result.get("row_index") == candidate.row_index
        ),
        None,
    )
    if matched is None:
        return {"detected": False, "reason": "target check result not found"}

    detected = matched.get("status") == "mismatch" and matched.get(
        "review_required"
    ) is True
    validation: dict[str, Any] = {"detected": detected}
    if detected:
        validation["matched_check_result"] = {
            "table_id": matched.get("table_id"),
            "row_index": matched.get("row_index"),
            "item_name": matched.get("item_name"),
            "status": matched.get("status"),
            "review_required": matched.get("review_required"),
        }
    else:
        validation["reason"] = (
            f"target check status={matched.get('status')}, "
            f"review_required={matched.get('review_required')}"
        )
    return validation


def _find_table_record(records: list[dict[str, Any]], table_id: str) -> dict[str, Any]:
    for record in records:
        if record.get("table_id") == table_id:
            return record
    raise FileNotFoundError(f"Table {table_id} is missing from tables_index.jsonl")


def _table_json_path(record: dict[str, Any], table_id: str) -> Path:
    relative = Path(str(record.get("json_path") or f"tables/{table_id}.json"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe table JSON path: {relative}")
    return relative


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            yield data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

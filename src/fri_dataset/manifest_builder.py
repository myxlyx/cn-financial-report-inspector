"""Build a unified benchmark index from parser, checker, and mutation outputs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Iterable

from fri_dataset.schema import (
    CheckManifestRecord,
    DatasetManifest,
    MutationManifestRecord,
    ReportManifestRecord,
)
from fri_dataset.stats import build_dataset_stats
from fri_dataset.validation import validate_dataset_records

DATASET_VERSION = "0.1"


def build_dataset_manifest(
    batch_name: str,
    source_dir: Path,
    parsed_dir: Path,
    mutated_dir: Path,
    batch_report: Path,
    output_dir: Path,
    project_root: Path,
    force: bool = False,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    source_dir = source_dir.resolve()
    parsed_dir = parsed_dir.resolve()
    mutated_dir = mutated_dir.resolve()
    batch_report = batch_report.resolve()
    output_dir = output_dir.resolve()
    _validate_input_paths(source_dir, parsed_dir, mutated_dir, batch_report)
    _prepare_output_dir(
        output_dir,
        force=force,
        allowed_root=project_root,
        forbidden={project_root, source_dir, parsed_dir, mutated_dir},
    )

    batch_data = _read_json(batch_report)
    source_display = _display_path(source_dir, project_root)
    load_warnings: list[str] = []
    if str(batch_data.get("batch_name")) != batch_name:
        load_warnings.append("batch_report:batch_name_mismatch")

    report_records = _collect_reports(
        batch_name=batch_name,
        batch_data=batch_data,
        source_dir=source_dir,
        source_display=source_display,
        parsed_dir=parsed_dir,
        project_root=project_root,
        warnings=load_warnings,
    )
    reports = [record.to_dict() for record in report_records]
    checks = _collect_checks(
        batch_name=batch_name,
        reports=reports,
        parsed_dir=parsed_dir,
        warnings=load_warnings,
    )
    mutations = _collect_mutations(
        batch_name=batch_name,
        reports=reports,
        mutated_dir=mutated_dir,
        project_root=project_root,
        warnings=load_warnings,
    )

    validation_warnings = load_warnings + validate_dataset_records(
        reports, checks, mutations, project_root
    )
    validation_warnings.extend(
        _validate_batch_counts(batch_data, reports, checks, mutations)
    )
    validation_warnings = list(dict.fromkeys(validation_warnings))
    problem_cases = batch_data.get("problem_cases")
    if not isinstance(problem_cases, list):
        problem_cases = []

    stats = build_dataset_stats(
        reports=reports,
        checks=checks,
        mutations=mutations,
        problem_cases=problem_cases,
        validation_warnings=validation_warnings,
    )
    manifest = DatasetManifest(
        dataset_name=f"{batch_name}_growth_rate_benchmark",
        version=DATASET_VERSION,
        batch_name=batch_name,
        task="growth_rate_consistency_check",
        language="zh",
        document_type="Chinese listed-company annual report",
        source_dir=source_display,
        parsed_dir=_display_path(parsed_dir, project_root),
        mutated_dir=_display_path(mutated_dir, project_root),
        batch_report=_display_path(batch_report, project_root),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        reports_count=len(reports),
        original_checks_count=len(checks),
        mutation_samples_count=len(mutations),
        notes=[
            "Original PDFs are not modified.",
            "Mutations are applied to parsed table JSON only.",
            "This dataset covers only reported growth-rate consistency checks in annual key financial metrics tables.",
        ],
    ).to_dict()

    _write_json(output_dir / "dataset_manifest.json", manifest)
    _write_jsonl(output_dir / "reports_manifest.jsonl", reports)
    _write_jsonl(output_dir / "checks_manifest.jsonl", checks)
    _write_jsonl(output_dir / "mutations_manifest.jsonl", mutations)
    _write_json(output_dir / "dataset_stats.json", stats)
    (output_dir / "dataset_card.md").write_text(
        _render_dataset_card(manifest, stats, output_dir, project_root),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "manifest": manifest,
        "stats": stats,
        "reports": reports,
        "checks": checks,
        "mutations": mutations,
        "output_dir": output_dir,
    }


def _collect_reports(
    batch_name: str,
    batch_data: dict[str, Any],
    source_dir: Path,
    source_display: str,
    parsed_dir: Path,
    project_root: Path,
    warnings: list[str],
) -> list[ReportManifestRecord]:
    batch_reports = batch_data.get("reports")
    if not isinstance(batch_reports, list):
        raise ValueError("Batch report does not contain a reports list")
    problem_flags = _problem_flags_by_report(batch_data.get("problem_cases"))
    records: list[ReportManifestRecord] = []
    included_sources: set[str] = set()

    for batch_record in batch_reports:
        if not isinstance(batch_record, dict):
            continue
        raw_source = str(batch_record.get("source_pdf") or "")
        if not _path_has_prefix(raw_source, source_display):
            continue
        report_id = str(batch_record.get("report_id") or "")
        if not report_id:
            warnings.append("report:missing_report_id")
            continue
        report_dir = parsed_dir / report_id
        metadata_path = report_dir / "metadata.json"
        if not metadata_path.is_file():
            warnings.append(f"report:{report_id}:parsed_metadata_missing")
            metadata: dict[str, Any] = {}
        else:
            metadata = _read_json(metadata_path)
        quality = _read_optional_json(report_dir / "parse_quality.json")
        check_summary = _read_optional_json(
            report_dir / "checks" / "growth_rate_summary.json"
        )

        source_path = _resolve_source_pdf(raw_source, source_dir, project_root)
        source_pdf = _display_path(source_path, project_root)
        included_sources.add(source_path.name.casefold())
        digest = _sha256_file(source_path) if source_path.is_file() else ""
        if not source_path.is_file():
            warnings.append(f"report:{report_id}:source_pdf_missing")

        parse_warnings = metadata.get("parse_warnings")
        warning_count = (
            len(parse_warnings)
            if isinstance(parse_warnings, list)
            else int(batch_record.get("parse_warnings_count") or 0)
        )
        records.append(
            ReportManifestRecord(
                record_type="report",
                batch_name=batch_name,
                report_id=report_id,
                source_pdf=source_pdf,
                source_pdf_sha256=digest,
                pdf_type=str(
                    metadata.get("pdf_type")
                    or batch_record.get("pdf_type")
                    or "unknown"
                ),
                page_count=int(
                    metadata.get("page_count")
                    or batch_record.get("page_count")
                    or 0
                ),
                text_pages=int(batch_record.get("text_pages") or 0),
                tables_count=int(
                    metadata.get("tables_count")
                    or batch_record.get("tables_count")
                    or 0
                ),
                quality_level=quality.get("quality_level")
                or batch_record.get("quality_level"),
                recommended_for_dataset=_optional_bool(
                    quality.get("recommended_for_dataset"),
                    batch_record.get("recommended_for_dataset"),
                ),
                growth_rate_checks_count=int(
                    check_summary.get("checks_count")
                    or batch_record.get("checks_count")
                    or 0
                ),
                ok_count=int(
                    check_summary.get("ok_count")
                    or batch_record.get("ok_count")
                    or 0
                ),
                mismatch_count=int(
                    check_summary.get("mismatch_count")
                    or batch_record.get("mismatch_count")
                    or 0
                ),
                not_applicable_count=int(
                    check_summary.get("not_applicable_count")
                    or batch_record.get("not_applicable_count")
                    or 0
                ),
                mapping_failed_count=int(
                    check_summary.get("mapping_failed_count")
                    or batch_record.get("mapping_failed_count")
                    or 0
                ),
                review_required_count=int(
                    check_summary.get("review_required_count")
                    or batch_record.get("review_required_count")
                    or 0
                ),
                has_mapping_diagnostics=(
                    report_dir / "checks" / "mapping_diagnostics.jsonl"
                ).is_file(),
                parse_warnings_count=warning_count,
                problem_flags=problem_flags.get(report_id, []),
            )
        )

    for source_path in sorted(source_dir.iterdir()):
        if (
            source_path.is_file()
            and source_path.suffix.lower() == ".pdf"
            and source_path.name.casefold() not in included_sources
        ):
            warnings.append(f"source_pdf_not_in_batch_report:{source_path.name}")
    return sorted(records, key=lambda record: record.report_id)


def _collect_checks(
    batch_name: str,
    reports: list[dict[str, Any]],
    parsed_dir: Path,
    warnings: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for report in reports:
        report_id = str(report["report_id"])
        checks_path = parsed_dir / report_id / "checks" / "growth_rate_checks.jsonl"
        if not checks_path.is_file():
            warnings.append(f"report:{report_id}:growth_rate_checks_missing")
            continue
        for check in _read_jsonl(checks_path):
            row_index = _safe_int(check.get("row_index"))
            current_cell = _safe_int(check.get("current_cell"))
            previous_cell = _safe_int(check.get("previous_cell"))
            reported_cell = _safe_int(check.get("reported_cell"))
            formula_type = str(check.get("formula_type") or "growth_rate")
            sample_id = _original_sample_id(
                report_id,
                str(check.get("table_id") or ""),
                row_index,
                formula_type,
            )
            record = CheckManifestRecord(
                record_type="original_check",
                batch_name=batch_name,
                sample_id=sample_id,
                report_id=report_id,
                source_pdf=str(report["source_pdf"]),
                check_type=str(check.get("check_type") or ""),
                formula_type=formula_type,
                table_id=str(check.get("table_id") or ""),
                page=_safe_int(check.get("page")),
                row_index=row_index,
                item_name=str(check.get("item_name") or ""),
                current_value_raw=str(check.get("current_value_raw") or ""),
                previous_value_raw=str(check.get("previous_value_raw") or ""),
                reported_growth_rate_raw=str(
                    check.get("reported_growth_rate_raw") or ""
                ),
                current_value=_optional_str(check.get("current_value")),
                previous_value=_optional_str(check.get("previous_value")),
                reported_growth_rate=_optional_str(
                    check.get("reported_growth_rate")
                ),
                computed_growth_rate=_optional_str(
                    check.get("computed_growth_rate")
                ),
                difference=_optional_str(check.get("difference")),
                tolerance=_optional_str(check.get("tolerance")),
                status=str(check.get("status") or ""),
                is_consistent=check.get("is_consistent"),
                review_required=check.get("review_required") is True,
                mapping_source=str(check.get("mapping_source") or ""),
                confidence=float(check.get("confidence") or 0.0),
                is_mutated=False,
                label="clean",
                evidence={
                    "current_cell": current_cell,
                    "previous_cell": previous_cell,
                    "reported_cell": reported_cell,
                    "current_cell_coord": [row_index, current_cell],
                    "previous_cell_coord": [row_index, previous_cell],
                    "reported_cell_coord": [row_index, reported_cell],
                },
                notes=[str(note) for note in check.get("notes") or []],
            )
            records.append(record.to_dict())
    return records


def _collect_mutations(
    batch_name: str,
    reports: list[dict[str, Any]],
    mutated_dir: Path,
    project_root: Path,
    warnings: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    reports_by_id = {str(report["report_id"]): report for report in reports}
    for source_report_id, report in sorted(reports_by_id.items()):
        group_dir = mutated_dir / source_report_id
        if not group_dir.is_dir():
            warnings.append(f"report:{source_report_id}:mutation_group_missing")
            continue
        for mutation_dir in sorted(group_dir.glob("growth_rate_mutation_*")):
            if not mutation_dir.is_dir():
                continue
            label_path = mutation_dir / "mutation_label.json"
            if not label_path.is_file():
                warnings.append(
                    f"mutation:{source_report_id}:{mutation_dir.name}:label_missing"
                )
                continue
            label = _read_json(label_path)
            mutation_id = str(label.get("mutation_id") or mutation_dir.name)
            target = label.get("target") if isinstance(label.get("target"), dict) else {}
            original = (
                label.get("original") if isinstance(label.get("original"), dict) else {}
            )
            mutated = (
                label.get("mutated") if isinstance(label.get("mutated"), dict) else {}
            )
            expected = (
                label.get("expected_detection")
                if isinstance(label.get("expected_detection"), dict)
                else {}
            )
            validation = (
                label.get("validation")
                if isinstance(label.get("validation"), dict)
                else {}
            )
            if not validation:
                warnings.append(
                    f"mutation:{source_report_id}:{mutation_id}:validation_missing"
                )

            matched_check = _find_mutated_check(mutation_dir, target, warnings)
            expected_status = str(expected.get("status") or "")
            expected_review_required = expected.get("review_required") is True
            detected = bool(
                validation.get("detected") is True
                and matched_check is not None
                and matched_check.get("status") == expected_status
                and (matched_check.get("review_required") is True)
                == expected_review_required
            )
            row_index = _safe_int(target.get("row_index"))
            reported_cell = _safe_int(target.get("reported_cell"))
            coord = target.get("reported_cell_coord")
            if not (
                isinstance(coord, list)
                and len(coord) == 2
                and all(isinstance(item, int) for item in coord)
            ):
                coord = [row_index, reported_cell]
            record = MutationManifestRecord(
                record_type="mutation",
                batch_name=batch_name,
                sample_id=f"mut::{source_report_id}::{mutation_id}",
                mutation_id=mutation_id,
                source_report_id=source_report_id,
                source_pdf=str(report["source_pdf"]),
                mutated_report_dir=_display_path(mutation_dir, project_root),
                mutation_type=str(label.get("mutation_type") or ""),
                strategy=str(label.get("strategy") or ""),
                table_id=str(target.get("table_id") or ""),
                page=_safe_int(target.get("page")),
                row_index=row_index,
                item_name=str(target.get("item_name") or ""),
                reported_cell=reported_cell,
                reported_cell_coord=coord,
                original_reported_growth_rate_raw=str(
                    original.get("reported_growth_rate_raw") or ""
                ),
                mutated_reported_growth_rate_raw=str(
                    mutated.get("reported_growth_rate_raw") or ""
                ),
                computed_growth_rate=_optional_str(
                    original.get("computed_growth_rate")
                ),
                expected_status=expected_status,
                expected_review_required=expected_review_required,
                expected_should_detect=expected.get("should_detect") is True,
                detected=detected,
                detected_status=(
                    str(matched_check.get("status")) if matched_check else None
                ),
                detected_review_required=(
                    matched_check.get("review_required") is True
                    if matched_check
                    else None
                ),
                is_mutated=True,
                label="growth_rate_error",
            )
            records.append(record.to_dict())
    return records


def _find_mutated_check(
    mutation_dir: Path,
    target: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any] | None:
    checks_path = mutation_dir / "checks" / "growth_rate_checks.jsonl"
    if not checks_path.is_file():
        warnings.append(f"mutation:{mutation_dir.name}:check_output_missing")
        return None
    table_id = str(target.get("table_id") or "")
    row_index = _safe_int(target.get("row_index"))
    for check in _read_jsonl(checks_path):
        if (
            str(check.get("table_id") or "") == table_id
            and _safe_int(check.get("row_index")) == row_index
        ):
            return check
    warnings.append(f"mutation:{mutation_dir.name}:target_check_missing")
    return None


def _validate_batch_counts(
    batch_data: dict[str, Any],
    reports: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    mutations: list[dict[str, Any]],
) -> list[str]:
    overview = batch_data.get("overview")
    if not isinstance(overview, dict):
        return ["batch_report:overview_missing"]
    comparisons = (
        ("parsed_reports", len(reports), "reports_count"),
        ("total_growth_rate_checks", len(checks), "original_checks_count"),
        ("mutations_generated", len(mutations), "mutations_count"),
        (
            "mutations_detected",
            sum(item.get("detected") is True for item in mutations),
            "mutations_detected_count",
        ),
    )
    warnings: list[str] = []
    for source_key, actual, label in comparisons:
        expected = overview.get(source_key)
        if isinstance(expected, int) and expected != actual:
            warnings.append(
                f"batch_count_mismatch:{label}:expected={expected}:actual={actual}"
            )
    return warnings


def _render_dataset_card(
    manifest: dict[str, Any],
    stats: dict[str, Any],
    output_dir: Path,
    project_root: Path,
) -> str:
    warnings = stats["validation_warnings"]
    warning_text = "None." if not warnings else "\n".join(
        f"- `{warning}`" for warning in warnings
    )
    return f"""# {manifest['dataset_name']}

## Version

`{manifest['version']}`

## Purpose

This benchmark indexes deterministic growth-rate consistency checks for Chinese listed-company annual reports. It is intended for reproducible pipeline evaluation, not as a complete financial audit dataset.

## Source documents

- Batch: `{manifest['batch_name']}`
- Source directory: `{manifest['source_dir']}`
- Reports: {manifest['reports_count']}
- Language: Chinese

Source PDF paths and SHA-256 digests are recorded in `reports_manifest.jsonl`. Original PDFs are never modified.

## Task definition

The task verifies whether a disclosed growth rate agrees with current-year and previous-year values in annual key financial metrics tables. Python `Decimal` performs the calculation; no LLM is used.

## Data format

- `dataset_manifest.json`: dataset identity and provenance.
- `reports_manifest.jsonl`: one row per source report.
- `checks_manifest.jsonl`: one row per original deterministic check.
- `mutations_manifest.jsonl`: one row per labeled mutation and its validation result.
- `dataset_stats.json`: aggregate counts, coverage, and validation warnings.
- `dataset_card.md`: this human-readable description.

## Current scope

- Original checks: {stats['original_checks']['total']}
- Mutation samples: {stats['mutations']['total']}
- Detected mutations: {stats['mutations']['detected']}
- Check type: growth-rate consistency only

## Limitations

This is not a complete financial audit dataset. It covers only reported growth-rate consistency in annual key financial metrics tables. Synthetic errors are applied to parsed table JSON, not to PDFs, and no synthetic PDF is generated.

## How to rebuild

```bash
python scripts/parse_pdfs.py --input-dir {manifest['source_dir']} --table-mode candidate --force
python scripts/run_growth_rate_checks.py --parsed-dir {manifest['parsed_dir']}
python scripts/generate_growth_rate_mutations.py --parsed-dir {manifest['parsed_dir']} --output-dir {manifest['mutated_dir']} --max-mutations-per-report 3 --strategy add_delta --force
python scripts/run_growth_rate_checks.py --parsed-dir {manifest['mutated_dir']}
python scripts/summarize_batch_results.py --parsed-dir {manifest['parsed_dir']} --mutated-dir {manifest['mutated_dir']} --source-dir {manifest['source_dir']} --output data/batch_reports/{manifest['batch_name']}_summary.md
python scripts/build_dataset_manifest.py --batch-name {manifest['batch_name']} --source-dir {manifest['source_dir']} --parsed-dir {manifest['parsed_dir']} --mutated-dir {manifest['mutated_dir']} --batch-report {manifest['batch_report']} --output-dir {_display_path(output_dir, project_root)} --force
```

## Validation

```bash
python -m py_compile scripts/build_dataset_manifest.py src/fri_dataset/*.py
pytest -q
```

Validation warnings:

{warning_text}
"""


def _validate_input_paths(
    source_dir: Path,
    parsed_dir: Path,
    mutated_dir: Path,
    batch_report: Path,
) -> None:
    for path, label in (
        (source_dir, "source directory"),
        (parsed_dir, "parsed directory"),
        (mutated_dir, "mutated directory"),
    ):
        if not path.is_dir():
            raise FileNotFoundError(f"Missing {label}: {path}")
    if not batch_report.is_file():
        raise FileNotFoundError(f"Missing batch report: {batch_report}")


def _prepare_output_dir(
    output_dir: Path,
    force: bool,
    allowed_root: Path,
    forbidden: set[Path],
) -> None:
    if not output_dir.is_relative_to(allowed_root):
        raise ValueError(f"Output directory must be inside project root: {output_dir}")
    if any(path == output_dir or path.is_relative_to(output_dir) for path in forbidden):
        raise ValueError(f"Unsafe output directory: {output_dir}")
    if output_dir.exists():
        if not force:
            raise FileExistsError(
                f"Output directory already exists; use --force: {output_dir}"
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _problem_flags_by_report(value: object) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if not isinstance(value, list):
        return result
    for item in value:
        if not isinstance(item, dict):
            continue
        report_id = str(item.get("report_id") or "")
        issue = str(item.get("issue") or "")
        if report_id and issue:
            result.setdefault(report_id, []).append(issue)
    return result


def _original_sample_id(
    report_id: str,
    table_id: str,
    row_index: int,
    formula_type: str,
) -> str:
    return f"orig::{report_id}::{table_id}::{row_index}::{formula_type}"


def _resolve_source_pdf(
    source_pdf: str,
    source_dir: Path,
    project_root: Path,
) -> Path:
    candidate = Path(source_pdf)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    if candidate.is_file():
        return candidate.resolve()
    return (source_dir / Path(source_pdf).name).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_has_prefix(value: object, prefix: str) -> bool:
    normalized = _normalize_path(value)
    normalized_prefix = _normalize_path(prefix).rstrip("/")
    return normalized == normalized_prefix or normalized.startswith(
        normalized_prefix + "/"
    )


def _normalize_path(value: object) -> str:
    return str(value or "").replace("\\", "/").strip("/")


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _optional_bool(primary: object, fallback: object) -> bool | None:
    if isinstance(primary, bool):
        return primary
    if isinstance(fallback, bool):
        return fallback
    return None


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _read_optional_json(path: Path) -> dict[str, Any]:
    return _read_json(path) if path.is_file() else {}


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            data = json.loads(line)
            if not isinstance(data, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            yield data


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

"""Validation rules for generated benchmark manifest records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

KNOWN_CHECK_STATUSES = {
    "ok",
    "mismatch",
    "not_applicable",
    "parse_failed",
    "mapping_failed",
    "skipped",
}


def validate_dataset_records(
    reports: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    mutations: list[dict[str, Any]],
    project_root: Path,
) -> list[str]:
    warnings: list[str] = []
    report_ids = {str(report.get("report_id")) for report in reports}

    _warn_duplicates(
        [str(report.get("report_id")) for report in reports],
        "report_id",
        warnings,
    )
    for report in reports:
        report_id = str(report.get("report_id"))
        source_pdf = str(report.get("source_pdf") or "")
        if _is_absolute_path(source_pdf):
            warnings.append(f"report:{report_id}:source_pdf_is_absolute")
        elif not (project_root / source_pdf).is_file():
            warnings.append(f"report:{report_id}:source_pdf_missing")
        digest = str(report.get("source_pdf_sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            warnings.append(f"report:{report_id}:invalid_source_pdf_sha256")

    check_ids = [str(check.get("sample_id")) for check in checks]
    _warn_duplicates(check_ids, "original_check_sample_id", warnings)
    for check in checks:
        sample_id = str(check.get("sample_id"))
        if not sample_id:
            warnings.append("original_check:missing_sample_id")
        if str(check.get("report_id")) not in report_ids:
            warnings.append(f"original_check:{sample_id}:unknown_report")
        if str(check.get("status")) not in KNOWN_CHECK_STATUSES:
            warnings.append(f"original_check:{sample_id}:unknown_status")

    mutation_ids = [str(item.get("sample_id")) for item in mutations]
    _warn_duplicates(mutation_ids, "mutation_sample_id", warnings)
    for mutation in mutations:
        sample_id = str(mutation.get("sample_id"))
        if not sample_id:
            warnings.append("mutation:missing_sample_id")
        if str(mutation.get("source_report_id")) not in report_ids:
            warnings.append(f"mutation:{sample_id}:unknown_source_report")
        if (
            mutation.get("expected_should_detect") is True
            and mutation.get("detected") is not True
        ):
            warnings.append(f"mutation:{sample_id}:expected_detection_missing")
        if mutation.get("detected") is True:
            if mutation.get("detected_status") != mutation.get("expected_status"):
                warnings.append(f"mutation:{sample_id}:detected_status_mismatch")
            if mutation.get("detected_review_required") != mutation.get(
                "expected_review_required"
            ):
                warnings.append(
                    f"mutation:{sample_id}:detected_review_required_mismatch"
                )
    return warnings


def _warn_duplicates(values: list[str], label: str, warnings: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    for value in sorted(duplicates):
        warnings.append(f"duplicate_{label}:{value}")


def _is_absolute_path(value: str) -> bool:
    return Path(value).is_absolute() or bool(re.match(r"^[A-Za-z]:[\\/]", value))

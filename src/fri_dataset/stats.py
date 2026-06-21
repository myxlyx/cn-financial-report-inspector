"""Aggregate statistics for dataset benchmark manifests."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_dataset_stats(
    reports: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    mutations: list[dict[str, Any]],
    problem_cases: list[dict[str, Any]],
    validation_warnings: list[str],
) -> dict[str, Any]:
    check_statuses = Counter(str(check.get("status")) for check in checks)
    strategies = Counter(str(item.get("strategy")) for item in mutations)
    reports_with_checks = sum(
        int(report.get("growth_rate_checks_count") or 0) > 0 for report in reports
    )
    return {
        "reports": {
            "total": len(reports),
            "text_based": sum(
                report.get("pdf_type") == "text_based" for report in reports
            ),
            "recommended": sum(
                report.get("recommended_for_dataset") is True for report in reports
            ),
        },
        "original_checks": {
            "total": len(checks),
            "ok": check_statuses["ok"],
            "mismatch": check_statuses["mismatch"],
            "not_applicable": check_statuses["not_applicable"],
            "parse_failed": check_statuses["parse_failed"],
            "mapping_failed": check_statuses["mapping_failed"],
            "skipped": check_statuses["skipped"],
            "review_required": sum(
                check.get("review_required") is True for check in checks
            ),
        },
        "mutations": {
            "total": len(mutations),
            "detected": sum(item.get("detected") is True for item in mutations),
            "undetected": sum(item.get("detected") is not True for item in mutations),
            "by_strategy": dict(sorted(strategies.items())),
        },
        "coverage": {
            "reports_with_checks": reports_with_checks,
            "reports_without_checks": len(reports) - reports_with_checks,
        },
        "problem_cases": problem_cases,
        "validation_warnings": validation_warnings,
    }

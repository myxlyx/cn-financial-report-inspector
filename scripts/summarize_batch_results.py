from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize deterministic PDF, check, and mutation batch results."
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "parsed_reports",
    )
    parser.add_argument(
        "--mutated-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "mutated_reports",
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = summarize_batch_results(
            parsed_dir=_project_path(args.parsed_dir),
            mutated_dir=_project_path(args.mutated_dir),
            source_dir=_project_path(args.source_dir),
            output_path=_project_path(args.output),
            project_root=PROJECT_ROOT,
        )
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Batch summary failed: {exc}")
        return 1

    overview = summary["overview"]
    print("Batch evaluation summary")
    print(f"- Batch: {summary['batch_name']}")
    print(f"- PDFs found: {overview['total_pdfs_found']}")
    print(f"- Parsed reports: {overview['parsed_reports']}")
    print(f"- Growth-rate checks: {overview['total_growth_rate_checks']}")
    print(f"- Mutations generated: {overview['mutations_generated']}")
    print(f"- Mutations detected: {overview['mutations_detected']}")
    print(f"- Markdown: {_display_path(_project_path(args.output), PROJECT_ROOT)}")
    print(f"- JSON: {_display_path(_project_path(args.output).with_suffix('.json'), PROJECT_ROOT)}")
    return 0


def summarize_batch_results(
    parsed_dir: Path,
    mutated_dir: Path,
    source_dir: Path,
    output_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    parsed_dir = parsed_dir.resolve()
    mutated_dir = mutated_dir.resolve()
    source_dir = source_dir.resolve()
    output_path = output_path.resolve()
    project_root = project_root.resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Batch source directory not found: {source_dir}")

    batch_name = source_dir.name
    source_display = _display_path(source_dir, project_root)
    input_files = sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )
    input_records = [
        {
            "filename": path.name,
            "path": _display_path(path, project_root),
            "suffix": path.suffix,
            "size_bytes": path.stat().st_size,
            "status": "found",
        }
        for path in input_files
    ]

    manifests_dir = parsed_dir.parent / "manifests"
    manifests = _load_filtered_json_files(
        manifests_dir.glob("*.json") if manifests_dir.exists() else [],
        source_display,
    )
    metadata = _load_filtered_json_files(
        parsed_dir.glob("*/metadata.json") if parsed_dir.exists() else [],
        source_display,
    )
    manifests_by_source = {
        _normalize_path(item.get("source_pdf")): item for item in manifests
    }
    metadata_by_report = {
        str(item.get("report_id")): item for item in metadata if item.get("report_id")
    }

    reports: list[dict[str, Any]] = []
    for input_record in input_records:
        source_pdf = _normalize_path(input_record["path"])
        manifest = manifests_by_source.get(source_pdf, {})
        report_id = str(manifest.get("report_id") or input_record["filename"])
        report_metadata = metadata_by_report.get(report_id, {})
        report_dir = parsed_dir / report_id
        quality = _read_optional_json(report_dir / "parse_quality.json")
        check_summary = _read_optional_json(
            report_dir / "checks" / "growth_rate_summary.json"
        )
        parsed = bool(report_metadata)
        pdf_type = str(manifest.get("pdf_type") or "not_processed")
        warnings = report_metadata.get("parse_warnings") or manifest.get("notes") or []
        report = {
            "report_id": report_id,
            "source_pdf": input_record["path"],
            "pdf_type": pdf_type,
            "parse_status": _parse_status(parsed, pdf_type, manifest),
            "page_count": int(manifest.get("page_count") or 0),
            "text_pages": int(manifest.get("text_pages") or 0),
            "tables_count": int(report_metadata.get("tables_count") or 0),
            "quality_level": quality.get("quality_level"),
            "recommended_for_dataset": quality.get("recommended_for_dataset"),
            "parse_warnings_count": len(warnings) if isinstance(warnings, list) else 0,
            "candidate_tables": int(check_summary.get("candidate_tables") or 0),
            "checks_count": int(check_summary.get("checks_count") or 0),
            "ok_count": int(check_summary.get("ok_count") or 0),
            "mismatch_count": int(check_summary.get("mismatch_count") or 0),
            "review_required_count": int(
                check_summary.get("review_required_count") or 0
            ),
            "mapping_failed_count": int(
                check_summary.get("mapping_failed_count") or 0
            ),
            "not_applicable_count": int(
                check_summary.get("not_applicable_count") or 0
            ),
        }
        reports.append(report)

    mutations = _collect_mutations(mutated_dir, reports)
    problem_cases = _collect_problem_cases(reports, mutations)
    parsed_reports_count = sum(report["parse_status"] == "parsed" for report in reports)
    reports_with_checks = sum(report["checks_count"] > 0 for report in reports)
    overview = {
        "total_pdfs_found": len(input_records),
        "parsed_reports": parsed_reports_count,
        "text_based_pdfs_parsed": sum(
            report["parse_status"] == "parsed" and report["pdf_type"] == "text_based"
            for report in reports
        ),
        "skipped_pdfs": len(input_records) - parsed_reports_count,
        "parse_failed_pdfs": sum(
            report["pdf_type"] == "parse_failed" for report in reports
        ),
        "reports_with_checks": reports_with_checks,
        "reports_without_checks": parsed_reports_count - reports_with_checks,
        "total_growth_rate_checks": sum(report["checks_count"] for report in reports),
        "ok_checks": sum(report["ok_count"] for report in reports),
        "mismatch_checks": sum(report["mismatch_count"] for report in reports),
        "review_required_checks": sum(
            report["review_required_count"] for report in reports
        ),
        "mutations_generated": sum(item["mutations_count"] for item in mutations),
        "mutations_detected": sum(item["detected_count"] for item in mutations),
    }
    summary = {
        "batch_name": batch_name,
        "pdf_source_dir": source_display,
        "overview": overview,
        "reports": reports,
        "mutations": mutations,
        "problem_cases": problem_cases,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path.with_suffix(".json"), summary)
    output_path.write_text(
        _render_markdown(summary),
        encoding="utf-8",
        newline="\n",
    )
    _write_json(
        output_path.parent / f"{batch_name}_inputs.json",
        {
            "batch_name": batch_name,
            "pdf_source_dir": source_display,
            "total_pdfs": len(input_records),
            "inputs": input_records,
        },
    )
    return summary


def _collect_mutations(
    mutated_dir: Path, reports: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    mutations: list[dict[str, Any]] = []
    for report in reports:
        source_report_id = report["report_id"]
        group_dir = mutated_dir / source_report_id
        group_summary = _read_optional_json(group_dir / "mutation_summary.json")
        labels = [
            _read_json(path)
            for path in sorted(group_dir.glob("growth_rate_mutation_*/mutation_label.json"))
        ]
        if not group_summary and not labels:
            continue
        mutation_count = int(group_summary.get("mutations_count") or len(labels))
        detected_count = sum(
            label.get("validation", {}).get("detected") is True for label in labels
        )
        if not labels:
            detected_count = int(
                group_summary.get("validation_detected_count") or 0
            )
        mutations.append(
            {
                "source_report_id": source_report_id,
                "mutations_count": mutation_count,
                "detected_count": detected_count,
                "undetected_count": max(mutation_count - detected_count, 0),
                "strategies_used": sorted(
                    {
                        str(label.get("strategy"))
                        for label in labels
                        if label.get("strategy")
                    }
                ),
                "mutation_ids": group_summary.get("mutation_ids")
                or [str(label.get("mutation_id")) for label in labels],
            }
        )
    return mutations


def _collect_problem_cases(
    reports: list[dict[str, Any]], mutations: list[dict[str, Any]]
) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for report in reports:
        report_id = report["report_id"]
        if report["parse_status"] != "parsed":
            _add_problem(cases, report_id, "pdf_skipped", "Need manual inspection: PDF was not parsed.")
        if report["pdf_type"] == "parse_failed":
            _add_problem(cases, report_id, "parse_failed", "Potential parsing failure: inspect the source PDF and manifest.")
        if report["recommended_for_dataset"] is False:
            _add_problem(cases, report_id, "not_recommended", "Potential parsing issue: report is not recommended for dataset use.")
        if report["parse_status"] == "parsed" and report["tables_count"] == 0:
            _add_problem(cases, report_id, "no_tables", "Potential parsing issue: tables_count is 0.")
        if report["parse_status"] == "parsed" and report["candidate_tables"] == 0:
            _add_problem(cases, report_id, "no_candidate_table", "Need manual inspection: no candidate annual key metrics table found.")
        if report["parse_status"] == "parsed" and report["checks_count"] == 0:
            _add_problem(cases, report_id, "no_growth_rate_checks", "Need manual inspection: no growth-rate checks generated.")
        if report["mismatch_count"] > 0:
            _add_problem(cases, report_id, "original_mismatch", "Potential real inconsistency or extraction issue: original mismatch detected.")

    for mutation in mutations:
        if mutation["undetected_count"] > 0:
            _add_problem(
                cases,
                mutation["source_report_id"],
                "mutation_not_detected",
                "Mutation validation failure: generated sample may be unusable.",
            )
    return cases


def _render_markdown(summary: dict[str, Any]) -> str:
    overview = summary["overview"]
    lines = [
        f"# Batch Evaluation: {summary['batch_name']}",
        "",
        "> Deterministic pipeline summary only. This report does not establish financial correctness.",
        "",
        "## Batch overview",
        "",
        f"- Batch name: {summary['batch_name']}",
        f"- PDF source dir: {summary['pdf_source_dir']}",
        f"- Total PDFs found: {overview['total_pdfs_found']}",
        f"- Text-based PDFs parsed: {overview['text_based_pdfs_parsed']}",
        f"- Skipped PDFs: {overview['skipped_pdfs']}",
        f"- Parse failed PDFs: {overview['parse_failed_pdfs']}",
        f"- Reports with growth-rate checks: {overview['reports_with_checks']}",
        f"- Reports without growth-rate checks: {overview['reports_without_checks']}",
        f"- Total growth-rate checks: {overview['total_growth_rate_checks']}",
        f"- OK checks: {overview['ok_checks']}",
        f"- Mismatch checks: {overview['mismatch_checks']}",
        f"- Review required checks: {overview['review_required_checks']}",
        f"- Mutations generated: {overview['mutations_generated']}",
        f"- Mutations validated as detected: {overview['mutations_detected']}",
        "",
        "## Per-report parse summary",
        "",
        "| report_id | source_pdf | pdf_type | page_count | text_pages | tables_count | quality_level | recommended | warnings |",
        "|---|---|---:|---:|---:|---:|---|---|---:|",
    ]
    for report in summary["reports"]:
        lines.append(
            "| "
            + " | ".join(
                _md(value)
                for value in (
                    report["report_id"],
                    report["source_pdf"],
                    report["pdf_type"],
                    report["page_count"],
                    report["text_pages"],
                    report["tables_count"],
                    report["quality_level"],
                    report["recommended_for_dataset"],
                    report["parse_warnings_count"],
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Per-report growth-rate check summary",
            "",
            "| report_id | candidate_tables | checks | ok | mismatch | review_required | mapping_failed | not_applicable |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for report in summary["reports"]:
        lines.append(
            "| "
            + " | ".join(
                _md(report[key])
                for key in (
                    "report_id",
                    "candidate_tables",
                    "checks_count",
                    "ok_count",
                    "mismatch_count",
                    "review_required_count",
                    "mapping_failed_count",
                    "not_applicable_count",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Mutation summary",
            "",
            "| source_report_id | mutations | detected | undetected | strategies |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for mutation in summary["mutations"]:
        lines.append(
            "| "
            + " | ".join(
                _md(value)
                for value in (
                    mutation["source_report_id"],
                    mutation["mutations_count"],
                    mutation["detected_count"],
                    mutation["undetected_count"],
                    ", ".join(mutation["strategies_used"]),
                )
            )
            + " |"
        )

    lines.extend(["", "## Problem cases", ""])
    if summary["problem_cases"]:
        lines.extend(
            [
                "| report_id | issue | suggestion |",
                "|---|---|---|",
            ]
        )
        for case in summary["problem_cases"]:
            lines.append(
                f"| {_md(case['report_id'])} | {_md(case['issue'])} | {_md(case['suggestion'])} |"
            )
    else:
        lines.append("No automatic problem cases were identified.")

    lines.extend(["", "## Suggested next actions", ""])
    suggestions = list(
        dict.fromkeys(case["suggestion"] for case in summary["problem_cases"])
    )
    if suggestions:
        lines.extend(f"- {suggestion}" for suggestion in suggestions)
    else:
        lines.append("- Manually review a sample of extracted tables and check evidence.")
    lines.append("")
    return "\n".join(lines)


def _load_filtered_json_files(
    paths: Iterable[Path], source_prefix: str
) -> list[dict[str, Any]]:
    results = []
    for path in paths:
        data = _read_json(path)
        if _path_has_prefix(data.get("source_pdf"), source_prefix):
            results.append(data)
    return results


def _parse_status(parsed: bool, pdf_type: str, manifest: dict[str, Any]) -> str:
    if parsed:
        return "parsed"
    if pdf_type == "parse_failed":
        return "parse_failed"
    if manifest:
        return "skipped"
    return "not_processed"


def _add_problem(
    cases: list[dict[str, str]], report_id: str, issue: str, suggestion: str
) -> None:
    cases.append(
        {"report_id": report_id, "issue": issue, "suggestion": suggestion}
    )


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


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _read_optional_json(path: Path) -> dict[str, Any]:
    return _read_json(path) if path.exists() else {}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _md(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())

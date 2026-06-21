import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "summarize_batch_results.py"
SPEC = importlib.util.spec_from_file_location("summarize_batch_results", SCRIPT_PATH)
assert SPEC is not None
summarizer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(summarizer)


def test_batch_summary_filters_source_and_writes_reports(tmp_path: Path):
    project_root = tmp_path / "project"
    data_dir = project_root / "data"
    source_dir = data_dir / "raw_reports" / "user_offer_01"
    parsed_dir = data_dir / "parsed_reports"
    manifests_dir = data_dir / "manifests"
    mutated_dir = data_dir / "mutated_reports"
    output_path = data_dir / "batch_reports" / "user_offer_01_summary.md"
    source_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)

    (source_dir / "batch_a.pdf").write_bytes(b"%PDF batch a")
    (source_dir / "batch_b.pdf").write_bytes(b"%PDF batch b")
    _write_json(
        manifests_dir / "batch-report.json",
        {
            "report_id": "batch-report",
            "source_pdf": "data/raw_reports/user_offer_01/batch_a.pdf",
            "pdf_type": "text_based",
            "page_count": 10,
            "text_pages": 10,
            "should_parse": True,
            "notes": [],
        },
    )
    _write_json(
        manifests_dir / "skipped-report.json",
        {
            "report_id": "skipped-report",
            "source_pdf": "data/raw_reports/user_offer_01/batch_b.pdf",
            "pdf_type": "scanned_or_image_based",
            "page_count": 8,
            "text_pages": 0,
            "should_parse": False,
            "notes": ["no selectable text"],
        },
    )
    _write_json(
        manifests_dir / "old-report.json",
        {
            "report_id": "old-report",
            "source_pdf": "data/raw_pdfs/old.pdf",
            "pdf_type": "text_based",
            "page_count": 5,
            "text_pages": 5,
            "should_parse": True,
            "notes": [],
        },
    )

    report_dir = parsed_dir / "batch-report"
    _write_json(
        report_dir / "metadata.json",
        {
            "report_id": "batch-report",
            "source_pdf": "data/raw_reports/user_offer_01/batch_a.pdf",
            "tables_count": 2,
            "parse_warnings": [],
        },
    )
    _write_json(
        report_dir / "parse_quality.json",
        {"quality_level": "good", "recommended_for_dataset": True},
    )
    _write_json(
        report_dir / "checks" / "growth_rate_summary.json",
        {
            "candidate_tables": 1,
            "checks_count": 2,
            "ok_count": 2,
            "mismatch_count": 0,
            "review_required_count": 0,
            "mapping_failed_count": 0,
            "not_applicable_count": 0,
        },
    )
    _write_json(
        parsed_dir / "old-report" / "metadata.json",
        {
            "report_id": "old-report",
            "source_pdf": "data/raw_pdfs/old.pdf",
            "tables_count": 99,
        },
    )

    mutation_group = mutated_dir / "batch-report"
    _write_json(
        mutation_group / "mutation_summary.json",
        {
            "source_report_id": "batch-report",
            "mutations_count": 2,
            "validation_detected_count": 1,
            "mutation_ids": ["growth_rate_mutation_001", "growth_rate_mutation_002"],
        },
    )
    _write_json(
        mutation_group
        / "growth_rate_mutation_001"
        / "mutation_label.json",
        {
            "mutation_id": "growth_rate_mutation_001",
            "strategy": "add_delta",
            "validation": {"detected": True},
        },
    )
    _write_json(
        mutation_group
        / "growth_rate_mutation_002"
        / "mutation_label.json",
        {
            "mutation_id": "growth_rate_mutation_002",
            "strategy": "swap_sign",
            "validation": {"detected": False},
        },
    )

    summary = summarizer.summarize_batch_results(
        parsed_dir=parsed_dir,
        mutated_dir=mutated_dir,
        source_dir=source_dir,
        output_path=output_path,
        project_root=project_root,
    )

    assert summary["overview"]["total_pdfs_found"] == 2
    assert summary["overview"]["parsed_reports"] == 1
    assert summary["overview"]["skipped_pdfs"] == 1
    assert summary["overview"]["reports_with_checks"] == 1
    assert summary["overview"]["total_growth_rate_checks"] == 2
    assert summary["overview"]["mutations_generated"] == 2
    assert summary["overview"]["mutations_detected"] == 1
    assert {report["report_id"] for report in summary["reports"]} == {
        "batch-report",
        "skipped-report",
    }
    assert summary["mutations"][0]["undetected_count"] == 1
    issues = {case["issue"] for case in summary["problem_cases"]}
    assert "pdf_skipped" in issues
    assert "mutation_not_detected" in issues
    assert output_path.exists()
    assert output_path.with_suffix(".json").exists()
    assert (output_path.parent / "user_offer_01_inputs.json").exists()
    markdown = output_path.read_text(encoding="utf-8")
    assert "batch-report" in markdown
    assert "old-report" not in markdown


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

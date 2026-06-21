import json
from pathlib import Path

import pytest

from fri_dataset.manifest_builder import build_dataset_manifest


OUTPUT_FILES = {
    "dataset_manifest.json",
    "reports_manifest.jsonl",
    "checks_manifest.jsonl",
    "mutations_manifest.jsonl",
    "dataset_stats.json",
    "dataset_card.md",
}


def test_build_dataset_manifest_from_small_fixture(tmp_path: Path):
    fixture = _create_fixture(tmp_path)

    result = _build(fixture, tmp_path / "data" / "datasets" / "batch")

    output_dir = result["output_dir"]
    assert OUTPUT_FILES.issubset(path.name for path in output_dir.iterdir())
    assert result["stats"]["reports"]["total"] == 1
    assert result["stats"]["original_checks"]["total"] == 1
    assert result["stats"]["mutations"]["detected"] == 1
    assert result["stats"]["validation_warnings"] == []
    assert len(result["reports"][0]["source_pdf_sha256"]) == 64


def test_source_filter_excludes_unrelated_parsed_report(tmp_path: Path):
    fixture = _create_fixture(tmp_path, include_unrelated=True)

    result = _build(fixture, tmp_path / "dataset")

    assert [record["report_id"] for record in result["reports"]] == ["sample-report"]
    assert all(
        check["report_id"] == "sample-report" for check in result["checks"]
    )


def test_sample_ids_are_stable_and_unique(tmp_path: Path):
    fixture = _create_fixture(tmp_path)

    first = _build(fixture, tmp_path / "dataset-a")
    second = _build(fixture, tmp_path / "dataset-b")

    first_check_ids = [item["sample_id"] for item in first["checks"]]
    second_check_ids = [item["sample_id"] for item in second["checks"]]
    first_mutation_ids = [item["sample_id"] for item in first["mutations"]]
    second_mutation_ids = [item["sample_id"] for item in second["mutations"]]
    assert first_check_ids == second_check_ids
    assert first_mutation_ids == second_mutation_ids
    assert len(first_check_ids) == len(set(first_check_ids))
    assert len(first_mutation_ids) == len(set(first_mutation_ids))


def test_undetected_mutation_emits_validation_warning(tmp_path: Path):
    fixture = _create_fixture(tmp_path, detected=False)

    result = _build(fixture, tmp_path / "dataset")

    warnings = result["stats"]["validation_warnings"]
    assert result["stats"]["mutations"]["undetected"] == 1
    assert any("expected_detection_missing" in warning for warning in warnings)


def test_manifest_jsonl_files_contain_valid_objects(tmp_path: Path):
    fixture = _create_fixture(tmp_path)
    result = _build(fixture, tmp_path / "dataset")

    for filename in (
        "reports_manifest.jsonl",
        "checks_manifest.jsonl",
        "mutations_manifest.jsonl",
    ):
        rows = [
            json.loads(line)
            for line in (result["output_dir"] / filename)
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        assert rows
        assert all(isinstance(row, dict) for row in rows)


def test_existing_output_requires_force(tmp_path: Path):
    fixture = _create_fixture(tmp_path)
    output_dir = tmp_path / "dataset"
    _build(fixture, output_dir)

    with pytest.raises(FileExistsError, match="use --force"):
        _build(fixture, output_dir)


def _build(fixture: dict[str, Path], output_dir: Path) -> dict:
    return build_dataset_manifest(
        batch_name="test_batch",
        source_dir=fixture["source_dir"],
        parsed_dir=fixture["parsed_dir"],
        mutated_dir=fixture["mutated_dir"],
        batch_report=fixture["batch_report"],
        output_dir=output_dir,
        project_root=fixture["project_root"],
    )


def _create_fixture(
    root: Path,
    include_unrelated: bool = False,
    detected: bool = True,
) -> dict[str, Path]:
    source_dir = root / "data" / "raw_reports" / "test_batch"
    parsed_dir = root / "data" / "parsed_reports"
    mutated_dir = root / "data" / "mutated_reports"
    batch_report = root / "data" / "batch_reports" / "test_batch_summary.json"
    source_dir.mkdir(parents=True)
    source_pdf = source_dir / "sample.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\nfixture\n%%EOF\n")

    report_id = "sample-report"
    source_pdf_relative = "data/raw_reports/test_batch/sample.pdf"
    report_dir = parsed_dir / report_id
    checks_dir = report_dir / "checks"
    checks_dir.mkdir(parents=True)
    _write_json(
        report_dir / "metadata.json",
        {
            "report_id": report_id,
            "source_pdf": source_pdf_relative,
            "pdf_type": "text_based",
            "page_count": 2,
            "tables_count": 1,
            "parse_warnings": [],
        },
    )
    _write_json(
        report_dir / "parse_quality.json",
        {
            "quality_level": "good",
            "recommended_for_dataset": True,
        },
    )
    original_check = _check(report_id=report_id, status="ok", reported="20.00")
    _write_jsonl(checks_dir / "growth_rate_checks.jsonl", [original_check])
    _write_json(
        checks_dir / "growth_rate_summary.json",
        {
            "checks_count": 1,
            "ok_count": 1,
            "mismatch_count": 0,
            "not_applicable_count": 0,
            "mapping_failed_count": 0,
            "review_required_count": 0,
        },
    )
    (checks_dir / "mapping_diagnostics.jsonl").write_text(
        json.dumps({"table_id": "table_001"}) + "\n",
        encoding="utf-8",
    )

    mutation_dir = mutated_dir / report_id / "growth_rate_mutation_001"
    mutation_checks_dir = mutation_dir / "checks"
    mutation_checks_dir.mkdir(parents=True)
    mutation_status = "mismatch" if detected else "ok"
    mutated_check = _check(
        report_id="growth_rate_mutation_001",
        status=mutation_status,
        reported="25.00" if detected else "20.00",
    )
    mutated_check["review_required"] = detected
    mutated_check["is_consistent"] = not detected
    _write_jsonl(
        mutation_checks_dir / "growth_rate_checks.jsonl", [mutated_check]
    )
    _write_json(
        mutation_dir / "mutation_label.json",
        {
            "mutation_id": "growth_rate_mutation_001",
            "source_report_id": report_id,
            "mutation_type": "growth_rate_reported_value_error",
            "strategy": "add_delta",
            "target": {
                "table_id": "table_001",
                "page": 1,
                "row_index": 1,
                "item_name": "营业收入",
                "reported_cell": 3,
                "reported_cell_coord": [1, 3],
            },
            "original": {
                "reported_growth_rate_raw": "20.00",
                "computed_growth_rate": "20.00",
            },
            "mutated": {"reported_growth_rate_raw": "25.00"},
            "expected_detection": {
                "status": "mismatch",
                "review_required": True,
                "should_detect": True,
            },
            "validation": {
                "detected": detected,
                "matched_check_result": {
                    "table_id": "table_001",
                    "row_index": 1,
                    "status": mutation_status,
                    "review_required": detected,
                },
            },
        },
    )

    reports = [
        {
            "report_id": report_id,
            "source_pdf": source_pdf_relative,
            "pdf_type": "text_based",
            "page_count": 2,
            "text_pages": 2,
            "tables_count": 1,
            "quality_level": "good",
            "recommended_for_dataset": True,
            "checks_count": 1,
            "ok_count": 1,
            "mismatch_count": 0,
            "not_applicable_count": 0,
            "mapping_failed_count": 0,
            "review_required_count": 0,
            "parse_warnings_count": 0,
        }
    ]
    if include_unrelated:
        unrelated_dir = parsed_dir / "unrelated-report"
        unrelated_dir.mkdir(parents=True)
        _write_json(
            unrelated_dir / "metadata.json",
            {
                "report_id": "unrelated-report",
                "source_pdf": "data/raw_reports/other/unrelated.pdf",
            },
        )
        reports.append(
            {
                "report_id": "unrelated-report",
                "source_pdf": "data/raw_reports/other/unrelated.pdf",
            }
        )

    _write_json(
        batch_report,
        {
            "batch_name": "test_batch",
            "pdf_source_dir": "data/raw_reports/test_batch",
            "overview": {
                "parsed_reports": 1,
                "total_growth_rate_checks": 1,
                "mutations_generated": 1,
                "mutations_detected": int(detected),
            },
            "reports": reports,
            "problem_cases": [],
        },
    )
    return {
        "project_root": root,
        "source_dir": source_dir,
        "parsed_dir": parsed_dir,
        "mutated_dir": mutated_dir,
        "batch_report": batch_report,
    }


def _check(report_id: str, status: str, reported: str) -> dict:
    return {
        "check_type": "growth_rate_consistency",
        "report_id": report_id,
        "table_id": "table_001",
        "page": 1,
        "row_index": 1,
        "item_name": "营业收入",
        "formula_type": "growth_rate",
        "current_cell": 1,
        "previous_cell": 2,
        "reported_cell": 3,
        "current_value_raw": "120",
        "previous_value_raw": "100",
        "reported_growth_rate_raw": reported,
        "current_value": "120",
        "previous_value": "100",
        "reported_growth_rate": reported,
        "computed_growth_rate": "20.00",
        "difference": "0.00" if status == "ok" else "5.00",
        "tolerance": "0.05",
        "is_consistent": status == "ok",
        "review_required": status == "mismatch",
        "status": status,
        "mapping_source": "rule_based",
        "confidence": 0.95,
        "notes": [],
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

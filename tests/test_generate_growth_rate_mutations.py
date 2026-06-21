import json
from pathlib import Path
import subprocess
import sys

from fri_checks.runner import run_all_reports


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "generate_growth_rate_mutations.py"


def test_generate_growth_rate_mutation_end_to_end(tmp_path: Path):
    parsed_dir = tmp_path / "parsed_reports"
    output_dir = tmp_path / "mutated_reports"
    report_dir = _create_source_report(parsed_dir)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--parsed-dir",
            str(parsed_dir),
            "--output-dir",
            str(output_dir),
            "--max-mutations-per-report",
            "1",
            "--strategy",
            "add_delta",
            "--force",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    mutation_dir = output_dir / "sample-report" / "growth_rate_mutation_001"
    mutated_table = _read_json(mutation_dir / "tables" / "table_001.json")
    label = _read_json(mutation_dir / "mutation_label.json")
    metadata = _read_json(mutation_dir / "metadata.json")
    summary = _read_json(mutation_dir / "mutation_summary.json")
    mutated_checks = _read_jsonl(
        mutation_dir / "checks" / "growth_rate_checks.jsonl"
    )
    assert report_dir.exists()
    assert mutation_dir.exists()
    assert mutated_table["data"][1][3] == "25.00"
    assert mutated_table["data"][1][:3] == ["营业收入", "120", "100"]
    assert label["target"]["reported_cell_coord"] == [1, 3]
    assert label["original"]["reported_growth_rate_raw"] == "20.00"
    assert label["mutated"]["reported_growth_rate_raw"] == "25.00"
    assert label["validation"]["detected"] is True
    assert metadata["source_report_id"] == "sample-report"
    assert metadata["is_mutated"] is True
    assert metadata["source_pdf_unmodified"] is True
    assert summary["mutations_count"] == 1
    assert not (mutation_dir / "report.md").exists()
    assert not (mutation_dir / "pages.jsonl").exists()
    assert any(result["status"] == "mismatch" for result in mutated_checks)

    summaries = run_all_reports(output_dir)
    assert len(summaries) == 1
    assert summaries[0].mismatch_count == 1


def test_missing_source_checks_reports_clear_error(tmp_path: Path):
    parsed_dir = tmp_path / "parsed_reports"
    report_dir = parsed_dir / "sample-report"
    report_dir.mkdir(parents=True)
    (report_dir / "tables_index.jsonl").write_text("", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--parsed-dir",
            str(parsed_dir),
            "--output-dir",
            str(tmp_path / "mutated_reports"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "Run scripts/run_growth_rate_checks.py first" in completed.stderr


def _create_source_report(parsed_dir: Path) -> Path:
    report_dir = parsed_dir / "sample-report"
    tables_dir = report_dir / "tables"
    checks_dir = report_dir / "checks"
    tables_dir.mkdir(parents=True)
    checks_dir.mkdir()
    table = {
        "table_id": "table_001",
        "page": 1,
        "rows": 2,
        "columns": 5,
        "json_path": "tables/table_001.json",
        "csv_path": "tables/table_001.csv",
        "title_candidate": "单位：元",
        "section_candidate": "七、近三年主要会计数据和财务指标",
        "data": [
            ["主要会计数据", "2025年", "2024年", "本期比上年同期增减(%)", "2023年"],
            ["营业收入", "120", "100", "20.00", "90"],
        ],
    }
    check = {
        "check_type": "growth_rate_consistency",
        "report_id": "sample-report",
        "table_id": "table_001",
        "page": 1,
        "row_index": 1,
        "item_name": "营业收入",
        "reported_cell": 3,
        "reported_growth_rate_raw": "20.00",
        "computed_growth_rate": "20.00",
        "status": "ok",
        "is_consistent": True,
        "review_required": False,
    }
    _write_json(report_dir / "metadata.json", {"report_id": "sample-report"})
    _write_json(report_dir / "parse_quality.json", {"report_id": "sample-report"})
    _write_json(tables_dir / "table_001.json", table)
    (report_dir / "tables_index.jsonl").write_text(
        json.dumps(table, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (checks_dir / "growth_rate_checks.jsonl").write_text(
        json.dumps(check, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report_dir


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_quarterly_sum_checks.py"


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")


def _make_report_fixture(tmp_path: Path) -> tuple[Path, Path]:
    parsed_dir = tmp_path / "parsed_reports"
    report_dir = parsed_dir / "sample-report"
    tables_dir = report_dir / "tables"
    checks_dir = report_dir / "checks"
    tables_dir.mkdir(parents=True)
    checks_dir.mkdir()

    table = {
        "table_id": "table_002",
        "page": 12,
        "json_path": "tables/table_002.json",
        "section_candidate": "分季度主要财务指标",
        "data": [
            ["", "第一季度", "第二季度", "第三季度", "第四季度"],
            ["营业收入", "10", "20", "30", "40"],
        ],
    }
    _write_json(report_dir / "metadata.json", {"report_id": "sample-report"})
    _write_json(report_dir / "parse_quality.json", {})
    _write_json(tables_dir / "table_002.json", table)
    (report_dir / "tables_index.jsonl").write_text(
        json.dumps(table, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (checks_dir / "growth_rate_checks.jsonl").write_text(
        json.dumps(
            {
                "check_type": "growth_rate_consistency",
                "report_id": "sample-report",
                "table_id": "table_annual",
                "page": 10,
                "row_index": 1,
                "item_name": "营业收入",
                "current_value_raw": "100",
                "status": "ok",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return parsed_dir, report_dir


def test_cli_writes_quarterly_sum_outputs(tmp_path: Path):
    parsed_dir, report_dir = _make_report_fixture(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--parsed-dir",
            str(parsed_dir),
            "--report-id",
            "sample-report",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    checks_path = report_dir / "checks" / "quarterly_sum_checks.jsonl"
    summary_path = report_dir / "checks" / "quarterly_sum_summary.json"
    diagnostics_path = report_dir / "checks" / "quarterly_mapping_diagnostics.jsonl"
    assert checks_path.exists()
    assert summary_path.exists()
    assert diagnostics_path.exists()
    result = json.loads(checks_path.read_text(encoding="utf-8").strip())
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(diagnostics_path.read_text(encoding="utf-8").strip())
    assert result["check_type"] == "quarterly_sum_consistency"
    assert result["status"] == "ok"
    assert result["computed_quarterly_sum"] == "100.00"
    assert result["annual_reference"]["table_id"] == "table_annual"
    assert summary["checks_count"] == 1
    assert summary["ok_count"] == 1
    assert diagnostic["table_id"] == "table_002"
    assert diagnostic["is_candidate"] is True


def test_cli_fails_clearly_when_growth_rate_checks_are_missing(tmp_path: Path):
    parsed_dir, report_dir = _make_report_fixture(tmp_path)
    (report_dir / "checks" / "growth_rate_checks.jsonl").unlink()

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--parsed-dir",
            str(parsed_dir),
            "--report-id",
            "sample-report",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "Please run scripts/run_growth_rate_checks.py first" in completed.stderr

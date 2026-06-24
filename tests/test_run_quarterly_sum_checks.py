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
            [
                "营业收入",
                "264,741,302.88",
                "267,393,464.49",
                "256,376,315.47",
                "374,027,072.80",
            ],
            [
                "归属于上市公司股东的净利润",
                "23,973,421.36",
                "11,607,446.52",
                "18,205,792.50",
                "3,155,348.99",
            ],
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
                "current_value_raw": "1,162,538,155.64",
                "status": "ok",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    with (checks_dir / "growth_rate_checks.jsonl").open(
        "a", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(
            json.dumps(
                {
                    "check_type": "growth_rate_consistency",
                    "report_id": "sample-report",
                    "table_id": "table_annual",
                    "page": 10,
                    "row_index": 2,
                    "item_name": "归属于上市公司股东的净利润",
                    "current_value_raw": "56,942,009.37",
                    "status": "ok",
                },
                ensure_ascii=False,
            )
            + "\n"
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
    results = [
        json.loads(line)
        for line in checks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    diagnostic = json.loads(diagnostics_path.read_text(encoding="utf-8").strip())
    assert len(results) == 2
    assert {result["item_name"] for result in results} == {
        "营业收入",
        "归属于上市公司股东的净利润",
    }
    assert all(result["check_type"] == "quarterly_sum_consistency" for result in results)
    assert all(result["status"] == "ok" for result in results)
    assert results[0]["annual_reference"]["table_id"] == "table_annual"
    assert summary["checks_count"] == 2
    assert summary["ok_count"] == 2
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


def test_runner_deduplicates_lower_confidence_quarterly_candidate(tmp_path: Path):
    parsed_dir, report_dir = _make_report_fixture(tmp_path)
    duplicate_table = {
        "table_id": "table_003",
        "page": 18,
        "json_path": "tables/table_003.json",
        "section_candidate": "经营数据对比",
        "data": [
            ["", "第一季度", "第二季度", "第三季度", "第四季度"],
            ["营业收入", "10", "20", "30", "40"],
        ],
    }
    _write_json(report_dir / "tables" / "table_003.json", duplicate_table)
    with (report_dir / "tables_index.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(duplicate_table, ensure_ascii=False) + "\n")

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
    checks = [
        json.loads(line)
        for line in (report_dir / "checks" / "quarterly_sum_checks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    diagnostics = [
        json.loads(line)
        for line in (report_dir / "checks" / "quarterly_mapping_diagnostics.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    summary = json.loads(
        (report_dir / "checks" / "quarterly_sum_summary.json").read_text(
            encoding="utf-8"
        )
    )

    assert [check["item_name"] for check in checks].count("营业收入") == 1
    assert any(
        diagnostic["status"] == "skipped"
        and "duplicate_quarterly_item:营业收入" in diagnostic["notes"]
        for diagnostic in diagnostics
    )
    assert summary["duplicate_skipped_count"] == 1

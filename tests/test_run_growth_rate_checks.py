import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_growth_rate_checks.py"


def test_cli_writes_growth_rate_check_outputs(tmp_path: Path):
    parsed_dir = tmp_path / "parsed_reports"
    report_dir = parsed_dir / "sample-report"
    tables_dir = report_dir / "tables"
    tables_dir.mkdir(parents=True)

    table = {
        "table_id": "table_001",
        "page": 10,
        "json_path": "tables/table_001.json",
        "title_candidate": "单位：元",
        "section_candidate": "七、近三年主要会计数据和财务指标",
        "data": [
            ["主要会计数据", "2025年", "2024年", "本期比上年同期增减(%)", "2023年"],
            ["营业收入", "120", "100", "20.00", "90"],
        ],
    }
    (report_dir / "metadata.json").write_text(
        json.dumps({"report_id": "sample-report"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (report_dir / "parse_quality.json").write_text("{}\n", encoding="utf-8")
    (tables_dir / "table_001.json").write_text(
        json.dumps(table, ensure_ascii=False),
        encoding="utf-8",
    )
    (report_dir / "tables_index.jsonl").write_text(
        json.dumps(table, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

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
    checks_path = report_dir / "checks" / "growth_rate_checks.jsonl"
    summary_path = report_dir / "checks" / "growth_rate_summary.json"
    assert checks_path.exists()
    assert summary_path.exists()
    result = json.loads(checks_path.read_text(encoding="utf-8").strip())
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert result["computed_growth_rate"] == "20.00"
    assert summary["checks_count"] == 1
    assert summary["candidate_tables"] == 1

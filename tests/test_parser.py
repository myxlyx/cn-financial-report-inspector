import json
from pathlib import Path

import fitz

from fri_pdf.parser import process_pdf


def _make_text_pdf(path: Path, text: str = "中文年度报告\n资产负债表\n营业收入 100") -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def test_process_pdf_outputs_report_files_for_chinese_filename(tmp_path: Path):
    pdf_path = tmp_path / "测试公司：2025年年度报告.PDF"
    parsed_root = tmp_path / "parsed_reports"
    manifests_root = tmp_path / "manifests"
    _make_text_pdf(pdf_path, text="中文年度报告\n" * 20)

    result = process_pdf(pdf_path, parsed_root, manifests_root, force=True)

    assert result.parsed is True
    report_dir = parsed_root / result.report_id
    assert (manifests_root / f"{result.report_id}.json").exists()
    assert (report_dir / "report.md").exists()
    assert (report_dir / "pages.jsonl").exists()
    assert (report_dir / "metadata.json").exists()
    assert (report_dir / "parse_quality.json").exists()
    assert (report_dir / "tables_index.jsonl").exists()

    metadata = json.loads((report_dir / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (manifests_root / f"{result.report_id}.json").read_text(encoding="utf-8")
    )
    quality = json.loads((report_dir / "parse_quality.json").read_text(encoding="utf-8"))
    assert not Path(metadata["source_pdf"]).is_absolute()
    assert not Path(manifest["source_pdf"]).is_absolute()
    assert metadata["parse_quality_path"] == "parse_quality.json"
    assert metadata["tables_index_path"] == "tables_index.jsonl"
    assert quality["page_count"] == 1
    assert "recommended_for_dataset" in quality
    assert "quality_level" in quality
    assert "pages_with_tables" in quality
    assert "chinese_char_ratio" in quality
    assert "garbled_char_ratio" in quality


def test_force_recreates_report_directory(tmp_path: Path):
    pdf_path = tmp_path / "force.pdf"
    parsed_root = tmp_path / "parsed_reports"
    manifests_root = tmp_path / "manifests"
    _make_text_pdf(pdf_path, text="中文年度报告\n" * 20)

    first = process_pdf(pdf_path, parsed_root, manifests_root, force=True)
    stale_file = parsed_root / first.report_id / "stale.txt"
    stale_file.write_text("old", encoding="utf-8")

    second = process_pdf(pdf_path, parsed_root, manifests_root, force=True)

    assert second.report_id == first.report_id
    assert not stale_file.exists()


def test_table_mode_none_writes_text_outputs_and_empty_table_index(tmp_path: Path):
    pdf_path = tmp_path / "no_tables.pdf"
    parsed_root = tmp_path / "parsed_reports"
    manifests_root = tmp_path / "manifests"
    _make_text_pdf(pdf_path, text="近三年主要会计数据和财务指标\n" * 20)

    result = process_pdf(
        pdf_path,
        parsed_root,
        manifests_root,
        force=True,
        table_mode="none",
    )

    report_dir = parsed_root / result.report_id
    metadata = json.loads((report_dir / "metadata.json").read_text(encoding="utf-8"))
    quality = json.loads((report_dir / "parse_quality.json").read_text(encoding="utf-8"))
    assert (report_dir / "report.md").exists()
    assert (report_dir / "pages.jsonl").exists()
    assert (report_dir / "tables_index.jsonl").read_text(encoding="utf-8") == ""
    assert metadata["tables_count"] == 0
    assert any("table_mode=none" in warning for warning in metadata["parse_warnings"])
    assert any("table_mode=none" in warning for warning in quality["warnings"])

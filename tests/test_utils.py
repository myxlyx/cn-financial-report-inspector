import hashlib
from pathlib import Path

from fri_pdf.utils import find_pdf_files, slugify_filename


def test_find_pdf_files_is_case_insensitive(tmp_path: Path):
    upper = tmp_path / "REPORT.PDF"
    text = tmp_path / "note.txt"
    upper.write_bytes(b"%PDF")
    text.write_text("not a pdf", encoding="utf-8")

    assert find_pdf_files(tmp_path) == [upper]


def test_find_pdf_files_empty_directory(tmp_path: Path):
    assert find_pdf_files(tmp_path) == []


def test_slugify_filename_handles_chinese_names():
    report_id = slugify_filename(Path("汽轮科技：2025年年度报告.pdf"))

    assert report_id.startswith("汽轮科技_2025年年度报告_")
    assert ":" not in report_id
    assert len(report_id.rsplit("_", 1)[-1]) == 8


def test_slugify_filename_handles_surrogate_characters():
    filename = "异常\udcff报告.pdf"
    report_id = slugify_filename(Path(filename))
    expected_digest = hashlib.sha1(
        filename.encode("utf-8", errors="replace")
    ).hexdigest()[:8]

    assert report_id.startswith("异常")
    assert report_id.endswith(f"_{expected_digest}")

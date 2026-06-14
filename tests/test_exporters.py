import json
from pathlib import Path

from fri_pdf.markdown_exporter import export_markdown, export_pages_jsonl
from fri_pdf.schema import PageText


def test_markdown_export_preserves_page_boundaries(tmp_path: Path):
    output = tmp_path / "report.md"
    pages = [
        PageText(page=1, text="第一页", char_count=3),
        PageText(page=2, text="第二页", char_count=3),
    ]

    export_markdown(pages, output)

    text = output.read_text(encoding="utf-8")
    assert "<!-- page: 1 -->" in text
    assert "# Page 2" in text
    assert "第二页" in text


def test_pages_jsonl_export(tmp_path: Path):
    output = tmp_path / "pages.jsonl"
    pages = [PageText(page=1, text="资产负债表", char_count=5)]

    export_pages_jsonl(pages, output)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"page": 1, "text": "资产负债表", "char_count": 5}]

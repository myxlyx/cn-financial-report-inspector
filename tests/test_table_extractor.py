import json
from pathlib import Path

from fri_pdf.schema import PageText
from fri_pdf.table_extractor import extract_tables


class FakeTable:
    bbox = [1, 2, 3, 4]

    def extract(self):
        return [
            ["项目", "金额", ""],
            ["营业收入", "1,234.50", ""],
            ["净利润", "-56", "备注"],
        ]


class FakeTableResult:
    tables = [FakeTable()]


class FakePage:
    def find_tables(self):
        return FakeTableResult()


class FakeDoc:
    page_count = 1

    def load_page(self, page_index):
        assert page_index == 0
        return FakePage()


def test_extract_tables_writes_csv_json_and_index(tmp_path: Path):
    pages = [PageText(page=1, text="一、财务报表\n单位：元\n项目 金额", char_count=15)]

    tables, warnings = extract_tables(FakeDoc(), tmp_path, pages=pages)

    assert warnings == []
    assert len(tables) == 1
    table_json = json.loads((tmp_path / "tables" / "table_001.json").read_text(encoding="utf-8"))
    index_rows = [
        json.loads(line)
        for line in (tmp_path / "tables_index.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert table_json["data"][1][1] == "1,234.50"
    assert table_json["blank_cell_ratio"] > 0
    assert table_json["numeric_cell_ratio"] > 0
    assert table_json["title_candidate"] == "单位：元"
    assert table_json["section_candidate"] == "一、财务报表"
    assert index_rows[0]["json_path"] == "tables/table_001.json"
    assert (tmp_path / "tables" / "table_001.csv").exists()

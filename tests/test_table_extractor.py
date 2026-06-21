import json
from pathlib import Path

from fri_pdf.schema import PageText
from fri_pdf.table_extractor import candidate_page_numbers, extract_tables


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


class TrackingFakeDoc:
    page_count = 2

    def __init__(self):
        self.loaded_page_indexes = []

    def load_page(self, page_index):
        self.loaded_page_indexes.append(page_index)
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


def test_candidate_mode_extracts_only_keyword_pages(tmp_path: Path):
    pages = [
        PageText(page=1, text="公司基本情况", char_count=6),
        PageText(
            page=2,
            text="七、近三年主要会计数据和财务指标\n本期比上年同期增减",
            char_count=30,
        ),
    ]
    doc = TrackingFakeDoc()

    tables, warnings = extract_tables(doc, tmp_path, pages=pages, mode="candidate")

    assert candidate_page_numbers(pages) == [2]
    assert doc.loaded_page_indexes == [1]
    assert len(tables) == 1
    assert tables[0].page == 2
    assert any("selected 1 of 2 pages" in warning for warning in warnings)

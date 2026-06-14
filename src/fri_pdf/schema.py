"""Shared dataclasses for the PDF parsing MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

PdfType = Literal["text_based", "mixed", "scanned_or_image_based", "parse_failed"]


@dataclass
class PdfManifest:
    report_id: str
    source_pdf: str
    pdf_type: PdfType
    page_count: int
    text_pages: int
    avg_text_chars_per_page: float
    should_parse: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["avg_text_chars_per_page"] = round(float(self.avg_text_chars_per_page), 2)
        return data


@dataclass
class PageText:
    page: int
    text: str
    char_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TableMetadata:
    table_id: str
    page: int
    rows: int
    columns: int
    bbox: list[float] | None
    source_method: str
    csv_path: str
    json_path: str
    title_candidate: str | None
    section_candidate: str | None
    blank_cell_ratio: float
    numeric_cell_ratio: float
    data: list[list[str]]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReportMetadata:
    report_id: str
    source_pdf: str
    pdf_type: PdfType
    page_count: int
    markdown_path: str
    pages_jsonl_path: str
    tables_count: int
    tables_dir: str
    tables_index_path: str
    parse_quality_path: str
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParseResult:
    report_id: str
    source_pdf: Path
    manifest: PdfManifest
    parsed: bool
    metadata_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

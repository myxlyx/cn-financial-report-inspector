"""Top-level PDF parsing workflow."""

from __future__ import annotations

from pathlib import Path

import fitz

from fri_pdf.markdown_exporter import export_markdown, export_pages_jsonl
from fri_pdf.pdf_type import classify_pdf
from fri_pdf.schema import PageText, ParseResult, ReportMetadata
from fri_pdf.table_extractor import extract_tables
from fri_pdf.utils import ensure_dir, relative_to_report, slugify_filename, write_json


def process_pdf(pdf_path: Path, parsed_root: Path, manifests_root: Path) -> ParseResult:
    """Detect, write manifest, and parse a PDF if it is text-based."""
    report_id = slugify_filename(pdf_path)
    manifest = classify_pdf(pdf_path, report_id=report_id)
    manifest_path = manifests_root / f"{report_id}.json"
    write_json(manifest_path, manifest.to_dict())

    if not manifest.should_parse:
        return ParseResult(
            report_id=report_id,
            source_pdf=pdf_path,
            manifest=manifest,
            parsed=False,
            warnings=manifest.notes,
        )

    metadata_path, warnings = parse_pdf(pdf_path, report_id, parsed_root, manifest.pdf_type)
    return ParseResult(
        report_id=report_id,
        source_pdf=pdf_path,
        manifest=manifest,
        parsed=True,
        metadata_path=metadata_path,
        warnings=warnings,
    )


def parse_pdf(
    pdf_path: Path,
    report_id: str,
    parsed_root: Path,
    pdf_type: str = "text_based",
) -> tuple[Path, list[str]]:
    """Extract text, Markdown, JSONL pages, best-effort tables, and metadata."""
    report_dir = ensure_dir(parsed_root / report_id)
    warnings: list[str] = []

    doc = fitz.open(pdf_path)
    try:
        pages: list[PageText] = []
        for page_index in range(doc.page_count):
            page_number = page_index + 1
            try:
                text = doc.load_page(page_index).get_text("text") or ""
            except Exception as exc:
                text = ""
                warnings.append(f"Page {page_number}: text extraction failed: {exc}")

            text = _normalize_page_text(text)
            pages.append(PageText(page=page_number, text=text, char_count=len(text)))

        markdown_path = report_dir / "report.md"
        pages_jsonl_path = report_dir / "pages.jsonl"
        export_markdown(pages, markdown_path)
        export_pages_jsonl(pages, pages_jsonl_path)

        table_metadata, table_warnings = extract_tables(doc, report_dir)
        warnings.extend(table_warnings)

        metadata = ReportMetadata(
            report_id=report_id,
            source_pdf=str(pdf_path),
            pdf_type=pdf_type,  # type: ignore[arg-type]
            page_count=doc.page_count,
            markdown_path=relative_to_report(markdown_path, report_dir),
            pages_jsonl_path=relative_to_report(pages_jsonl_path, report_dir),
            tables_count=len(table_metadata),
            tables_dir="tables",
            parse_warnings=warnings,
        )
        metadata_path = report_dir / "metadata.json"
        write_json(metadata_path, metadata.to_dict())
        return metadata_path, warnings
    finally:
        doc.close()


def _normalize_page_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    compact_lines: list[str] = []
    blank_seen = False
    for line in lines:
        if line.strip():
            compact_lines.append(line)
            blank_seen = False
        elif not blank_seen:
            compact_lines.append("")
            blank_seen = True
    return "\n".join(compact_lines).strip()

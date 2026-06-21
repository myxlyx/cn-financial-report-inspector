"""Top-level PDF parsing workflow."""

from __future__ import annotations

from pathlib import Path

import fitz

from fri_pdf.markdown_exporter import export_markdown, export_pages_jsonl
from fri_pdf.pdf_type import classify_pdf
from fri_pdf.schema import PageText, ParseResult, ReportMetadata
from fri_pdf.table_extractor import TableMode, extract_tables
from fri_pdf.utils import (
    ensure_dir,
    project_relative_path,
    relative_to_report,
    reset_dir,
    slugify_filename,
    write_json,
)


def process_pdf(
    pdf_path: Path,
    parsed_root: Path,
    manifests_root: Path,
    force: bool = False,
    table_mode: TableMode = "candidate",
) -> ParseResult:
    """Detect, write manifest, and parse a PDF if it is text-based."""
    report_id = slugify_filename(pdf_path)
    project_root = manifests_root.resolve().parents[1]
    source_pdf = project_relative_path(pdf_path, project_root)
    manifest = classify_pdf(pdf_path, report_id=report_id, source_pdf=source_pdf)
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

    metadata_path, warnings = parse_pdf(
        pdf_path,
        report_id,
        parsed_root,
        manifest.pdf_type,
        project_root=project_root,
        force=force,
        table_mode=table_mode,
    )
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
    project_root: Path | None = None,
    force: bool = False,
    table_mode: TableMode = "candidate",
) -> tuple[Path, list[str]]:
    """Extract text, Markdown, JSONL pages, best-effort tables, and metadata."""
    report_dir = reset_dir(parsed_root / report_id) if force else ensure_dir(parsed_root / report_id)
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

        table_metadata, table_warnings = extract_tables(
            doc,
            report_dir,
            pages=pages,
            mode=table_mode,
        )
        warnings.extend(table_warnings)

        quality_path = report_dir / "parse_quality.json"
        quality = _build_parse_quality(
            report_id=report_id,
            pages=pages,
            tables_count=len(table_metadata),
            table_pages=sorted({item.page for item in table_metadata}),
            warnings=warnings,
        )
        write_json(quality_path, quality)

        metadata = ReportMetadata(
            report_id=report_id,
            source_pdf=project_relative_path(
                pdf_path,
                project_root or parsed_root.resolve().parents[1],
            ),
            pdf_type=pdf_type,  # type: ignore[arg-type]
            page_count=doc.page_count,
            markdown_path=relative_to_report(markdown_path, report_dir),
            pages_jsonl_path=relative_to_report(pages_jsonl_path, report_dir),
            tables_count=len(table_metadata),
            tables_dir="tables",
            tables_index_path="tables_index.jsonl",
            parse_quality_path=relative_to_report(quality_path, report_dir),
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


def _build_parse_quality(
    report_id: str,
    pages: list[PageText],
    tables_count: int,
    table_pages: list[int],
    warnings: list[str],
) -> dict:
    page_count = len(pages)
    char_counts = [page.char_count for page in pages]
    total_chars = sum(char_counts)
    empty_pages = [page.page for page in pages if page.char_count == 0]
    short_pages = [page.page for page in pages if 0 < page.char_count < 50]
    avg_chars = total_chars / page_count if page_count else 0
    min_chars = min(char_counts) if char_counts else 0
    max_chars = max(char_counts) if char_counts else 0
    chinese_chars, garbled_chars, visible_chars = _count_text_quality_chars(pages)
    chinese_char_ratio = chinese_chars / visible_chars if visible_chars else 0
    garbled_char_ratio = garbled_chars / visible_chars if visible_chars else 0
    quality_level = _quality_level(
        avg_chars=avg_chars,
        empty_pages_count=len(empty_pages),
        page_count=page_count,
        garbled_char_ratio=garbled_char_ratio,
        warnings_count=len(warnings),
    )

    return {
        "report_id": report_id,
        "page_count": page_count,
        "total_text_chars": total_chars,
        "avg_text_chars_per_page": round(avg_chars, 2),
        "min_text_chars_per_page": min_chars,
        "max_text_chars_per_page": max_chars,
        "empty_pages_count": len(empty_pages),
        "empty_pages": empty_pages,
        "short_text_pages_count": len(short_pages),
        "short_text_pages": short_pages,
        "tables_count": tables_count,
        "pages_with_tables": table_pages,
        "chinese_char_ratio": round(chinese_char_ratio, 4),
        "garbled_char_ratio": round(garbled_char_ratio, 4),
        "quality_level": quality_level,
        "recommended_for_dataset": quality_level in {"good", "excellent"},
        "warnings_count": len(warnings),
        "warnings": warnings,
    }


def _count_text_quality_chars(pages: list[PageText]) -> tuple[int, int, int]:
    text = "".join(page.text for page in pages)
    visible_chars = sum(1 for char in text if not char.isspace())
    chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    garbled_chars = sum(1 for char in text if char in {"�", "\ufffd", "□", "�"})
    return chinese_chars, garbled_chars, visible_chars


def _quality_level(
    avg_chars: float,
    empty_pages_count: int,
    page_count: int,
    garbled_char_ratio: float,
    warnings_count: int,
) -> str:
    empty_ratio = empty_pages_count / page_count if page_count else 1
    if warnings_count == 0 and avg_chars >= 500 and empty_ratio == 0 and garbled_char_ratio < 0.01:
        return "excellent"
    if avg_chars >= 200 and empty_ratio <= 0.05 and garbled_char_ratio < 0.03:
        return "good"
    if avg_chars >= 50 and empty_ratio <= 0.2 and garbled_char_ratio < 0.08:
        return "usable_with_review"
    return "poor"

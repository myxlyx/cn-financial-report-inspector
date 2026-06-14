"""PDF type detection based on extractable text availability."""

from __future__ import annotations

from pathlib import Path

import fitz

from fri_pdf.schema import PdfManifest, PdfType
from fri_pdf.utils import slugify_filename

MIN_AVG_TEXT_CHARS = 100
MIN_TEXT_PAGE_CHARS = 50
TEXT_BASED_PAGE_RATIO = 0.8
MIXED_PAGE_RATIO = 0.2


def classify_pdf(
    pdf_path: Path,
    report_id: str | None = None,
    source_pdf: str | None = None,
) -> PdfManifest:
    """Classify a PDF as text-based, mixed, scanned/image-based, or failed."""
    report_id = report_id or slugify_filename(pdf_path)
    notes: list[str] = []

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        return PdfManifest(
            report_id=report_id,
            source_pdf=source_pdf or str(pdf_path),
            pdf_type="parse_failed",
            page_count=0,
            text_pages=0,
            avg_text_chars_per_page=0,
            should_parse=False,
            notes=[f"Failed to open PDF: {exc}"],
        )

    try:
        page_count = doc.page_count
        if page_count == 0:
            return PdfManifest(
                report_id=report_id,
                source_pdf=source_pdf or str(pdf_path),
                pdf_type="parse_failed",
                page_count=0,
                text_pages=0,
                avg_text_chars_per_page=0,
                should_parse=False,
                notes=["PDF has zero pages."],
            )

        text_lengths: list[int] = []
        failed_pages = 0
        for page_index in range(page_count):
            try:
                text = doc.load_page(page_index).get_text("text") or ""
                text_lengths.append(len(text.strip()))
            except Exception as exc:
                failed_pages += 1
                text_lengths.append(0)
                notes.append(f"Page {page_index + 1}: text extraction failed during detection: {exc}")

        text_pages = sum(length >= MIN_TEXT_PAGE_CHARS for length in text_lengths)
        avg_text_chars = sum(text_lengths) / page_count
        text_page_ratio = text_pages / page_count

        pdf_type = _classify_from_metrics(text_page_ratio, avg_text_chars, failed_pages)
        should_parse = pdf_type == "text_based"
        if pdf_type != "text_based":
            notes.append(
                "Skipped full parsing because the PDF is not classified as text_based."
            )

        return PdfManifest(
            report_id=report_id,
            source_pdf=source_pdf or str(pdf_path),
            pdf_type=pdf_type,
            page_count=page_count,
            text_pages=text_pages,
            avg_text_chars_per_page=avg_text_chars,
            should_parse=should_parse,
            notes=notes,
        )
    except Exception as exc:
        return PdfManifest(
            report_id=report_id,
            source_pdf=source_pdf or str(pdf_path),
            pdf_type="parse_failed",
            page_count=doc.page_count if doc else 0,
            text_pages=0,
            avg_text_chars_per_page=0,
            should_parse=False,
            notes=[f"PDF detection failed: {exc}"],
        )
    finally:
        doc.close()


def _classify_from_metrics(
    text_page_ratio: float,
    avg_text_chars: float,
    failed_pages: int,
) -> PdfType:
    if failed_pages > 0 and text_page_ratio < TEXT_BASED_PAGE_RATIO:
        return "parse_failed"
    if text_page_ratio >= TEXT_BASED_PAGE_RATIO and avg_text_chars >= MIN_AVG_TEXT_CHARS:
        return "text_based"
    if text_page_ratio >= MIXED_PAGE_RATIO:
        return "mixed"
    return "scanned_or_image_based"

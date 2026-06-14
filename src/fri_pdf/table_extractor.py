"""Best-effort table extraction using PyMuPDF."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import fitz

from fri_pdf.schema import PageText, TableMetadata
from fri_pdf.utils import ensure_dir, write_json, write_jsonl


def extract_tables(
    doc: fitz.Document,
    report_dir: Path,
    pages: list[PageText] | None = None,
) -> tuple[list[TableMetadata], list[str]]:
    """Extract tables with page.find_tables when available.

    PyMuPDF table extraction support varies by version and PDF layout. This
    function is intentionally forgiving: page-level failures become warnings.
    """
    tables_dir = ensure_dir(report_dir / "tables")
    index_path = report_dir / "tables_index.jsonl"
    metadata: list[TableMetadata] = []
    warnings: list[str] = []

    for page_index in range(doc.page_count):
        page_number = page_index + 1
        page = doc.load_page(page_index)
        find_tables = getattr(page, "find_tables", None)
        if find_tables is None:
            warnings.append("PyMuPDF page.find_tables is unavailable in this environment.")
            break

        try:
            result = find_tables()
        except Exception as exc:
            warnings.append(f"Page {page_number}: table extraction failed: {exc}")
            continue

        page_tables = getattr(result, "tables", []) or []
        for table in page_tables:
            rows = _extract_table_rows(table)
            if not rows:
                continue

            table_id = f"table_{len(metadata) + 1:03d}"
            csv_path = tables_dir / f"{table_id}.csv"
            json_path = tables_dir / f"{table_id}.json"
            _write_csv(csv_path, rows)

            rows_count = len(rows)
            columns_count = max((len(row) for row in rows), default=0)
            title_candidate, section_candidate = _find_context_candidates(
                pages, page_number, getattr(table, "bbox", None)
            )
            item = TableMetadata(
                table_id=table_id,
                page=page_number,
                rows=rows_count,
                columns=columns_count,
                bbox=_bbox_to_list(getattr(table, "bbox", None)),
                source_method="pymupdf_find_tables",
                csv_path=f"tables/{table_id}.csv",
                json_path=f"tables/{table_id}.json",
                title_candidate=title_candidate,
                section_candidate=section_candidate,
                blank_cell_ratio=_blank_cell_ratio(rows),
                numeric_cell_ratio=_numeric_cell_ratio(rows),
                data=rows,
            )
            write_json(json_path, item.to_dict())
            metadata.append(item)

    write_jsonl(index_path, (item.to_dict() for item in metadata))
    return metadata, warnings


def _extract_table_rows(table: Any) -> list[list[str]]:
    try:
        rows = table.extract()
    except Exception:
        return []

    clean_rows: list[list[str]] = []
    for row in rows or []:
        clean_rows.append(["" if cell is None else str(cell).strip() for cell in row])
    return clean_rows


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def _bbox_to_list(bbox: Any) -> list[float] | None:
    if bbox is None:
        return None
    try:
        return [float(value) for value in bbox]
    except Exception:
        return None


def _blank_cell_ratio(rows: list[list[str]]) -> float:
    cells = [cell for row in rows for cell in row]
    if not cells:
        return 0.0
    blanks = sum(1 for cell in cells if not cell.strip())
    return round(blanks / len(cells), 4)


def _numeric_cell_ratio(rows: list[list[str]]) -> float:
    cells = [cell for row in rows for cell in row if cell.strip()]
    if not cells:
        return 0.0
    numeric_cells = sum(1 for cell in cells if _looks_numeric(cell))
    return round(numeric_cells / len(cells), 4)


def _looks_numeric(value: str) -> bool:
    cleaned = value.strip()
    cleaned = cleaned.replace(",", "").replace("，", "")
    cleaned = cleaned.replace("%", "").replace("％", "")
    cleaned = cleaned.replace("(", "-").replace(")", "")
    cleaned = cleaned.replace("（", "-").replace("）", "")
    if cleaned in {"", "-", "--", "不适用"}:
        return False
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", cleaned))


def _find_context_candidates(
    pages: list[PageText] | None,
    page_number: int,
    bbox: Any,
) -> tuple[str | None, str | None]:
    _ = bbox
    if not pages or page_number < 1 or page_number > len(pages):
        return None, None

    page_text = pages[page_number - 1].text
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return None, None

    title = _nearest_table_title(lines)
    section = _nearest_section(lines)
    return title, section


def _nearest_table_title(lines: list[str]) -> str | None:
    for line in lines:
        if re.search(r"(项目|金额|单位[:：])", line) and len(line) <= 80:
            return line
    for line in lines:
        if re.search(r"表", line) and not _nearest_section([line]) and len(line) <= 80:
            return line
    return lines[0][:80] if lines else None


def _nearest_section(lines: list[str]) -> str | None:
    section_pattern = re.compile(r"^([一二三四五六七八九十]+、|\d+(\.\d+)*\s+|第[一二三四五六七八九十\d]+[章节])")
    for line in lines:
        if re.fullmatch(r"\d+\s*/\s*\d+", line):
            continue
        if section_pattern.search(line) and len(line) <= 120:
            return line
    return None

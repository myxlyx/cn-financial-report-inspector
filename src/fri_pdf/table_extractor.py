"""Best-effort table extraction using PyMuPDF."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import fitz

from fri_pdf.schema import TableMetadata
from fri_pdf.utils import ensure_dir, write_json


def extract_tables(
    doc: fitz.Document,
    report_dir: Path,
) -> tuple[list[TableMetadata], list[str]]:
    """Extract tables with page.find_tables when available.

    PyMuPDF table extraction support varies by version and PDF layout. This
    function is intentionally forgiving: page-level failures become warnings.
    """
    tables_dir = ensure_dir(report_dir / "tables")
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
            item = TableMetadata(
                table_id=table_id,
                page=page_number,
                rows=rows_count,
                columns=columns_count,
                bbox=_bbox_to_list(getattr(table, "bbox", None)),
                source_method="pymupdf_find_tables",
                csv_path=f"tables/{table_id}.csv",
            )
            write_json(json_path, item.to_dict())
            metadata.append(item)

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

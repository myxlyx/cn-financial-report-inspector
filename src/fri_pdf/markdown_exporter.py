"""Markdown and JSONL exporters for page-level PDF text."""

from __future__ import annotations

from pathlib import Path

from fri_pdf.schema import PageText
from fri_pdf.utils import ensure_dir, write_jsonl


def export_markdown(pages: list[PageText], output_path: Path) -> None:
    ensure_dir(output_path.parent)
    sections: list[str] = []
    for page in pages:
        text = page.text.strip()
        sections.append(f"<!-- page: {page.page} -->\n# Page {page.page}\n\n{text}\n")
    output_path.write_text("\n".join(sections), encoding="utf-8", newline="\n")


def export_pages_jsonl(pages: list[PageText], output_path: Path) -> None:
    write_jsonl(output_path, (page.to_dict() for page in pages))

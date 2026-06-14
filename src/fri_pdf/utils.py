"""Small file and JSON helpers."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Iterable


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def reset_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    return ensure_dir(path)


def slugify_filename(path: Path, max_base_len: int = 80) -> str:
    """Create a filesystem-safe report id from a possibly Chinese filename."""
    stem = path.stem.strip()
    cleaned = re.sub(r"[\\/:*?\"<>|：]+", "_", stem)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    if not cleaned:
        cleaned = "report"

    digest = hashlib.sha1(path.name.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:max_base_len]}_{digest}"


def write_json(path: Path, data: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def find_pdf_files(input_dir: Path) -> list[Path]:
    """Find PDFs in a directory using a case-insensitive suffix check."""
    if not input_dir.exists():
        return []
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def relative_to_report(path: Path, report_dir: Path) -> str:
    return path.relative_to(report_dir).as_posix()


def project_relative_path(path: Path, project_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = project_root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()

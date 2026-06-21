from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - optional dependency
    tqdm = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fri_pdf.parser import process_pdf  # noqa: E402
from fri_pdf.utils import ensure_dir, find_pdf_files  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse Chinese financial report PDFs.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw_pdfs",
        help="Directory containing PDFs. Defaults to data/raw_pdfs.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        action="append",
        default=[],
        help="Specific PDF path to parse. Can be supplied multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N PDFs after sorting.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and regenerate each parsed report output directory.",
    )
    parser.add_argument(
        "--table-mode",
        choices=("all", "candidate", "none"),
        default="candidate",
        help=(
            "Table extraction scope: all pages, keyword candidate pages, or none. "
            "Defaults to candidate."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_pdf_dir = args.input_dir
    parsed_root = ensure_dir(PROJECT_ROOT / "data" / "parsed_reports")
    manifests_root = ensure_dir(PROJECT_ROOT / "data" / "manifests")

    pdf_paths = _resolve_pdf_paths(raw_pdf_dir, args.pdf)
    if args.limit is not None:
        pdf_paths = pdf_paths[: max(args.limit, 0)]

    if not pdf_paths:
        print(f"No PDFs found under {raw_pdf_dir}")
        return 0

    iterator = tqdm(pdf_paths, desc="Parsing PDFs") if tqdm else pdf_paths
    results = [
        process_pdf(
            path,
            parsed_root,
            manifests_root,
            force=args.force,
            table_mode=args.table_mode,
        )
        for path in iterator
    ]

    parsed_count = sum(result.parsed for result in results)
    skipped_count = len(results) - parsed_count
    print("\nPDF parsing summary")
    print(f"- PDFs found: {len(results)}")
    print(f"- Parsed text-based PDFs: {parsed_count}")
    print(f"- Skipped PDFs: {skipped_count}")
    print(f"- Table mode: {args.table_mode}")
    print(f"- Manifests: {manifests_root}")
    print(f"- Parsed reports: {parsed_root}")

    for result in results:
        status = "parsed" if result.parsed else "skipped"
        print(
            f"  - {result.report_id}: {status}, "
            f"type={result.manifest.pdf_type}, "
            f"pages={result.manifest.page_count}, "
            f"text_pages={result.manifest.text_pages}"
        )
        if result.warnings:
            print(f"    warnings: {len(result.warnings)}")

    return 0


def _resolve_pdf_paths(input_dir: Path, explicit_pdfs: list[Path]) -> list[Path]:
    if explicit_pdfs:
        paths = [path if path.is_absolute() else (PROJECT_ROOT / path) for path in explicit_pdfs]
    else:
        paths = find_pdf_files(input_dir if input_dir.is_absolute() else PROJECT_ROOT / input_dir)

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved.suffix.lower() != ".pdf":
            continue
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return sorted(unique)


if __name__ == "__main__":
    raise SystemExit(main())

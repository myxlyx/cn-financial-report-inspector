from __future__ import annotations

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
from fri_pdf.utils import ensure_dir  # noqa: E402


def main() -> int:
    raw_pdf_dir = PROJECT_ROOT / "data" / "raw_pdfs"
    parsed_root = ensure_dir(PROJECT_ROOT / "data" / "parsed_reports")
    manifests_root = ensure_dir(PROJECT_ROOT / "data" / "manifests")

    pdf_paths = sorted(raw_pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found under {raw_pdf_dir}")
        return 0

    iterator = tqdm(pdf_paths, desc="Parsing PDFs") if tqdm else pdf_paths
    results = [process_pdf(path, parsed_root, manifests_root) for path in iterator]

    parsed_count = sum(result.parsed for result in results)
    skipped_count = len(results) - parsed_count
    print("\nPDF parsing summary")
    print(f"- PDFs found: {len(results)}")
    print(f"- Parsed text-based PDFs: {parsed_count}")
    print(f"- Skipped PDFs: {skipped_count}")
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


if __name__ == "__main__":
    raise SystemExit(main())

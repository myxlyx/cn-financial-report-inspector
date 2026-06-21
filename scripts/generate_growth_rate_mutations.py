from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fri_mutation.runner import (  # noqa: E402
    discover_source_reports,
    generate_report_mutations,
)


def _decimal_argument(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("delta must be a decimal number") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and validate synthetic reported growth-rate errors."
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "parsed_reports",
    )
    parser.add_argument("--report-id")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "mutated_reports",
    )
    parser.add_argument("--max-mutations-per-report", type=int, default=3)
    parser.add_argument(
        "--strategy",
        choices=("add_delta", "replace_with_zero", "swap_sign"),
        default="add_delta",
    )
    parser.add_argument("--delta", type=_decimal_argument, default=Decimal("5.00"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    parsed_dir = _project_path(args.parsed_dir)
    output_dir = _project_path(args.output_dir)
    if args.max_mutations_per_report < 0:
        print("max-mutations-per-report must be non-negative", file=sys.stderr)
        return 2

    try:
        report_dirs = discover_source_reports(parsed_dir, report_id=args.report_id)
        summaries = [
            generate_report_mutations(
                source_report_dir=report_dir,
                output_dir=output_dir,
                max_mutations=args.max_mutations_per_report,
                strategy=args.strategy,
                delta=args.delta,
                force=args.force,
            )
            for report_dir in report_dirs
        ]
    except (FileNotFoundError, FileExistsError, OSError, ValueError) as exc:
        print(f"Mutation generation failed: {exc}", file=sys.stderr)
        return 1

    print("Growth-rate mutation summary")
    print(f"- Reports processed: {len(summaries)}")
    print(f"- Mutations generated: {sum(item.mutations_count for item in summaries)}")
    print(
        "- Validated detections: "
        f"{sum(item.validation_detected_count for item in summaries)}"
    )
    for summary in summaries:
        print(
            f"  - {summary.source_report_id}: mutations={summary.mutations_count}, "
            f"detected={summary.validation_detected_count}, "
            f"skipped={summary.skipped_candidates_count}"
        )
    return 0


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())

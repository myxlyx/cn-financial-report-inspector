from __future__ import annotations

import argparse
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fri_checks.quarterly_runner import run_all_quarterly_sum_checks  # noqa: E402


def _decimal_argument(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(
            "absolute tolerance must be a decimal number"
        ) from exc
    if result < 0:
        raise argparse.ArgumentTypeError("absolute tolerance must be non-negative")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check quarterly key metrics against annual values."
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "parsed_reports",
        help="Parsed report root. Defaults to data/parsed_reports.",
    )
    parser.add_argument(
        "--report-id",
        help="Run only one parsed report directory.",
    )
    parser.add_argument(
        "--absolute-tolerance",
        type=_decimal_argument,
        default=Decimal("1.00"),
        help="Allowed absolute difference. Defaults to 1.00.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    parsed_dir = args.parsed_dir
    if not parsed_dir.is_absolute():
        parsed_dir = PROJECT_ROOT / parsed_dir

    try:
        summaries = run_all_quarterly_sum_checks(
            parsed_dir=parsed_dir,
            report_id=args.report_id,
            absolute_tolerance=args.absolute_tolerance,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Quarterly sum checks failed: {exc}", file=sys.stderr)
        return 1

    print("Quarterly sum check summary")
    print(f"- Reports processed: {len(summaries)}")
    print(f"- Reports with checks: {sum(summary.checks_count > 0 for summary in summaries)}")
    print(f"- Checks: {sum(summary.checks_count for summary in summaries)}")
    print(f"- OK: {sum(summary.ok_count for summary in summaries)}")
    print(f"- Mismatches: {sum(summary.mismatch_count for summary in summaries)}")
    print(
        "- Not applicable: "
        f"{sum(summary.not_applicable_count for summary in summaries)}"
    )
    print(
        "- Review required: "
        f"{sum(summary.review_required_count for summary in summaries)}"
    )
    print(
        "- Duplicate tasks skipped: "
        f"{sum(summary.duplicate_skipped_count for summary in summaries)}"
    )
    for summary in summaries:
        print(
            f"  - {summary.report_id}: candidates={summary.candidate_tables}, "
            f"checks={summary.checks_count}, ok={summary.ok_count}, "
            f"mismatches={summary.mismatch_count}, "
            f"not_applicable={summary.not_applicable_count}, "
            f"duplicates_skipped={summary.duplicate_skipped_count}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

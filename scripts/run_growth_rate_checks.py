from __future__ import annotations

import argparse
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fri_checks.runner import run_all_reports  # noqa: E402


def _decimal_argument(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("tolerance must be a decimal number") from exc
    if result < 0:
        raise argparse.ArgumentTypeError("tolerance must be non-negative")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check reported annual growth rates using deterministic rules."
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
        "--tolerance",
        type=_decimal_argument,
        default=Decimal("0.05"),
        help="Allowed percentage-point difference. Defaults to 0.05.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    parsed_dir = args.parsed_dir
    if not parsed_dir.is_absolute():
        parsed_dir = PROJECT_ROOT / parsed_dir

    try:
        summaries = run_all_reports(
            parsed_dir=parsed_dir,
            report_id=args.report_id,
            tolerance=args.tolerance,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Growth-rate checks failed: {exc}", file=sys.stderr)
        return 1

    print("Growth-rate check summary")
    print(f"- Reports processed: {len(summaries)}")
    print(f"- Checks: {sum(summary.checks_count for summary in summaries)}")
    print(f"- OK: {sum(summary.ok_count for summary in summaries)}")
    print(f"- Mismatches: {sum(summary.mismatch_count for summary in summaries)}")
    print(
        "- Review required: "
        f"{sum(summary.review_required_count for summary in summaries)}"
    )
    for summary in summaries:
        print(
            f"  - {summary.report_id}: tables={summary.tables_scanned}, "
            f"candidates={summary.candidate_tables}, checks={summary.checks_count}, "
            f"ok={summary.ok_count}, mismatches={summary.mismatch_count}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fri_dataset.manifest_builder import build_dataset_manifest  # noqa: E402


OUTPUT_FILES = (
    "dataset_manifest.json",
    "reports_manifest.jsonl",
    "checks_manifest.jsonl",
    "mutations_manifest.jsonl",
    "dataset_stats.json",
    "dataset_card.md",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a reproducible benchmark index from pipeline outputs."
    )
    parser.add_argument("--batch-name", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--parsed-dir", type=Path, required=True)
    parser.add_argument("--mutated-dir", type=Path, required=True)
    parser.add_argument("--batch-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = _project_path(args.output_dir)
    try:
        result = build_dataset_manifest(
            batch_name=args.batch_name,
            source_dir=_project_path(args.source_dir),
            parsed_dir=_project_path(args.parsed_dir),
            mutated_dir=_project_path(args.mutated_dir),
            batch_report=_project_path(args.batch_report),
            output_dir=output_dir,
            project_root=PROJECT_ROOT,
            force=args.force,
        )
    except (
        FileNotFoundError,
        FileExistsError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Dataset manifest build failed: {exc}", file=sys.stderr)
        return 1

    stats = result["stats"]
    print("Dataset manifest summary")
    print(f"- Reports included: {stats['reports']['total']}")
    print(f"- Original checks included: {stats['original_checks']['total']}")
    print(f"- Mutations included: {stats['mutations']['total']}")
    print(f"- Validation warnings: {len(stats['validation_warnings'])}")
    for warning in stats["validation_warnings"]:
        print(f"  - {warning}")
    print("- Output files:")
    for filename in OUTPUT_FILES:
        print(f"  - {_display_path(output_dir / filename)}")
    return 0


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


if __name__ == "__main__":
    raise SystemExit(main())

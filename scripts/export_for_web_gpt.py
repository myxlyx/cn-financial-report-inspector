from __future__ import annotations

import argparse
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a zip package for web GPT review using Git-tracked files."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "exports" / "webgpt",
        help="Directory where the zip file will be written.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Optional zip filename. Defaults to cn-financial-report-inspector-<timestamp>.zip.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_name = args.name or f"cn-financial-report-inspector-{_timestamp()}.zip"
    if not zip_name.lower().endswith(".zip"):
        zip_name += ".zip"
    zip_path = output_dir / zip_name

    tracked_files = _git_ls_files()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in tracked_files:
            source = PROJECT_ROOT / relative_path
            if source.is_file():
                archive.write(source, arcname=relative_path.as_posix())

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Created {zip_path}")
    print(f"Files: {len(tracked_files)}")
    print(f"Size: {size_mb:.2f} MB")
    return 0


def _git_ls_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    names = result.stdout.decode("utf-8").split("\0")
    return [Path(name) for name in names if name]


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


if __name__ == "__main__":
    raise SystemExit(main())

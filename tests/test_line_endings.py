from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _tracked_text_files() -> list[Path]:
    files = [
        PROJECT_ROOT / ".gitattributes",
        PROJECT_ROOT / ".gitignore",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "pyproject.toml",
    ]
    for pattern in ("scripts/*.py", "src/**/*.py", "tests/**/*.py"):
        files.extend(PROJECT_ROOT.glob(pattern))
    return sorted(path for path in files if path.is_file())


def test_source_and_config_files_use_lf_line_endings():
    offenders = []
    for path in _tracked_text_files():
        data = path.read_bytes()
        if b"\r" in data:
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []

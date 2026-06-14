from pathlib import Path
import importlib.util


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "parse_pdfs.py"
SPEC = importlib.util.spec_from_file_location("parse_pdfs_script", SCRIPT_PATH)
assert SPEC is not None
parse_pdfs_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(parse_pdfs_script)
_resolve_pdf_paths = parse_pdfs_script._resolve_pdf_paths


def test_resolve_pdf_paths_from_input_dir_handles_uppercase_suffix(tmp_path: Path):
    pdf = tmp_path / "A.PDF"
    other = tmp_path / "B.txt"
    pdf.write_bytes(b"%PDF")
    other.write_text("ignore", encoding="utf-8")

    assert _resolve_pdf_paths(tmp_path, []) == [pdf.resolve()]


def test_resolve_pdf_paths_deduplicates_explicit_pdfs(tmp_path: Path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")

    assert _resolve_pdf_paths(tmp_path, [pdf, pdf]) == [pdf.resolve()]

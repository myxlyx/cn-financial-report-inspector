---
tags:
- pdf-processing
- chinese-financial-reports
- annual-reports
- pymupdf
- research
---

# cn-financial-report-inspector

`cn-financial-report-inspector` is a research project for inspecting Chinese listed-company annual reports. The long-term direction is an Adaptive RAG / Agent system, but this stage intentionally focuses only on the PDF processing module.

## Current Scope

The MVP converts text-based Chinese financial report PDFs into clean intermediate files for later table checking, RAG indexing, and synthetic error construction.

This stage does not implement:

- RAG
- Agent workflows
- Law or regulation knowledge graphs
- Financial error detection
- OCR

Scanned PDFs or badly parsed PDFs are intentionally detected and excluded in stage 1.

## Where To Put PDFs

Place source PDFs under:

```text
data/raw_pdfs/
```

PDF filenames may contain Chinese characters. The parser does not hard-code any report names.

## Data Policy For GitHub

The GitHub repository intentionally does not include the full raw PDFs or full parsed outputs. Those files can be large and may also need separate data-governance decisions.

GitHub tracks only compact examples under:

```text
data/sample_reports/
```

The sample files show the expected manifest, metadata, page JSONL, Markdown excerpt, and table CSV/JSON formats. Put full local inputs and generated outputs under `data/raw_pdfs/`, `data/parsed_reports/`, and `data/manifests/`; these paths are ignored by Git.

## Install Dependencies

```bash
pip install -e .
```

The MVP uses lightweight dependencies:

- PyMuPDF
- pandas
- tqdm

## Run Parsing

From the project root:

```bash
python scripts/parse_pdfs.py
```

The script will:

1. Detect each PDF type.
2. Write one manifest JSON per PDF.
3. Skip PDFs that are not classified as `text_based`.
4. Extract page-level text from text-based PDFs.
5. Export Markdown, JSONL pages, table CSV/JSON files, and report metadata.
6. Print a concise terminal summary.

## Output Structure

```text
data/
  manifests/
    <report_id>.json
  parsed_reports/
    <report_id>/
      report.md
      pages.jsonl
      metadata.json
      tables/
        table_001.csv
        table_001.json
```

Manifest example:

```json
{
  "report_id": "...",
  "source_pdf": "...",
  "pdf_type": "text_based",
  "page_count": 0,
  "text_pages": 0,
  "avg_text_chars_per_page": 0,
  "should_parse": true,
  "notes": []
}
```

Page JSONL line example:

```json
{"page": 1, "text": "...", "char_count": 1234}
```

Report metadata example:

```json
{
  "report_id": "...",
  "source_pdf": "...",
  "pdf_type": "text_based",
  "page_count": 0,
  "markdown_path": "report.md",
  "pages_jsonl_path": "pages.jsonl",
  "tables_count": 0,
  "tables_dir": "tables",
  "parse_warnings": []
}
```

## PDF Type Detection

The first version uses PyMuPDF to inspect:

- page count
- pages with extractable text
- average text characters per page
- whether most pages have selectable text

PDFs are classified as:

- `text_based`
- `mixed`
- `scanned_or_image_based`
- `parse_failed`

Only `text_based` PDFs are fully parsed.

## Current Limitations

- No OCR is performed.
- Scanned and image-based PDFs are skipped by design.
- Table extraction uses PyMuPDF `page.find_tables()` on a best-effort basis.
- Table extraction quality depends on the PDF layout and installed PyMuPDF version.
- Extracted text is page-level plain text, not a semantic document hierarchy.

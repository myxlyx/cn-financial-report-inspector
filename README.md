---
tags:
- pdf-processing
- chinese-financial-reports
- annual-reports
- pymupdf
- research
---

# cn-financial-report-inspector

`cn-financial-report-inspector` is a research project for inspecting Chinese listed-company annual reports. The long-term direction is an Adaptive RAG / Agent system. The current project contains a stable PDF processing module, one narrowly scoped deterministic financial check, and JSON-level mutation samples for that check.

## Current Scope

The PDF module converts text-based Chinese financial report PDFs into clean intermediate files. Financial checks v0.1 uses those files to verify reported growth rates in annual key financial metric tables. Mutation samples v0.1 introduces labeled errors only in copied table JSON data.

This stage does not implement:

- RAG
- Agent workflows
- Law or regulation knowledge graphs
- AI-based or general-purpose financial error detection
- OCR

Scanned PDFs or badly parsed PDFs are intentionally detected and excluded in stage 1.

## Where To Put PDFs

Place source PDFs under:

```text
data/raw_pdfs/
```

PDF filenames may contain Chinese characters. The parser does not hard-code any report names.

## Data Policy For GitHub

The GitHub repository intentionally does not include every raw PDF or every parsed output. Full datasets can be large and may also need separate data-governance decisions.

To make the repository useful for code review and web-based analysis, GitHub tracks one complete real example using the same directory layout as local runs:

```text
data/raw_pdfs/
data/manifests/
data/parsed_reports/
data/mutated_reports/
```

Other full local inputs and generated outputs under these directories are ignored by Git. The tracked example shows the expected manifest, metadata, parse quality report, page JSONL, Markdown, table index, and table CSV/JSON formats.

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

Useful options:

```bash
python scripts/parse_pdfs.py --input-dir data/raw_pdfs
python scripts/parse_pdfs.py --pdf data/raw_pdfs/example.pdf
python scripts/parse_pdfs.py --limit 1
python scripts/parse_pdfs.py --force
python scripts/parse_pdfs.py --table-mode candidate
python scripts/parse_pdfs.py --table-mode none
```

`--force` removes and regenerates each selected report output directory. PDF discovery is case-insensitive, so both `.pdf` and `.PDF` files are supported.

Table extraction defaults to `candidate` mode so PyMuPDF does not run `page.find_tables()` across every page of a long annual report:

- `candidate`: extract only pages containing annual key-metric or growth-rate keywords.
- `none`: skip table extraction while still writing text, metadata, quality data, and an empty table index.
- `all`: attempt table extraction on every page. This preserves the original exhaustive behavior and can be slow on complex PDFs.

Candidate or disabled modes record skipped-page information in `metadata.json` and `parse_quality.json`. The terminal summary reports the warning count.

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
      parse_quality.json
      tables_index.jsonl
      tables/
        table_001.csv
        table_001.json
      checks/
        growth_rate_checks.jsonl
        growth_rate_summary.json
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
  "tables_index_path": "tables_index.jsonl",
  "parse_quality_path": "parse_quality.json",
  "parse_warnings": []
}
```

Each table JSON stores both metadata and full table data:

```json
{
  "table_id": "table_001",
  "page": 12,
  "rows": 10,
  "columns": 5,
  "title_candidate": "...",
  "section_candidate": "...",
  "blank_cell_ratio": 0.12,
  "numeric_cell_ratio": 0.45,
  "csv_path": "tables/table_001.csv",
  "json_path": "tables/table_001.json",
  "data": [["项目", "金额"]]
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

## Financial Checks v0.1

This first check identifies tables related to `近三年主要会计数据和财务指标`, maps the item, current-year, previous-year, and reported growth-rate columns, and creates structured calculation tasks.

No LLM or LLM API is used. Rule-based mapping produces the tasks, and Python `Decimal` performs the calculation:

```text
growth_rate = (current - previous) / abs(previous) * 100
```

Run checks for all parsed reports:

```bash
python scripts/run_growth_rate_checks.py --parsed-dir data/parsed_reports
```

Useful options:

```bash
python scripts/run_growth_rate_checks.py --report-id <report_id>
python scripts/run_growth_rate_checks.py --tolerance 0.05
```

Each report receives:

```text
data/parsed_reports/<report_id>/checks/
  growth_rate_checks.jsonl
  growth_rate_summary.json
```

This is only a consistency check for one reported growth-rate formula. It is not a complete financial audit, semantic table classifier, or AI error-detection system. Rows reported as percentage-point changes are intentionally not evaluated with the growth-rate formula.

## Growth-rate Mutation Samples v0.1

Mutation samples are created from parsed table JSON, never from the original PDF. Version 0.1 changes only the disclosed growth-rate cell; current-year and previous-year values remain unchanged.

Run mutation generation after the source growth-rate checks exist:

```bash
python scripts/generate_growth_rate_mutations.py \
  --parsed-dir data/parsed_reports \
  --output-dir data/mutated_reports \
  --max-mutations-per-report 3 \
  --strategy add_delta \
  --force
```

Supported deterministic strategies are `add_delta`, `replace_with_zero`, and `swap_sign`. Each mutation directory contains a ground-truth `mutation_label.json`, a summary, copied table JSON data, and fresh checker outputs:

```text
data/mutated_reports/<source_report_id>/growth_rate_mutation_001/
  tables_index.jsonl
  tables/*.json
  metadata.json
  parse_quality.json
  mutation_label.json
  mutation_summary.json
  checks/
    growth_rate_checks.jsonl
    growth_rate_summary.json
```

The existing checker runs after every mutation. The label records whether the target was detected as `mismatch` with `review_required=true`. This stage does not edit PDFs or generate synthetic PDFs.

## Current Limitations

- No OCR is performed.
- Scanned and image-based PDFs are skipped by design.
- Table extraction uses PyMuPDF `page.find_tables()` on a best-effort basis and defaults to keyword candidate pages.
- Table extraction quality depends on the PDF layout and installed PyMuPDF version.
- Extracted text is page-level plain text, not a semantic document hierarchy.
- Financial checks v0.1 depends on recognizable annual key-metric table headers.
- Ambiguous mappings are marked for future semantic mapping instead of calling an LLM.
- Mutation samples v0.1 only target reported growth-rate cells in table JSON.

# Validation Log

Generated for the targeted Fuxing quarterly-table fix.

## Code Validation

```text
python -m py_compile scripts/parse_pdfs.py scripts/export_for_web_gpt.py scripts/run_growth_rate_checks.py scripts/run_quarterly_sum_checks.py scripts/generate_growth_rate_mutations.py scripts/summarize_batch_results.py scripts/build_dataset_manifest.py src/fri_pdf/*.py src/fri_checks/*.py src/fri_mutation/*.py src/fri_dataset/*.py
Result: passed
```

```text
pytest -q
Result: 81 passed in 2.16s
```

## Full Local Quarterly Validation

```text
python scripts/parse_pdfs.py --input-dir data/raw_reports/user_offer_01 --table-mode candidate --force
PDFs found: 10
Parsed text-based PDFs: 10
Skipped PDFs: 0
Table mode: candidate
```

```text
python scripts/run_growth_rate_checks.py --parsed-dir data/parsed_reports
Reports processed: 13
Checks: 113
OK: 95
Mismatches: 0
Review required: 0

Filtered user_offer_01 growth-rate summary:
Reports included: 10
Original growth-rate checks: 86
Original growth-rate mismatches: 0
```

```text
python scripts/run_quarterly_sum_checks.py --parsed-dir data/parsed_reports
Reports processed: 13
Reports with checks: 12
Checks: 37
OK: 37
Mismatches: 0
Not applicable: 0
Review required: 0
Duplicate tasks skipped: 0

Filtered user_offer_01 quarterly summary:
Reports processed: 10
Reports with quarterly checks: 10
Reports without quarterly checks: 0
Total quarterly checks: 30
OK: 30
Mismatches: 0
Not applicable: 0
Review required: 0
Duplicate tasks skipped: 0
```

## Fuxing Regression Check

Report: `000926_fuxing_2025_annual_report_79c79b2f`

```text
Quarterly candidate tables: 1
Quarterly checks: 4
OK: 4
Mismatches: 0
Not applicable: 0
Review required: 0
Duplicate tasks skipped: 0
```

The selected table is `table_010` on page 8. It is a standard one-year quarterly key metrics table and is no longer incorrectly marked as `multi_year_quarterly_comparison`.

## Scope Guardrails

- Original PDFs were not modified.
- The lightweight review bundle does not include the 10 `user_offer_01` PDFs.
- No LLM API, RAG, Agent, Law KG, PDF editing, synthetic PDF generation, new check type, or quarterly mutation sample was implemented.

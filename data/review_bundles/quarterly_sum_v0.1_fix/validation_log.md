# Validation Log

Generated for `quarterly_sum_v0.1_fix`.

## Code Validation

```text
python -m py_compile scripts/parse_pdfs.py scripts/export_for_web_gpt.py scripts/run_growth_rate_checks.py scripts/run_quarterly_sum_checks.py scripts/generate_growth_rate_mutations.py scripts/summarize_batch_results.py scripts/build_dataset_manifest.py src/fri_pdf/*.py src/fri_checks/*.py src/fri_mutation/*.py src/fri_dataset/*.py
Result: passed
```

```text
pytest -q
Result: 79 passed in 2.06s
```

## Full Local Pipeline

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

Filtered user_offer_01 batch summary:
Reports included: 10
Original growth-rate checks: 86
Mutations generated later: 29
```

```text
python scripts/run_quarterly_sum_checks.py --parsed-dir data/parsed_reports
Reports processed: 13
Reports with checks: 10
Checks: 30
OK: 30
Mismatches: 0
Not applicable: 0
Review required: 0
Duplicate tasks skipped: 4

Filtered user_offer_01 quarterly summary:
Reports processed: 10
Reports with quarterly checks: 9
Reports without quarterly checks: 1
Total quarterly checks: 26
OK: 26
Mismatches: 0
Not applicable: 0
Review required: 0
Duplicate tasks skipped: 2
```

```text
python scripts/generate_growth_rate_mutations.py --parsed-dir data/parsed_reports --output-dir data/mutated_reports --max-mutations-per-report 3 --strategy add_delta --force
Reports processed: 13
Mutations generated: 38
Validated detections: 38

Filtered user_offer_01 mutation summary:
Mutations generated: 29
Mutations detected: 29
```

```text
python scripts/run_growth_rate_checks.py --parsed-dir data/mutated_reports
Reports processed: 38
Checks: 330
OK: 245
Mismatches: 38
Review required: 38
```

```text
python scripts/summarize_batch_results.py --parsed-dir data/parsed_reports --mutated-dir data/mutated_reports --source-dir data/raw_reports/user_offer_01 --output data/batch_reports/user_offer_01_summary.md
Batch: user_offer_01
PDFs found: 10
Parsed reports: 10
Growth-rate checks: 86
Mutations generated: 29
Mutations detected: 29
```

```text
python scripts/build_dataset_manifest.py --batch-name user_offer_01 --source-dir data/raw_reports/user_offer_01 --parsed-dir data/parsed_reports --mutated-dir data/mutated_reports --batch-report data/batch_reports/user_offer_01_summary.json --output-dir data/datasets/user_offer_01 --force
Reports included: 10
Original checks included: 86
Mutations included: 29
Validation warnings: 0
```

## ST Fucheng Spot Check

The tracked ST Fucheng sample was re-parsed with the updated candidate page logic.

```text
python scripts/parse_pdfs.py --pdf data/raw_pdfs/_ST福成：福成股份：2025年年度报告(更正后）.pdf --table-mode candidate --force
Parsed text-based PDFs: 1
```

```text
python scripts/run_quarterly_sum_checks.py --parsed-dir data/parsed_reports --report-id ST福成_福成股份_2025年年度报告(更正后）_281d4b63
Reports processed: 1
Reports with checks: 1
Checks: 3
OK: 3
Mismatches: 0
Not applicable: 0
Review required: 0
Duplicate tasks skipped: 0
```

## Scope Guardrails

- Original PDFs were not modified.
- The lightweight review bundle does not include the 10 `user_offer_01` PDFs.
- No LLM API, RAG, Agent, Law KG, PDF editing, synthetic PDF generation, new check type, or quarterly mutation sample was implemented.

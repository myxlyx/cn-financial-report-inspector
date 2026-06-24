# Quarterly Sum v0.1 Fix Review Bundle

This lightweight bundle is for project review only. It does not include the 10 original annual-report PDFs.

The source PDFs remain local under `data/raw_reports/user_offer_01/`. Their file sizes and SHA-256 digests are listed in `source_pdf_hashes.json` so reviewers can verify source identity without receiving the PDFs.

## Commands Used

```bash
python scripts/parse_pdfs.py --input-dir data/raw_reports/user_offer_01 --table-mode candidate --force
python scripts/run_growth_rate_checks.py --parsed-dir data/parsed_reports
python scripts/run_quarterly_sum_checks.py --parsed-dir data/parsed_reports
python scripts/generate_growth_rate_mutations.py --parsed-dir data/parsed_reports --output-dir data/mutated_reports --max-mutations-per-report 3 --strategy add_delta --force
python scripts/run_growth_rate_checks.py --parsed-dir data/mutated_reports
python scripts/summarize_batch_results.py --parsed-dir data/parsed_reports --mutated-dir data/mutated_reports --source-dir data/raw_reports/user_offer_01 --output data/batch_reports/user_offer_01_summary.md
python scripts/build_dataset_manifest.py --batch-name user_offer_01 --source-dir data/raw_reports/user_offer_01 --parsed-dir data/parsed_reports --mutated-dir data/mutated_reports --batch-report data/batch_reports/user_offer_01_summary.json --output-dir data/datasets/user_offer_01 --force
```

## Files

- `validation_log.md`: concise command results from the validation run.
- `source_pdf_hashes.json`: local source PDF names, paths, sizes, and SHA-256 hashes.
- `batch_quarterly_summary.json` / `.md`: batch-level and per-report quarterly check summaries.
- `selected_quarterly_checks.jsonl`: all quarterly sum checks for `user_offer_01`.
- `selected_quarterly_diagnostics.jsonl`: mapped quarterly candidates, duplicate skips, and mapping failures.
- `selected_table_previews.json`: preview rows for quarterly tables used in checks or diagnostics.

This bundle does not change the scope of the project: no LLM, RAG, Agent, Law KG, PDF editing, synthetic PDF generation, or quarterly mutation samples are included.

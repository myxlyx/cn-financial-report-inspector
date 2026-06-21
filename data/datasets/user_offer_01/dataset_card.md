# user_offer_01_growth_rate_benchmark

## Version

`0.1`

## Purpose

This benchmark indexes deterministic growth-rate consistency checks for Chinese listed-company annual reports. It is intended for reproducible pipeline evaluation, not as a complete financial audit dataset.

## Source documents

- Batch: `user_offer_01`
- Source directory: `data/raw_reports/user_offer_01`
- Reports: 10
- Language: Chinese

Source PDF paths and SHA-256 digests are recorded in `reports_manifest.jsonl`. Original PDFs are never modified.

## Task definition

The task verifies whether a disclosed growth rate agrees with current-year and previous-year values in annual key financial metrics tables. Python `Decimal` performs the calculation; no LLM is used.

## Data format

- `dataset_manifest.json`: dataset identity and provenance.
- `reports_manifest.jsonl`: one row per source report.
- `checks_manifest.jsonl`: one row per original deterministic check.
- `mutations_manifest.jsonl`: one row per labeled mutation and its validation result.
- `dataset_stats.json`: aggregate counts, coverage, and validation warnings.
- `dataset_card.md`: this human-readable description.

## Current scope

- Original checks: 86
- Mutation samples: 29
- Detected mutations: 29
- Check type: growth-rate consistency only

## Limitations

This is not a complete financial audit dataset. It covers only reported growth-rate consistency in annual key financial metrics tables. Synthetic errors are applied to parsed table JSON, not to PDFs, and no synthetic PDF is generated.

## How to rebuild

```bash
python scripts/parse_pdfs.py --input-dir data/raw_reports/user_offer_01 --table-mode candidate --force
python scripts/run_growth_rate_checks.py --parsed-dir data/parsed_reports
python scripts/generate_growth_rate_mutations.py --parsed-dir data/parsed_reports --output-dir data/mutated_reports --max-mutations-per-report 3 --strategy add_delta --force
python scripts/run_growth_rate_checks.py --parsed-dir data/mutated_reports
python scripts/summarize_batch_results.py --parsed-dir data/parsed_reports --mutated-dir data/mutated_reports --source-dir data/raw_reports/user_offer_01 --output data/batch_reports/user_offer_01_summary.md
python scripts/build_dataset_manifest.py --batch-name user_offer_01 --source-dir data/raw_reports/user_offer_01 --parsed-dir data/parsed_reports --mutated-dir data/mutated_reports --batch-report data/batch_reports/user_offer_01_summary.json --output-dir data/datasets/user_offer_01 --force
```

## Validation

```bash
python -m py_compile scripts/build_dataset_manifest.py src/fri_dataset/*.py
pytest -q
```

Validation warnings:

None.

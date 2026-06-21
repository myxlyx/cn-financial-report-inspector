# Batch Evaluation: user_offer_01

> Deterministic pipeline summary only. This report does not establish financial correctness.

## Batch overview

- Batch name: user_offer_01
- PDF source dir: data/raw_reports/user_offer_01
- Total PDFs found: 10
- Text-based PDFs parsed: 10
- Skipped PDFs: 0
- Parse failed PDFs: 0
- Reports with growth-rate checks: 6
- Reports without growth-rate checks: 4
- Total growth-rate checks: 50
- OK checks: 37
- Mismatch checks: 0
- Review required checks: 0
- Mutations generated: 16
- Mutations validated as detected: 16

## Per-report parse summary

| report_id | source_pdf | pdf_type | page_count | text_pages | tables_count | quality_level | recommended | warnings |
|---|---|---:|---:|---:|---:|---|---|---:|
| 000034_digitalchina_2025_annual_report_fdad6d3c | data/raw_reports/user_offer_01/000034_digitalchina_2025_annual_report.pdf | text_based | 283 | 283 | 20 | good | True | 1 |
| 000926_fuxing_2025_annual_report_79c79b2f | data/raw_reports/user_offer_01/000926_fuxing_2025_annual_report.pdf | text_based | 197 | 196 | 21 | good | True | 1 |
| 000983_shanxijiaomei_2025_annual_report_ba60ae1a | data/raw_reports/user_offer_01/000983_shanxijiaomei_2025_annual_report.pdf | text_based | 254 | 253 | 19 | good | True | 1 |
| 300277_hailianxun_2025_annual_report_c2be3488 | data/raw_reports/user_offer_01/300277_hailianxun_2025_annual_report.pdf | text_based | 198 | 198 | 25 | good | True | 1 |
| 600169_taiyuanheavy_2025_annual_report_590e48ac | data/raw_reports/user_offer_01/600169_taiyuanheavy_2025_annual_report.pdf | text_based | 229 | 229 | 8 | good | True | 1 |
| 600965_fucheng_2025_annual_report_be5c235f | data/raw_reports/user_offer_01/600965_fucheng_2025_annual_report.pdf | text_based | 228 | 228 | 9 | good | True | 1 |
| 601212_baiyin_2025_annual_report_2e832fe9 | data/raw_reports/user_offer_01/601212_baiyin_2025_annual_report.pdf | text_based | 281 | 281 | 13 | good | True | 1 |
| 688158_ucloud_2025_annual_report_75aa8f8a | data/raw_reports/user_offer_01/688158_ucloud_2025_annual_report.pdf | text_based | 303 | 303 | 13 | good | True | 1 |
| 688353_huashenglithium_2025_annual_report_9a6f0977 | data/raw_reports/user_offer_01/688353_huashenglithium_2025_annual_report.pdf | text_based | 305 | 305 | 11 | good | True | 1 |
| 871626_weili_2025_annual_report_426cd375 | data/raw_reports/user_offer_01/871626_weili_2025_annual_report.pdf | text_based | 158 | 157 | 20 | good | True | 1 |

## Per-report growth-rate check summary

| report_id | candidate_tables | checks | ok | mismatch | review_required | mapping_failed | not_applicable |
|---|---:|---:|---:|---:|---:|---:|---:|
| 000034_digitalchina_2025_annual_report_fdad6d3c | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| 000926_fuxing_2025_annual_report_79c79b2f | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 000983_shanxijiaomei_2025_annual_report_ba60ae1a | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| 300277_hailianxun_2025_annual_report_c2be3488 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| 600169_taiyuanheavy_2025_annual_report_590e48ac | 2 | 10 | 10 | 0 | 0 | 0 | 0 |
| 600965_fucheng_2025_annual_report_be5c235f | 2 | 10 | 10 | 0 | 0 | 0 | 0 |
| 601212_baiyin_2025_annual_report_2e832fe9 | 2 | 8 | 8 | 0 | 0 | 0 | 0 |
| 688158_ucloud_2025_annual_report_75aa8f8a | 3 | 10 | 5 | 0 | 0 | 0 | 5 |
| 688353_huashenglithium_2025_annual_report_9a6f0977 | 3 | 11 | 3 | 0 | 0 | 0 | 8 |
| 871626_weili_2025_annual_report_426cd375 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |

## Mutation summary

| source_report_id | mutations | detected | undetected | strategies |
|---|---:|---:|---:|---|
| 000034_digitalchina_2025_annual_report_fdad6d3c | 0 | 0 | 0 |  |
| 000926_fuxing_2025_annual_report_79c79b2f | 0 | 0 | 0 |  |
| 000983_shanxijiaomei_2025_annual_report_ba60ae1a | 0 | 0 | 0 |  |
| 300277_hailianxun_2025_annual_report_c2be3488 | 0 | 0 | 0 |  |
| 600169_taiyuanheavy_2025_annual_report_590e48ac | 3 | 3 | 0 | add_delta |
| 600965_fucheng_2025_annual_report_be5c235f | 3 | 3 | 0 | add_delta |
| 601212_baiyin_2025_annual_report_2e832fe9 | 3 | 3 | 0 | add_delta |
| 688158_ucloud_2025_annual_report_75aa8f8a | 3 | 3 | 0 | add_delta |
| 688353_huashenglithium_2025_annual_report_9a6f0977 | 3 | 3 | 0 | add_delta |
| 871626_weili_2025_annual_report_426cd375 | 1 | 1 | 0 | add_delta |

## Problem cases

| report_id | issue | suggestion |
|---|---|---|
| 000034_digitalchina_2025_annual_report_fdad6d3c | no_growth_rate_checks | Need manual inspection: no growth-rate checks generated. |
| 000926_fuxing_2025_annual_report_79c79b2f | no_candidate_table | Need manual inspection: no candidate annual key metrics table found. |
| 000926_fuxing_2025_annual_report_79c79b2f | no_growth_rate_checks | Need manual inspection: no growth-rate checks generated. |
| 000983_shanxijiaomei_2025_annual_report_ba60ae1a | no_growth_rate_checks | Need manual inspection: no growth-rate checks generated. |
| 300277_hailianxun_2025_annual_report_c2be3488 | no_growth_rate_checks | Need manual inspection: no growth-rate checks generated. |

## Suggested next actions

- Need manual inspection: no growth-rate checks generated.
- Need manual inspection: no candidate annual key metrics table found.

"""Placeholder for future financial table classification.

This module is intentionally lightweight for the PDF-processing MVP. The next
stage can classify extracted tables into categories such as balance sheet,
income statement, cash-flow statement, notes, ownership tables, and generic
non-financial tables.

Planned inputs:
- table metadata from ``tables_index.jsonl``
- table rows from each table JSON ``data`` field
- page-level text from ``pages.jsonl``
- title and section candidates produced during table extraction

Planned outputs:
- ``table_type``
- ``confidence``
- ``classification_reason``

The current project scope stops before complex classification, RAG, Agent
workflows, law knowledge graphs, or financial error detection.
"""


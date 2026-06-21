"""Parse financial table cells without using binary floating point."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fri_checks.schema import NumberParseResult

NON_APPLICABLE_MARKERS = {
    "",
    "-",
    "--",
    "---",
    "—",
    "–",
    "不适用",
    "无",
    "n/a",
    "na",
}


def parse_financial_number(raw: object) -> NumberParseResult:
    raw_text = "" if raw is None else str(raw)
    text = "".join(raw_text.strip().split())
    marker = text.lower()
    if marker in NON_APPLICABLE_MARKERS:
        return NumberParseResult(
            raw=raw_text,
            value=None,
            status="not_applicable",
            notes=["non_applicable_marker"],
        )

    notes: list[str] = []
    is_negative_parentheses = (
        len(text) >= 2
        and text[0] in {"(", "（"}
        and text[-1] in {")",
            "）",
        }
    )
    if is_negative_parentheses:
        text = text[1:-1].strip()
        notes.append("parentheses_negative")

    is_percent = text.endswith(("%", "％"))
    if is_percent:
        text = text[:-1].strip()
        notes.append("percent_sign_stripped")

    normalized = (
        text.replace(",", "")
        .replace("，", "")
        .replace("−", "-")
        .replace("﹣", "-")
    )
    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return NumberParseResult(
            raw=raw_text,
            value=None,
            status="parse_failed",
            is_percent=is_percent,
            notes=notes + ["invalid_number"],
        )

    if not value.is_finite():
        return NumberParseResult(
            raw=raw_text,
            value=None,
            status="parse_failed",
            is_percent=is_percent,
            notes=notes + ["non_finite_number"],
        )

    if is_negative_parentheses:
        value = -abs(value)

    return NumberParseResult(
        raw=raw_text,
        value=value,
        status="ok",
        is_percent=is_percent,
        notes=notes,
    )

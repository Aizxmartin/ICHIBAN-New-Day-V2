from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ReportQualityResult:
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


REQUIRED_TARZAN_TERMS = [
    "subject",
    "comparable",
    "adjust",
    "range",
    "momentum",
    "absorption",
    "concession",
    "1004mc",
    "verification",
]

FORBIDDEN_TARZAN_LEAKS = [
    "PART 1 — BBC SELLER REPORT",
    "BBC Seller Report",
    "Seller Point",
    "ICHIBAN RETROSPECT",
    "Standalone After-Active Review",
]


def validate_tarzan_report(markdown: str) -> ReportQualityResult:
    text = markdown or ""
    low = text.lower()
    errors: List[str] = []
    warnings: List[str] = []
    if len(text.strip()) < 2500:
        errors.append("Tarzan report is too thin for valuation support.")
    for term in REQUIRED_TARZAN_TERMS:
        if term not in low:
            errors.append(f"Missing required Tarzan concept: {term}")
    for leak in FORBIDDEN_TARZAN_LEAKS:
        if leak.lower() in low:
            errors.append(f"Tarzan-only branch leaked paused report language: {leak}")
    valid_statuses = ["confirmed", "qualified", "incomplete", "human review required"]
    if not any(status in low for status in valid_statuses):
        errors.append("Missing final Tarzan status: CONFIRMED, QUALIFIED, INCOMPLETE, or HUMAN REVIEW REQUIRED.")
    return ReportQualityResult(passed=not errors, errors=errors, warnings=warnings)

"""
ICHIBAN INSIGHT - Subject Acquisition Layer

This layer runs AFTER document diagnostics.
It should receive only files that have already been classified and routed.
"""

from .realist_pdf_coordinate_parser import parse_realist_subject

from .subject_verification_store import (
    save_verified_subject,
    load_verified_subject,
    subject_is_verified,
    clear_verified_subject,
)

__all__ = [
    "parse_realist_subject",
    "save_verified_subject",
    "load_verified_subject",
    "subject_is_verified",
    "clear_verified_subject",
]
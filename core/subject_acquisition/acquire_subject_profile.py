from __future__ import annotations

from typing import BinaryIO

from core.address_subject_profile import blank_subject_profile
from core.subject_acquisition.extract_subject_from_pdf import extract_subject_from_pdf
from core.subject_acquisition.lookup_subject_backup import lookup_subject_backup
from core.subject_acquisition.merge_subject_sources import merge_subject_sources
from core.subject_acquisition.validate_subject_profile import validate_subject_profile



def acquire_subject_profile(
    subject_pdf: BinaryIO | bytes | str | None = None,
    fallback_address: str | None = None,
    manual_patch: dict | None = None,
) -> dict:
    locked = validate_subject_profile(blank_subject_profile(fallback_address or ""))
    result = locked

    if subject_pdf is not None:
        pdf_profile = extract_subject_from_pdf(subject_pdf, fallback_address=fallback_address)
        result = merge_subject_sources(result, pdf_profile, "subject_pdf")
        result["subject_acquisition_status"] = pdf_profile.get("subject_acquisition_status", "pdf_attempted")

    if not result.get("subject_profile_ready"):
        lookup_profile = lookup_subject_backup(result.get("subject_address") or fallback_address)
        result = merge_subject_sources(result, lookup_profile, "backup_lookup")
        if result.get("subject_profile_ready"):
            result["subject_acquisition_status"] = "locked_from_pdf_plus_lookup"

    if manual_patch:
        result = merge_subject_sources(result, manual_patch, "manual_recovery")
        if result.get("subject_profile_ready"):
            result["subject_acquisition_status"] = "locked_from_manual_recovery"

    if not result.get("subject_profile_ready"):
        result["subject_acquisition_status"] = "blocked_missing_required_subject_fields"

    return validate_subject_profile(result)

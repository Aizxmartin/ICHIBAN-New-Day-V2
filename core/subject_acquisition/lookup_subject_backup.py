from __future__ import annotations

from core.address_subject_profile import blank_subject_profile
from core.subject_acquisition.validate_subject_profile import validate_subject_profile



def lookup_subject_backup(address: str | None = None) -> dict:
    """
    Backup lookup placeholder.

    In V2 this is a safe stub so the pipeline has a fixed place to plug in
    Redfin, county/public record, or future API providers without changing the
    orchestration contract.
    """
    profile = blank_subject_profile(address or "")
    profile["subject_acquisition_status"] = "backup_lookup_not_configured"
    profile["source_summary"] = ["backup_lookup_stub"]
    return validate_subject_profile(profile)

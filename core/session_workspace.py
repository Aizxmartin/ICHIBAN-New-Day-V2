from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict


def safe_slug(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80] or fallback


def workspace_root() -> Path:
    return Path(os.getenv("ICHIBAN_WORKSPACE_ROOT", "data/workspaces"))


def current_session_id() -> str:
    return os.getenv("ICHIBAN_SESSION_ID", "local")


def current_workspace_dir() -> Path:
    path = workspace_root() / safe_slug(current_session_id(), fallback="local")
    path.mkdir(parents=True, exist_ok=True)
    return path


def subject_identity_from_profile(profile: Dict[str, Any] | None) -> Dict[str, str]:
    profile = profile or {}
    address = (
        profile.get("subject_address")
        or profile.get("address")
        or profile.get("full_address")
        or profile.get("property_address")
        or ""
    )
    city = profile.get("city") or ""
    state = profile.get("state") or profile.get("state_or_province") or ""
    postal_code = profile.get("postal_code") or profile.get("zip") or ""
    display = " ".join(str(x).strip() for x in [address, city, state, postal_code] if str(x or "").strip())
    subject_slug = safe_slug(display or address, fallback="unknown-subject")
    return {
        "subject_address": str(address or ""),
        "city": str(city or ""),
        "state": str(state or ""),
        "postal_code": str(postal_code or ""),
        "subject_display": display,
        "subject_slug": subject_slug,
        "session_id": current_session_id(),
    }


def subject_run_id(profile: Dict[str, Any] | None) -> str:
    identity = subject_identity_from_profile(profile)
    slug = identity.get("subject_slug") or "unknown-subject"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def scoped_data_path(filename: str) -> Path:
    return current_workspace_dir() / filename

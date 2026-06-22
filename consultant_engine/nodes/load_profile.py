import re

from consultant_engine.state import ConsultantState

MIDPOINT = {"Conservative": 3.5, "Moderate": 5.0,
            "Moderately Aggressive": 7.0, "Aggressive": 9.0}
CEILING = {"Conservative": 4.0, "Moderate": 6.0,
           "Moderately Aggressive": 8.0, "Aggressive": 10.0}

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_NAME_LEN = 100


def _normalize_client_name(raw) -> str:
    """Normalize a raw client_name into a render- and filename-safe string.

    Collapses every run of whitespace (spaces, tabs, newlines) to a single
    space and trims the ends, strips residual control characters, and caps the
    length at ``_MAX_NAME_LEN``. A missing, non-string, or all-whitespace value
    normalizes to ``""`` — the generic sentinel.

    Args:
        raw: The raw ``client_name`` from the profile (any type).

    Returns:
        The cleaned name, or ``""`` when absent/blank/non-string.
    """
    if not isinstance(raw, str):
        return ""
    collapsed = " ".join(raw.split())          # trim + collapse all whitespace runs
    cleaned = _CONTROL_CHARS_RE.sub("", collapsed)
    return cleaned[:_MAX_NAME_LEN]


def load_profile(state: ConsultantState) -> dict:
    """load_profile node: normalise the client profile and flag unrealistic targets.

    Fills defaults (experience tier, and target return = profile MIDPOINT when
    absent) and sets target_note when the target return exceeds the profile's
    realistic CEILING. Returns {"client_profile": {...}} (the normalised copy).
    """
    p = dict(state["client_profile"])
    profile_risk_level = p["risk_level"]
    p.setdefault("experience", "experienced")   # normalize the tier into the profile (single owner)
    p["client_name"] = _normalize_client_name(p.get("client_name"))
    p.setdefault("target_annual_return_pct", MIDPOINT[profile_risk_level])
    note = ""
    if p["target_annual_return_pct"] > CEILING[profile_risk_level]:
        note = (f"Target {p['target_annual_return_pct']}% p.a. exceeds the realistic ceiling "
                f"for a {profile_risk_level} profile ({CEILING[profile_risk_level]}%).")
    p["target_note"] = note
    return {"client_profile": p}

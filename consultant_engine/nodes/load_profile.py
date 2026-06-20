from consultant_engine.state import ConsultantState

MIDPOINT = {"Conservative": 3.5, "Moderate": 5.0,
            "Moderately Aggressive": 7.0, "Aggressive": 9.0}
CEILING = {"Conservative": 4.0, "Moderate": 6.0,
           "Moderately Aggressive": 8.0, "Aggressive": 10.0}

def load_profile(state: ConsultantState) -> dict:
    """load_profile node: normalise the client profile and flag unrealistic targets.

    Fills defaults (experience tier, and target return = profile MIDPOINT when
    absent) and sets target_note when the target return exceeds the profile's
    realistic CEILING. Returns {"client_profile": {...}} (the normalised copy).
    """
    p = dict(state["client_profile"])
    profile_risk_level = p["risk_level"]
    p.setdefault("experience", "experienced")   # normalize the tier into the profile (single owner)
    p.setdefault("target_annual_return_pct", MIDPOINT[profile_risk_level])
    note = ""
    if p["target_annual_return_pct"] > CEILING[profile_risk_level]:
        note = (f"Target {p['target_annual_return_pct']}% p.a. exceeds the realistic ceiling "
                f"for a {profile_risk_level} profile ({CEILING[profile_risk_level]}%).")
    p["target_note"] = note
    return {"client_profile": p}

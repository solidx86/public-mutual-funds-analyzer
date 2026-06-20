from consultant_engine.state import ConsultantState

MIDPOINT = {"Conservative": 3.5, "Moderate": 5.0,
            "Moderately Aggressive": 7.0, "Aggressive": 9.0}
CEILING = {"Conservative": 4.0, "Moderate": 6.0,
           "Moderately Aggressive": 8.0, "Aggressive": 10.0}

def load_profile(state: ConsultantState) -> dict:
    p = dict(state.get("client_profile", {}))
    # Handle empty/stub case (return as-is for skeleton testing)
    if not p or "risk_level" not in p:
        return {"client_profile": p}

    rl = p["risk_level"]
    p.setdefault("experience", "experienced")   # normalize the tier into the profile (single owner)
    p.setdefault("e_target", MIDPOINT[rl])
    note = ""
    if p["e_target"] > CEILING[rl]:
        note = (f"Target {p['e_target']}% p.a. exceeds the realistic ceiling "
                f"for a {rl} profile ({CEILING[rl]}%).")
    p["target_note"] = note
    return {"client_profile": p}

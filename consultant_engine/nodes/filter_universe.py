from consultant_engine.state import ConsultantState

# Risk-level ceiling map per client profile risk level
RISK_CEILING = {
    "Conservative": 2,
    "Moderate": 3,
    "Moderately Aggressive": 4,
    "Aggressive": 5,
}


def filter_universe(state: ConsultantState) -> dict:
    """Filter eligible_funds by Shariah preference and risk-level ceiling.

    Shariah logic:
    - None: no Shariah filter (keep both compliant and conventional)
    - True: keep only Shariah-compliant funds
    - False: keep only conventional funds (exclude Shariah-compliant)

    Risk-level ceiling: keep funds with risk_level <= ceiling[profile_risk_level]

    Args:
        state: ConsultantState with eligible_funds and client_profile

    Returns:
        dict with filtered_funds list
    """
    eligible_funds = state.get("eligible_funds", [])
    client_profile = state.get("client_profile", {})

    shariah_pref = client_profile.get("shariah")
    # risk_level is a required, normalized field by the time this node runs
    # (load_profile guarantees it) — fail loud rather than guess the client's risk.
    ceiling = RISK_CEILING[client_profile["risk_level"]]

    filtered_funds = []
    for fund in eligible_funds:
        # Apply Shariah filter
        if shariah_pref is not None:
            fund_shariah = fund.get("shariah", False)
            if shariah_pref is True:
                # Keep only Shariah-compliant
                if not fund_shariah:
                    continue
            elif shariah_pref is False:
                # Keep only conventional (exclude Shariah-compliant)
                if fund_shariah:
                    continue

        # Apply risk-level ceiling. A fund with an unknown risk level (None) is
        # excluded rather than silently admitted — we never recommend a fund whose
        # risk we can't place.
        fund_risk_level = fund.get("risk_level")
        if fund_risk_level is None or fund_risk_level > ceiling:
            continue

        filtered_funds.append(fund)

    return {"filtered_funds": filtered_funds}

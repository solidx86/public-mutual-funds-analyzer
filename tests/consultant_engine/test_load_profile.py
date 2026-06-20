from consultant_engine.nodes.load_profile import load_profile


def test_experience_normalized_and_default_target():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000}})
    assert out["client_profile"]["experience"] == "new"      # profile is the sole owner of the tier
    assert out["client_profile"]["target_annual_return_pct"] == 5.0          # midpoint default


def test_experience_defaults_to_experienced_when_absent():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "shariah": None, "upfront_capital_rm": 5000}})
    assert out["client_profile"]["experience"] == "experienced"


def test_target_mismatch_note():
    out = load_profile({"client_profile": {
        "risk_level": "Conservative", "experience": "experienced",
        "shariah": None, "upfront_capital_rm": 100000, "target_annual_return_pct": 9.0}})
    assert "exceeds" in out["client_profile"]["target_note"].lower()

from consultant_engine.state import ConsultantState, ClientProfile

def test_state_is_constructable_with_partial_keys():
    # TypedDict total=False → partial construction is legal at runtime
    s: ConsultantState = {"thread_id": "t1", "repair_iterations": 0}
    assert s["thread_id"] == "t1"

def test_client_profile_keys():
    p: ClientProfile = {
        "risk_level": "Moderate", "shariah": False, "experience": "experienced",
        "upfront_capital_rm": 50000.0, "target_annual_return_pct": 5.0, "goals": None,
    }
    assert p["risk_level"] == "Moderate"

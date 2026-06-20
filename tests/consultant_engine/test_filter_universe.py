from consultant_engine.nodes.filter_universe import filter_universe

FUNDS = [
    {"abbr": "A", "shariah": True,  "risk_level": 2},
    {"abbr": "B", "shariah": False, "risk_level": 4},
    {"abbr": "C", "shariah": True,  "risk_level": 3},
]


def test_shariah_true_and_ceiling():
    """When shariah=True, keep only Shariah-compliant funds within RL ceiling."""
    out = filter_universe({
        "eligible_funds": FUNDS,
        "client_profile": {"risk_level": "Moderate", "shariah": True}
    })
    # Moderate ceiling: 3. shariah=True means only A and C qualify.
    # A (shariah=True, RL=2) ✓, B (shariah=False) ✗, C (shariah=True, RL=3) ✓
    assert {f["abbr"] for f in out["filtered_funds"]} == {"A", "C"}


def test_shariah_none_and_ceiling():
    """When shariah=None, keep both Shariah and conventional within RL ceiling."""
    out = filter_universe({
        "eligible_funds": FUNDS,
        "client_profile": {"risk_level": "Moderate", "shariah": None}
    })
    # Moderate ceiling: 3. No shariah filter means A, B (RL too high), C all candidates.
    # A (RL=2) ✓, B (RL=4) ✗, C (RL=3) ✓
    assert {f["abbr"] for f in out["filtered_funds"]} == {"A", "C"}


def test_shariah_false_and_ceiling():
    """When shariah=False, exclude Shariah-compliant; keep only conventional within RL ceiling."""
    out = filter_universe({
        "eligible_funds": FUNDS,
        "client_profile": {"risk_level": "Moderate", "shariah": False}
    })
    # Moderate ceiling: 3. shariah=False means exclude A and C (Shariah-compliant).
    # A (shariah=True) ✗, B (shariah=False, RL=4) ✗, C (shariah=True) ✗
    assert {f["abbr"] for f in out["filtered_funds"]} == set()


def test_aggressive_ceiling():
    """Test with Aggressive risk level (ceiling=5)."""
    out = filter_universe({
        "eligible_funds": FUNDS,
        "client_profile": {"risk_level": "Aggressive", "shariah": True}
    })
    # Aggressive ceiling: 5. shariah=True means A and C (no B).
    # A (shariah=True, RL=2) ✓, B (shariah=False) ✗, C (shariah=True, RL=3) ✓
    assert {f["abbr"] for f in out["filtered_funds"]} == {"A", "C"}


def test_conservative_ceiling():
    """Test with Conservative risk level (ceiling=2)."""
    out = filter_universe({
        "eligible_funds": FUNDS,
        "client_profile": {"risk_level": "Conservative", "shariah": True}
    })
    # Conservative ceiling: 2. shariah=True means A and C, but only A is within RL 2.
    # A (shariah=True, RL=2) ✓, B (shariah=False) ✗, C (shariah=True, RL=3) ✗
    assert {f["abbr"] for f in out["filtered_funds"]} == {"A"}

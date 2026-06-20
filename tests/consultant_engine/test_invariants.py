from consultant_engine.invariants import check_invariants

PORT = [
    {"abbr": "PIX", "role": "core", "allocation_pct": 60},
    {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
    {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10},
    {"abbr": "PeDiv", "role": "core", "allocation_pct": 20},
]
UNIVERSE = {"PIX", "PeEMAS", "PeCDF-A", "PeDiv"}


def test_concentration_violation():
    v = check_invariants(PORT, "Moderate", UNIVERSE, rl_by_abbr={a: 3 for a in UNIVERSE})
    assert any("cap" in x["msg"].lower() for x in v)     # PIX 60 > 50 cap


def test_clean_portfolio_has_no_violations():
    clean = [{"abbr": "PIX", "role": "core", "allocation_pct": 40},
             {"abbr": "PeDiv", "role": "core", "allocation_pct": 40},
             {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
             {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10}]
    v = check_invariants(clean, "Moderate", UNIVERSE, rl_by_abbr={a: 3 for a in UNIVERSE})
    assert v == []


def test_count_violation_three_funds():
    """A 3-fund portfolio fires the count check."""
    three = [
        {"abbr": "PIX", "role": "core", "allocation_pct": 40},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 30},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 30},
    ]
    universe = {"PIX", "PeEMAS", "PeCDF-A"}
    v = check_invariants(three, "Moderate", universe, rl_by_abbr={a: 3 for a in universe})
    codes = [x["code"] for x in v]
    assert "count" in codes


def test_structural_violation_missing_money_market():
    """A portfolio missing the money-market structural fires the structural check."""
    no_mm = [
        {"abbr": "PIX", "role": "core", "allocation_pct": 40},
        {"abbr": "PeDiv", "role": "core", "allocation_pct": 40},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "EXTRA", "role": "core", "allocation_pct": 10},
    ]
    universe = {"PIX", "PeDiv", "PeEMAS", "EXTRA"}
    v = check_invariants(no_mm, "Moderate", universe, rl_by_abbr={a: 3 for a in universe})
    codes = [x["code"] for x in v]
    assert "structural" in codes


def test_rl_ceiling_violation_for_core_role():
    """A core fund with RL above the ceiling fires rl_ceiling."""
    # Moderate ceiling = 3; use RL=4 for PIX
    clean_alloc = [
        {"abbr": "PIX", "role": "core", "allocation_pct": 40},
        {"abbr": "PeDiv", "role": "core", "allocation_pct": 40},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10},
    ]
    rl = {a: 3 for a in UNIVERSE}
    rl["PIX"] = 4  # exceeds Moderate ceiling of 3
    v = check_invariants(clean_alloc, "Moderate", UNIVERSE, rl_by_abbr=rl)
    codes = [x["code"] for x in v]
    assert "rl_ceiling" in codes


def test_rl_ceiling_satellite_exception():
    """A satellite fund exceeding the ceiling must NOT fire rl_ceiling (Step 4d exception)."""
    clean_alloc = [
        {"abbr": "PIX", "role": "satellite", "allocation_pct": 40},
        {"abbr": "PeDiv", "role": "core", "allocation_pct": 40},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10},
    ]
    rl = {a: 3 for a in UNIVERSE}
    rl["PIX"] = 5  # well above Moderate ceiling of 3, but role is satellite
    v = check_invariants(clean_alloc, "Moderate", UNIVERSE, rl_by_abbr=rl)
    codes = [x["code"] for x in v]
    assert "rl_ceiling" not in codes


def test_rl_ceiling_structural_gold_exempt():
    """A structural:gold holding above the profile RL ceiling must NOT fire rl_ceiling.

    Gold (PeEMAS) is always included regardless of profile risk level — it is a
    structural hedge, not a risk-scaled pick.  Conservative ceiling = 2; PeEMAS RL 3
    must be exempt.
    """
    port = [
        {"abbr": "LOWA", "role": "core", "allocation_pct": 40},
        {"abbr": "LOWB", "role": "core", "allocation_pct": 40},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10},
    ]
    universe = {"LOWA", "LOWB", "PeEMAS", "PeCDF-A"}
    rl = {"LOWA": 2, "LOWB": 2, "PeEMAS": 3, "PeCDF-A": 1}
    # Conservative ceiling is 2; PeEMAS is RL 3 — must NOT produce rl_ceiling violation
    v = check_invariants(port, "Conservative", universe, rl_by_abbr=rl)
    codes = [x["code"] for x in v]
    assert "rl_ceiling" not in codes


def test_rl_ceiling_structural_money_market_exempt():
    """A structural:money_market holding above the profile RL ceiling must NOT fire rl_ceiling."""
    port = [
        {"abbr": "LOWA", "role": "core", "allocation_pct": 40},
        {"abbr": "LOWB", "role": "core", "allocation_pct": 40},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10},
    ]
    universe = {"LOWA", "LOWB", "PeEMAS", "PeCDF-A"}
    # Hypothetical: MM fund assigned RL 3 while Conservative ceiling is 2
    rl = {"LOWA": 2, "LOWB": 2, "PeEMAS": 2, "PeCDF-A": 3}
    v = check_invariants(port, "Conservative", universe, rl_by_abbr=rl)
    codes = [x["code"] for x in v]
    assert "rl_ceiling" not in codes


def test_sum_violation():
    """Portfolio summing to ≠ 100 fires the sum check."""
    bad_sum = [
        {"abbr": "PIX", "role": "core", "allocation_pct": 30},
        {"abbr": "PeDiv", "role": "core", "allocation_pct": 30},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10},
    ]
    v = check_invariants(bad_sum, "Moderate", UNIVERSE, rl_by_abbr={a: 3 for a in UNIVERSE})
    codes = [x["code"] for x in v]
    assert "sum" in codes


def test_universe_violation():
    """A fund not in the universe fires the universe check."""
    with_outsider = [
        {"abbr": "PIX", "role": "core", "allocation_pct": 30},
        {"abbr": "PeDiv", "role": "core", "allocation_pct": 30},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 20},
        {"abbr": "UNKNOWN", "role": "structural:money_market", "allocation_pct": 20},
    ]
    v = check_invariants(with_outsider, "Moderate", UNIVERSE, rl_by_abbr={"PIX": 3, "PeDiv": 3, "PeEMAS": 3, "UNKNOWN": 3})
    codes = [x["code"] for x in v]
    assert "universe" in codes

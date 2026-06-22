from consultant_engine.portfolio import build, dedup_overlap
from consultant_engine.invariants import CAP, check_invariants


def test_structural_always_present_and_sums_100():
    scores = [{"abbr": f"E{i}", "composite": 90 - i, "derived_class": "Equity-equivalent",
               "alpha_n": 50} for i in range(6)]
    port = build(scores, "Moderate", shariah=None)
    roles = {h["role"] for h in port}
    assert "structural:gold" in roles and "structural:money_market" in roles
    assert len(port) == 4                                      # gold + MM + 2 core, always
    assert round(sum(h["allocation_pct"] for h in port)) == 100


def test_core_picks_are_top_two_by_composite_cfs_proportional():
    """Top-2 by composite are picked as core; higher composite gets >= allocation."""
    scores = [{"abbr": f"E{i}", "composite": 90 - i, "derived_class": "Equity-equivalent",
               "alpha_n": 50} for i in range(6)]
    port = build(scores, "Moderate", shariah=None)

    core_holdings = [h for h in port if h["role"] == "core"]
    assert len(core_holdings) == 2

    core_abbrs = {h["abbr"] for h in core_holdings}
    assert core_abbrs == {"E0", "E1"}

    # E0 has composite 90, E1 has composite 89 — E0 should get >= allocation
    e0 = next(h for h in core_holdings if h["abbr"] == "E0")
    e1 = next(h for h in core_holdings if h["abbr"] == "E1")
    assert e0["allocation_pct"] >= e1["allocation_pct"]

    # Must sum to exactly 100.0
    assert sum(h["allocation_pct"] for h in port) == 100.0


def test_shariah_true_uses_pimmf_a_mm_and_gold_is_peemas():
    """shariah=True → MM abbr is PIMMF-A; gold is still PeEMAS; four pct sum to 100.0."""
    scores = [{"abbr": f"E{i}", "composite": 80 - i * 2, "derived_class": "Equity-equivalent",
               "alpha_n": 40} for i in range(4)]

    port = build(scores, "Aggressive", shariah=True)

    mm_holding = next(h for h in port if h["role"] == "structural:money_market")
    gold_holding = next(h for h in port if h["role"] == "structural:gold")

    assert mm_holding["abbr"] == "PIMMF-A"
    assert gold_holding["abbr"] == "PeEMAS"

    assert len(port) == 4
    assert sum(h["allocation_pct"] for h in port) == 100.0


def test_overlap_drops_lower_alpha():
    """If two picks share >=3 of top-5 holdings, drop the lower-alpha one."""
    picks = [
        {"abbr": "A", "alpha_n": 80, "top5_holdings": ["x", "y", "z", "p", "q"]},
        {"abbr": "B", "alpha_n": 60, "top5_holdings": ["x", "y", "z", "m", "n"]},
    ]  # shares x,y,z (3 items)
    kept = dedup_overlap(picks)
    assert [p["abbr"] for p in kept] == ["A"]


def test_overlap_preserves_non_overlapping_and_order():
    """Three picks: overlapping pair drops lower-alpha, non-overlapping third kept in order."""
    picks = [
        {"abbr": "A", "alpha_n": 80, "top5_holdings": ["x", "y", "z", "p", "q"]},
        {"abbr": "B", "alpha_n": 60, "top5_holdings": ["x", "y", "z", "m", "n"]},  # overlaps A, lower alpha
        {"abbr": "C", "alpha_n": 70, "top5_holdings": ["a", "b", "c", "d", "e"]},  # no overlap
    ]
    kept = dedup_overlap(picks)
    abbrs = [p["abbr"] for p in kept]
    assert abbrs == ["A", "C"]


def test_build_carries_alpha_n_on_cores_only():
    scores = [
        {"abbr": "HIA", "composite": 90.0, "alpha_n": 95},
        {"abbr": "LOA", "composite": 80.0, "alpha_n": 40},
    ]
    port = build(scores, "Moderate", shariah=False)
    cores = [h for h in port if h["role"] == "core"]
    structurals = [h for h in port if h["role"].startswith("structural")]
    assert {h["abbr"]: h["alpha_n"] for h in cores} == {"HIA": 95, "LOA": 40}
    assert all("alpha_n" not in h for h in structurals)


# ---------------------------------------------------------------------------
# exposure_gap_pick tests
# ---------------------------------------------------------------------------
from consultant_engine.portfolio import exposure_gap_pick


def test_build_then_exposure_gap_replaces_true_lowest_alpha_core():
    # HIA: highest composite AND highest alpha_n -> list-first.
    # LOA: lower composite AND lowest alpha_n  -> the one that SHOULD be replaced.
    scores = [
        {"abbr": "HIA", "composite": 90.0, "alpha_n": 95},
        {"abbr": "LOA", "composite": 80.0, "alpha_n": 40},
    ]
    port = build(scores, "Moderate", shariah=False)
    candidate = {"abbr": "GAP", "returns": {"3y": {"alpha": 1.0}}}
    out = exposure_gap_pick(port, candidates=[candidate], gaps=["china"], profile="Moderate")
    abbrs = [h["abbr"] for h in out]
    assert "GAP" in abbrs                # the gap pick was substituted in
    assert "LOA" not in abbrs            # the LOWEST-alpha core was the one replaced
    assert "HIA" in abbrs                # the higher-alpha core survived

CAND = [{"abbr": "PUSEQ", "returns": {"3y": {"alpha": 1.5}}, "fund_type": "Equity"}]
CORE = [{"abbr": "PIX", "role": "core", "allocation_pct": 45, "alpha_n": 70},
        {"abbr": "PLO", "role": "core", "allocation_pct": 35, "alpha_n": 30},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10}]


def test_gap_pick_substitutes_lowest_alpha_core_capped_15():
    out = exposure_gap_pick(CORE, candidates=CAND, gaps=["US equity"], profile="Moderate")
    abbrs = {h["abbr"] for h in out}
    assert "PUSEQ" in abbrs and "PLO" not in abbrs           # replaced the lower-alpha core slot
    assert len(out) == 4 and round(sum(h["allocation_pct"] for h in out)) == 100
    assert next(h for h in out if h["abbr"] == "PUSEQ")["allocation_pct"] <= 15


def test_no_gap_returns_portfolio_unchanged():
    assert exposure_gap_pick(CORE, CAND, gaps=[], profile="Moderate") == CORE


def test_skip_when_satellite_present():
    with_sat = CORE + [{"abbr": "STAR", "role": "satellite", "allocation_pct": 8}]
    assert exposure_gap_pick(with_sat, CAND, gaps=["US equity"], profile="Moderate") == with_sat


def test_exposure_gap_role_and_negative_alpha_rejected():
    """Substituted holding has role 'exposure_gap'; negative-alpha candidate → no-op."""
    out = exposure_gap_pick(CORE, candidates=CAND, gaps=["US equity"], profile="Moderate")
    gap_holding = next(h for h in out if h["abbr"] == "PUSEQ")
    assert gap_holding["role"] == "exposure_gap"

    # Candidate with negative 3Y alpha must be rejected → portfolio unchanged
    bad_cand = [{"abbr": "PBAD", "returns": {"3y": {"alpha": -0.5}}, "fund_type": "Equity"}]
    assert exposure_gap_pick(CORE, bad_cand, gaps=["US equity"], profile="Moderate") == CORE


def test_exact_100_sum_after_redistribution():
    """After substitution the allocation_pct sum is exactly 100.0 (not just rounded)."""
    out = exposure_gap_pick(CORE, candidates=CAND, gaps=["US equity"], profile="Moderate")
    assert sum(h["allocation_pct"] for h in out) == 100.0


# ---------------------------------------------------------------------------
# alpha_outlier tests
# ---------------------------------------------------------------------------
from consultant_engine.portfolio import alpha_outlier


def test_outlier_substitutes_lowest_alpha_core():
    portfolio = [{"abbr": "CORE_HI", "role": "core", "allocation_pct": 45, "alpha_n": 70},
                 {"abbr": "CORE_LO", "role": "core", "allocation_pct": 35, "alpha_n": 40},
                 {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
                 {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10}]
    scores = [{"abbr": "STAR", "composite": 99, "alpha_n": 95, "derived_class": "Equity-equivalent"}]
    funds = {"STAR": {"abbr": "STAR", "status": "Qualified", "shariah": False,
                      "risk_level": 5, "top5_holdings": [], "returns": {"3y": {"alpha": 9.0}, "5y": {"alpha": 7.0}}}}
    out = alpha_outlier(portfolio, scores, funds, "Moderate", shariah=None)
    abbrs = {h["abbr"] for h in out}
    assert "STAR" in abbrs and "CORE_LO" not in abbrs        # took the lowest-alpha core's slot
    assert next(h for h in out if h["abbr"] == "STAR")["role"] == "satellite"
    assert len(out) == 4 and round(sum(h["allocation_pct"] for h in out)) == 100


def test_aggressive_skips_outlier():
    assert alpha_outlier([], [], {}, "Aggressive", None) == []


def test_outlier_gate_a2_fails_below_80():
    """Candidate with alpha_n=60 (< 80) must not be swapped in."""
    portfolio = [{"abbr": "CORE_HI", "role": "core", "allocation_pct": 45, "alpha_n": 70},
                 {"abbr": "CORE_LO", "role": "core", "allocation_pct": 35, "alpha_n": 40},
                 {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
                 {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10}]
    scores = [{"abbr": "WEAK", "composite": 99, "alpha_n": 60, "derived_class": "Equity-equivalent"}]
    funds = {"WEAK": {"abbr": "WEAK", "status": "Qualified", "shariah": False,
                      "risk_level": 4, "top5_holdings": [], "returns": {"3y": {"alpha": 8.0}}}}
    out = alpha_outlier(portfolio, scores, funds, "Moderate", shariah=None)
    # portfolio unchanged — gate A2 blocked
    assert out is portfolio


def test_outlier_gate_a_fails_non_positive_3y_alpha():
    """Candidate with 3Y alpha <= 0 must not be swapped in."""
    portfolio = [{"abbr": "CORE_HI", "role": "core", "allocation_pct": 45, "alpha_n": 70},
                 {"abbr": "CORE_LO", "role": "core", "allocation_pct": 35, "alpha_n": 40},
                 {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
                 {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10}]
    scores = [{"abbr": "FLAT", "composite": 99, "alpha_n": 90, "derived_class": "Equity-equivalent"}]
    funds = {"FLAT": {"abbr": "FLAT", "status": "Qualified", "shariah": False,
                      "risk_level": 4, "top5_holdings": [], "returns": {"3y": {"alpha": 0.0}}}}
    out = alpha_outlier(portfolio, scores, funds, "Moderate", shariah=None)
    # portfolio unchanged — gate A blocked (3Y alpha = 0 is not > 0)
    assert out is portfolio


# ---------------------------------------------------------------------------
# concentration-cap clamp tests (Task 1)
# ---------------------------------------------------------------------------


def test_build_clamps_skewed_core_to_cap_moderate():
    # Composites ~95/5 → naive CFS-proportional split puts core A at ~70% of the
    # 63.5 core budget, i.e. >50 (the Moderate cap). build() must clamp & spill.
    scores = [
        {"abbr": "BIG", "composite": 95.0, "alpha_n": 90},
        {"abbr": "SMALL", "composite": 5.0, "alpha_n": 30},
    ]
    port = build(scores, "Moderate", shariah=False)
    cap = CAP["Moderate"]
    assert all(h["allocation_pct"] <= cap for h in port), port
    assert sum(h["allocation_pct"] for h in port) == 100.0
    # Smoke check that the clamped portfolio is invariant-clean by construction.
    # RL here is a uniform 3 (== the Moderate ceiling), so this asserts the cap and
    # sum branches, not the RL-ceiling branch. RL-ceiling enforcement (core
    # violation plus the satellite/gold/money-market exemptions) has dedicated
    # coverage in test_invariants.py; it is intentionally not re-tested here.
    universe = {h["abbr"] for h in port}
    rl = {h["abbr"]: 3 for h in port}
    assert check_invariants(port, "Moderate", universe, rl) == []


def test_gap_pick_clamps_surviving_core_to_cap():
    # Surviving core inherits freed share and would exceed the Conservative cap (50);
    # the redistribution must clamp it and spill to structurals.
    core = [
        {"abbr": "BIG", "role": "core", "allocation_pct": 48.0, "alpha_n": 70},
        {"abbr": "LO", "role": "core", "allocation_pct": 25.0, "alpha_n": 20},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 17.0},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10.0},
    ]
    cand = [{"abbr": "GAP", "returns": {"3y": {"alpha": 1.0}}}]
    out = exposure_gap_pick(core, candidates=cand, gaps=["china"], profile="Conservative")
    cap = CAP["Conservative"]
    assert all(h["allocation_pct"] <= cap for h in out), out
    assert sum(h["allocation_pct"] for h in out) == 100.0

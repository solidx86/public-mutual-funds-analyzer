from consultant_engine.portfolio import build, dedup_overlap


def test_structural_always_present_and_sums_100():
    scores = [{"abbr": f"E{i}", "composite": 90 - i, "derived_class": "Equity-equivalent",
               "alpha_n": 50} for i in range(6)]
    funds = {f"E{i}": {"abbr": f"E{i}", "fund_type": "Equity", "risk_level": 3,
                       "top5": [], "shariah": False} for i in range(6)}
    funds["PeEMAS"] = {"abbr": "PeEMAS", "fund_type": "Gold", "risk_level": 3, "top5": []}
    funds["PeCDF-A"] = {"abbr": "PeCDF-A", "fund_type": "Money Market", "risk_level": 1, "top5": []}
    port = build(scores, funds, "Moderate", shariah=None)
    roles = {h["role"] for h in port}
    assert "structural:gold" in roles and "structural:money_market" in roles
    assert len(port) == 4                                      # gold + MM + 2 core, always
    assert round(sum(h["allocation_pct"] for h in port)) == 100


def test_core_picks_are_top_two_by_composite_cfs_proportional():
    """Top-2 by composite are picked as core; higher composite gets >= allocation."""
    scores = [{"abbr": f"E{i}", "composite": 90 - i, "derived_class": "Equity-equivalent",
               "alpha_n": 50} for i in range(6)]
    funds = {f"E{i}": {"abbr": f"E{i}", "fund_type": "Equity", "risk_level": 3,
                       "top5": [], "shariah": False} for i in range(6)}
    funds["PeEMAS"] = {"abbr": "PeEMAS", "fund_type": "Gold", "risk_level": 3, "top5": []}
    funds["PeCDF-A"] = {"abbr": "PeCDF-A", "fund_type": "Money Market", "risk_level": 1, "top5": []}
    port = build(scores, funds, "Moderate", shariah=None)

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
    funds = {f"E{i}": {"abbr": f"E{i}", "fund_type": "Equity", "risk_level": 3,
                       "top5": [], "shariah": True} for i in range(4)}
    funds["PeEMAS"] = {"abbr": "PeEMAS", "fund_type": "Gold", "risk_level": 3, "top5": []}
    funds["PIMMF-A"] = {"abbr": "PIMMF-A", "fund_type": "Money Market", "risk_level": 1, "top5": []}

    port = build(scores, funds, "Aggressive", shariah=True)

    mm_holding = next(h for h in port if h["role"] == "structural:money_market")
    gold_holding = next(h for h in port if h["role"] == "structural:gold")

    assert mm_holding["abbr"] == "PIMMF-A"
    assert gold_holding["abbr"] == "PeEMAS"

    assert len(port) == 4
    assert sum(h["allocation_pct"] for h in port) == 100.0


def test_overlap_drops_lower_alpha():
    """If two picks share >=3 of top-5 holdings, drop the lower-alpha one."""
    picks = [
        {"abbr": "A", "alpha_n": 80, "top5": ["x", "y", "z", "p", "q"]},
        {"abbr": "B", "alpha_n": 60, "top5": ["x", "y", "z", "m", "n"]},
    ]  # shares x,y,z (3 items)
    kept = dedup_overlap(picks)
    assert [p["abbr"] for p in kept] == ["A"]


def test_overlap_preserves_non_overlapping_and_order():
    """Three picks: overlapping pair drops lower-alpha, non-overlapping third kept in order."""
    picks = [
        {"abbr": "A", "alpha_n": 80, "top5": ["x", "y", "z", "p", "q"]},
        {"abbr": "B", "alpha_n": 60, "top5": ["x", "y", "z", "m", "n"]},  # overlaps A, lower alpha
        {"abbr": "C", "alpha_n": 70, "top5": ["a", "b", "c", "d", "e"]},  # no overlap
    ]
    kept = dedup_overlap(picks)
    abbrs = [p["abbr"] for p in kept]
    assert abbrs == ["A", "C"]


# ---------------------------------------------------------------------------
# exposure_gap_pick tests
# ---------------------------------------------------------------------------
from consultant_engine.portfolio import exposure_gap_pick

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

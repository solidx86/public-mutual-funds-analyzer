"""Unit tests for consultant_engine.evals.figures_extractor.

Builds a small hand-constructed ConsultantState (a plain dict literal — no engine
run, no fixtures, no LLM) and checks that ``extract_figures`` reshapes it into the
figures schema with exactly the values a hand computation predicts, including the
portfolio- and per-derived-class derived aggregates (§4a of the prose-number eval spec).
A purity test confirms the input state is never mutated.
"""

import copy

from consultant_engine.evals.figures_extractor import extract_figures

# ── Hand-built ConsultantState ────────────────────────────────────────────────
# Four holdings: two core equity funds (one Equity-equivalent, one Balanced by
# consultant_engine.cfs.derived_class) plus the two usual structural sleeves
# (gold + money market). Allocation sums to 100. Numbers are chosen so every
# derived aggregate below can be hand-verified without a calculator slip.

_FA = {  # core, Equity-equivalent (dom_equity + for_equity = 80 >= 60)
    "abbr": "FA",
    "name": "Public Alpha Fund",
    "risk_level": 3,
    "weighted_alpha": 6.0,
    "assets": {"dom_equity": 60, "for_equity": 20, "fi": 10, "mm": 5, "deposits": 5, "other": 0},
    "geo": {"USA": 40, "Taiwan": 10},
}

_FB = {  # core, Balanced (equity 50 < 60, defensive 50 < 60)
    "abbr": "FB",
    "name": "Public Balanced Fund",
    "risk_level": 3,
    "weighted_alpha": 2.0,
    "assets": {"dom_equity": 30, "for_equity": 20, "fi": 30, "mm": 10, "deposits": 10, "other": 0},
    "geo": {"USA": 20, "Korea": 15},
}

_PEEMAS = {  # structural gold sleeve
    "abbr": "PeEMAS",
    "name": "Public e-Islamic EMAS",
    "risk_level": 3,
    "weighted_alpha": 0.5,
    "assets": {"dom_equity": 0, "for_equity": 0, "fi": 0, "mm": 0, "deposits": 0, "other": 95},
    "geo": {},
}

_PECDFA = {  # structural money-market sleeve; deliberately negative alpha
    "abbr": "PeCDF-A",
    "name": "Public e-Cash Deposit",
    "risk_level": 1,
    "weighted_alpha": -0.1,
    "assets": {"dom_equity": 0, "for_equity": 0, "fi": 0, "mm": 100, "deposits": 0, "other": 0},
    "geo": {},
}

_ELIGIBLE_FUNDS = [_FA, _FB, _PEEMAS, _PECDFA]

# cfs_scores mirrors score_all's output shape/order (already sorted desc by composite).
_CFS_SCORES = [
    {"abbr": "FA", "composite": 70, "derived_class": "Equity-equivalent"},
    {"abbr": "FB", "composite": 50, "derived_class": "Balanced"},
    {"abbr": "PeEMAS", "composite": 10, "derived_class": "Balanced"},
    {"abbr": "PeCDF-A", "composite": 5, "derived_class": "Defensive"},
]

_PORTFOLIO = [
    {"abbr": "FA", "role": "core", "allocation_pct": 30.0},
    {"abbr": "FB", "role": "core", "allocation_pct": 30.0},
    {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 20.0},
    {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 20.0},
]


def _make_state() -> dict:
    return {
        "eligible_funds": _ELIGIBLE_FUNDS,
        "cfs_scores": _CFS_SCORES,
        "portfolio": _PORTFOLIO,
    }


# ── Per-fund schema fields ────────────────────────────────────────────────────

def test_per_fund_fields_present_and_correct():
    figures = extract_figures(_make_state())
    funds = figures["funds"]

    assert set(funds.keys()) == {"FA", "FB", "PeEMAS", "PeCDF-A"}

    fa = funds["FA"]
    assert fa["cfs"] == 70
    assert fa["rank"] == 1
    assert fa["weighted_alpha"] == 6.0
    assert fa["allocation_pct"] == 30.0
    assert fa["role"] == "core"
    assert fa["derived_class"] == "Equity-equivalent"
    assert fa["exposure_pct"]["assets"] == _FA["assets"]
    assert fa["exposure_pct"]["geo"] == _FA["geo"]

    # Rank reflects cfs_scores order (already-sorted, reused not recomputed).
    assert funds["FB"]["rank"] == 2
    assert funds["PeEMAS"]["rank"] == 3
    assert funds["PeCDF-A"]["rank"] == 4
    assert funds["PeCDF-A"]["weighted_alpha"] == -0.1


def test_fund_missing_from_cfs_scores_degrades_gracefully():
    state = _make_state()
    state["cfs_scores"] = [c for c in _CFS_SCORES if c["abbr"] != "PeCDF-A"]
    figures = extract_figures(state)
    pecdfa = figures["funds"]["PeCDF-A"]
    assert pecdfa["cfs"] is None
    assert pecdfa["rank"] is None
    # weighted_alpha still comes from eligible_funds, independent of cfs_scores.
    assert pecdfa["weighted_alpha"] == -0.1
    # derived_class falls back to consultant_engine.cfs.derived_class(fund) —
    # PeCDF-A's assets (mm=100) makes it Defensive either way.
    assert pecdfa["derived_class"] == "Defensive"


# ── Portfolio-level derived aggregates (hand-computed) ────────────────────────
#
# weighted_alpha = 6.0*.30 + 2.0*.30 + 0.5*.20 + (-0.1)*.20
#                = 1.8 + 0.6 + 0.1 - 0.02 = 2.48
# weighted_cfs   = 70*.30 + 50*.30 + 10*.20 + 5*.20 = 21 + 15 + 2 + 1 = 39.0
# benchmark_beat_count = 3 (FA, FB, PeEMAS have weighted_alpha > 0; PeCDF-A does not)
# benchmark_beat_share_pct = 3/4 * 100 = 75.0

def test_portfolio_weighted_alpha_and_cfs():
    figures = extract_figures(_make_state())
    portfolio = figures["portfolio"]
    assert portfolio["n_holdings"] == 4
    assert round(portfolio["weighted_alpha"], 4) == 2.48
    assert round(portfolio["weighted_cfs"], 4) == 39.0


def test_portfolio_benchmark_beat_count_and_share():
    figures = extract_figures(_make_state())
    portfolio = figures["portfolio"]
    assert portfolio["benchmark_beat_count"] == 3
    assert portfolio["benchmark_beat_share_pct"] == 75.0


# ── Per-derived-class aggregates (hand-computed) ──────────────────────────────
# (Grouped by CFS derived_class — not to be confused with consultant_engine.
# portfolio's role-based "sleeves"; see figures_extractor.py's module docstring.)
#
# Equity-equivalent = {FA} alone -> weighted_alpha 6.0, weighted_cfs 70.0, n=1
# Balanced = {FB (.30), PeEMAS (.20)}, class alloc total = .50
#   weighted_alpha = (2.0*.30 + 0.5*.20) / .50 = (0.6+0.1)/0.5 = 1.4
#   weighted_cfs   = (50*.30 + 10*.20) / .50   = (15+2)/0.5   = 34.0
# Defensive = {PeCDF-A} alone -> weighted_alpha -0.1, weighted_cfs 5.0, n=1

def test_by_derived_class_aggregates():
    figures = extract_figures(_make_state())
    by_derived_class = figures["by_derived_class"]

    assert by_derived_class["Equity-equivalent"]["n"] == 1
    assert round(by_derived_class["Equity-equivalent"]["weighted_alpha"], 4) == 6.0
    assert round(by_derived_class["Equity-equivalent"]["weighted_cfs"], 4) == 70.0

    assert by_derived_class["Balanced"]["n"] == 2
    assert round(by_derived_class["Balanced"]["weighted_alpha"], 4) == 1.4
    assert round(by_derived_class["Balanced"]["weighted_cfs"], 4) == 34.0

    assert by_derived_class["Defensive"]["n"] == 1
    assert round(by_derived_class["Defensive"]["weighted_alpha"], 4) == -0.1
    assert round(by_derived_class["Defensive"]["weighted_cfs"], 4) == 5.0


# ── Exposure aggregates (hand-computed against consultant_engine.exposure) ────
#
# Asset-class raw totals (structural sleeves bypass the workbook breakdown and
# route their FULL weighted allocation to a single slice — see exposure.py):
#   dom_equity   = .30*60 + .30*30                     = 27.0
#   for_equity   = .30*20 + .30*20                     = 12.0
#   fixed_income = .30*10 + .30*30                     = 12.0
#   money_market = (.30*(5+5) + .30*(10+10)) + 20.0(structural MM full weight)
#                = (3.0 + 6.0) + 20.0                  = 29.0
#   gold         = 20.0 (structural gold full weight)
# Total = 27+12+12+29+20 = 100 exactly, so normalization is a no-op.
#
# Geo raw totals (Malaysia = dom_equity proxy; structural sleeves are NOT
# geo-overridden — see exposure.py's compute_geo_exposure docstring):
#   Malaysia = .30*60 + .30*30              = 27.0
#   USA      = .30*40 + .30*20               = 18.0
#   Taiwan   = .30*10                        = 3.0
#   Korea    = .30*15                        = 4.5
#   (all other foreign countries are 0, merge into "Other" = 0.0)
# Total = 27+18+3+4.5 = 52.5; normalized to 100 -> 51.4 / 34.3 / 8.6 / 5.7 / 0.0

def test_portfolio_asset_exposure():
    figures = extract_figures(_make_state())
    asset_exposure = figures["portfolio"]["asset_exposure_pct"]
    assert asset_exposure == {
        "exposure.asset.domestic_equity_pct": 27.0,
        "exposure.asset.foreign_equity_pct": 12.0,
        "exposure.asset.fixed_income_pct": 12.0,
        "exposure.asset.money_market_pct": 29.0,
        "exposure.asset.gold_pct": 20.0,
    }


def test_portfolio_geo_exposure():
    figures = extract_figures(_make_state())
    geo_exposure = figures["portfolio"]["geo_exposure_pct"]
    assert geo_exposure == {
        "Malaysia": 51.4,
        "USA": 34.3,
        "Korea": 8.6,
        "Taiwan": 5.7,
        "Other": 0.0,
    }


# ── Purity ─────────────────────────────────────────────────────────────────────

def test_extract_figures_does_not_mutate_input_state():
    state = _make_state()
    before = copy.deepcopy(state)
    extract_figures(state)
    assert state == before


def test_extract_figures_returns_fresh_containers_not_aliases():
    """Mutating the returned figures dict must not reach back into state."""
    state = _make_state()
    figures = extract_figures(state)
    figures["funds"]["FA"]["exposure_pct"]["assets"]["dom_equity"] = -999
    assert state["eligible_funds"][0]["assets"]["dom_equity"] == 60


# ── Empty portfolio edge case ──────────────────────────────────────────────────

def test_empty_portfolio_does_not_crash():
    state = {"eligible_funds": [], "cfs_scores": [], "portfolio": []}
    figures = extract_figures(state)
    assert figures["funds"] == {}
    assert figures["portfolio"]["n_holdings"] == 0
    assert figures["portfolio"]["weighted_alpha"] == 0.0
    assert figures["portfolio"]["benchmark_beat_share_pct"] == 0.0
    assert figures["by_derived_class"] == {}

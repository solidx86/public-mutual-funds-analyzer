from consultant_engine.cfs import (
    derived_class, percentile_rank, weighted_blend, raw_alpha_penalised,
    score_all,
)


def test_derived_class():
    assert derived_class({"assets": {"dom_equity": 70, "for_equity": 10, "fi": 0,
                                     "mm": 10, "deposits": 0, "other": 10}}) == "Equity-equivalent"
    assert derived_class({"assets": {"dom_equity": 5, "for_equity": 0, "fi": 50,
                                     "mm": 20, "deposits": 10, "other": 15}}) == "Defensive"


def test_percentile_rank():
    pop = [10, 20, 30, 40, 50]
    assert percentile_rank(50, pop) == 100
    assert percentile_rank(10, pop) == 0
    assert percentile_rank(30, pop) == 50


def test_weighted_blend_full():
    periods = {"ytd": 1.0, "1y": 2.0, "3y": 3.0, "5y": 4.0}
    assert weighted_blend(periods) == round(3*.4 + 4*.3 + 2*.2 + 1*.1, 4)


def test_weighted_blend_redistributes_missing():
    # only 3Y + 5Y present → weights .4/.3 renormalize to .571/.429
    v = weighted_blend({"3y": 10.0, "5y": 10.0})
    assert round(v, 2) == 10.0


def test_penalties_halve_on_negative_long_alpha():
    fund = {"returns": {"3y": {"alpha": -1.0}, "5y": {"alpha": 2.0},
                        "1y": {"alpha": 5.0}, "ytd": {"alpha": 5.0}}}
    base = raw_alpha_penalised(fund, penalize=False)
    pen = raw_alpha_penalised(fund, penalize=True)
    assert pen == base / 2          # 3Y<0 halves once


def test_returnfit_anchors():
    from consultant_engine.cfs import returnfit_score
    assert returnfit_score(1.5) == 100
    assert returnfit_score(1.0) == 80
    assert returnfit_score(0.75) == 50
    assert returnfit_score(0.0) == 0


def test_returnfit_interpolates():
    from consultant_engine.cfs import returnfit_score
    assert 80 < returnfit_score(1.25) < 100      # between 1.0 and 1.5


def test_efficiency_prefers_3y_then_1y():
    from consultant_engine.cfs import efficiency_raw
    assert efficiency_raw({"alpha_efficiency": {"3y": 1.2, "1y": 0.5}}) == 1.2
    assert efficiency_raw({"alpha_efficiency": {"3y": None, "1y": 0.5}}) == 0.5


def test_efficiency_preserves_zero_3y():
    from consultant_engine.cfs import efficiency_raw
    # 0.0 is a valid Alpha Efficiency value — it must NOT fall through to 1Y
    assert efficiency_raw({"alpha_efficiency": {"3y": 0.0, "1y": 0.5}}) == 0.0


def test_momentum_at_ath_fast_recovery():
    from consultant_engine.cfs import momentum_score
    assert momentum_score(0.0, 10) == 95          # band 80 + <30d bonus 15


def test_momentum_none_drawdown_defaults_to_minus_50():
    from consultant_engine.cfs import momentum_score
    # None drawdown defaults to -50.0; compare against -50.0 with the SAME days
    assert momentum_score(None, None) == momentum_score(-50.0, None)


def test_momentum_clamped():
    from consultant_engine.cfs import momentum_score
    assert momentum_score(-3.0, 500) == 70        # 80 base + (-10) old → 70


def test_base_weights_sum_100():
    from consultant_engine.cfs import profile_weights
    w = profile_weights("Moderate", 5.0)        # at midpoint → no stretch
    assert round(sum(w.values())) == 100
    assert w["returnfit"] == 40


def test_stretch_above_shifts_alpha_to_returnfit():
    from consultant_engine.cfs import profile_weights
    w = profile_weights("Moderate", 6.0)        # +20% stretch
    base = profile_weights("Moderate", 5.0)
    assert w["returnfit"] > base["returnfit"] and w["alpha"] < base["alpha"]


# ── score_all tests ────────────────────────────────────────────────────────────

def _f(abbr, a3, ret3, ae3, dd):
    return {
        "abbr": abbr,
        "assets": {"dom_equity": 80, "for_equity": 0, "fi": 0,
                   "mm": 10, "deposits": 0, "other": 10},
        "returns": {
            "3y": {"alpha": a3, "fund": ret3},
            "5y": {"alpha": a3, "fund": ret3},
            "1y": {"alpha": a3, "fund": ret3},
            "ytd": {"alpha": a3, "fund": ret3},
        },
        "alpha_efficiency": {"3y": ae3},
        "drawdown": dd,
        "days_from_ath": 20,
    }


def test_score_all_ranks_higher_alpha_first():
    funds = [_f("LOW", 1.0, 5.0, 0.3, -3.0), _f("HIGH", 8.0, 12.0, 1.5, -3.0)]
    scores = score_all(funds, "Moderate", 5.0)
    assert scores[0]["abbr"] == "HIGH"
    assert 0 <= scores[0]["composite"] <= 100


def test_score_all_returnfit_is_absolute_not_percentile():
    """
    ReturnFit_N must use the absolute piecewise curve, not percentile.

    Fund EXACT has Wtd_Return == target_annual_return_pct (ratio 1.0) → returnfit_score(1.0) == 80.
    Fund ABOVE has a higher return. In a percentile world EXACT would score below 100;
    on the absolute curve it must be exactly 80 regardless of class rank.
    """
    exact = _f("EXACT", 5.0, 5.0, 1.0, -3.0)   # ret3=5.0 == target_annual_return_pct=5.0 → ratio 1.0
    above = _f("ABOVE", 7.0, 10.0, 1.5, -3.0)   # higher return, would be top of class
    scores = score_all([exact, above], "Moderate", 5.0)
    score_exact = next(s for s in scores if s["abbr"] == "EXACT")
    assert score_exact["returnfit_n"] == 80.0

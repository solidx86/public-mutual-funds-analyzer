from consultant_engine.cfs import derived_class, percentile_rank, weighted_blend, raw_alpha_penalised


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

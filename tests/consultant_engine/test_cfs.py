from consultant_engine.cfs import derived_class, percentile_rank


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

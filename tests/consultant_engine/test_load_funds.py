from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.portfolio import dedup_overlap


def test_step1b_exclusions(tiny_fundmaster):
    out = load_funds({"fundmaster_path": tiny_fundmaster})
    abbrs = {f["abbr"] for f in out["eligible_funds"]}
    assert abbrs == {"PIX", "PeCDF-A"}           # PB / -B / wholesale dropped
    pix = next(f for f in out["eligible_funds"] if f["abbr"] == "PIX")
    assert pix["risk_level"] == 3 and pix["drawdown"] == -3.0


def test_top5_parsed_as_list_of_names(fundmaster_top5):
    out = load_funds({"fundmaster_path": fundmaster_top5})
    f = next(x for x in out["eligible_funds"] if x["abbr"] == "PAAA")
    assert f["top5"] == ["Apple Inc", "Microsoft", "Nvidia", "Tesla", "Amazon"]


def test_no_false_overlap_between_string_holdings(fundmaster_top5):
    out = load_funds({"fundmaster_path": fundmaster_top5})
    funds = {x["abbr"]: x for x in out["eligible_funds"]}
    picks = [
        {"abbr": "PAAA", "alpha_n": 80, "top5": funds["PAAA"]["top5"]},
        {"abbr": "PBBB", "alpha_n": 60, "top5": funds["PBBB"]["top5"]},
    ]
    kept = {p["abbr"] for p in dedup_overlap(picks)}
    assert kept == {"PAAA", "PBBB"}, "zero real holdings in common — neither should be dropped"


def test_real_overlap_still_dedups_lower_alpha():
    """Positive control: two funds sharing ≥3 real holding names → the
    lower-alpha pick is dropped. Proves dedup still acts on genuine overlap."""
    picks = [
        {"abbr": "PAAA", "alpha_n": 80, "top5": ["Apple Inc", "Microsoft", "Nvidia", "Tesla", "Amazon"]},
        {"abbr": "PBBB", "alpha_n": 60, "top5": ["Apple Inc", "Microsoft", "Nvidia", "Petronas", "Maybank"]},
    ]
    kept = {p["abbr"] for p in dedup_overlap(picks)}
    assert kept == {"PAAA"}, "3 real holdings in common — lower-alpha PBBB dropped"

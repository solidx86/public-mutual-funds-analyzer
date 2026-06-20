from consultant_engine.nodes.load_funds import load_funds


def test_step1b_exclusions(tiny_fundmaster):
    out = load_funds({"fundmaster_path": tiny_fundmaster})
    abbrs = {f["abbr"] for f in out["eligible_funds"]}
    assert abbrs == {"PIX", "PeCDF-A"}           # PB / -B / wholesale dropped
    pix = next(f for f in out["eligible_funds"] if f["abbr"] == "PIX")
    assert pix["risk_level"] == 3 and pix["drawdown"] == -3.0

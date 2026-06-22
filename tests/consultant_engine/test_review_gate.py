import json
from consultant_engine.nodes.review_gate import build_proposed_allocation, write_artifact, apply_resume


def _make_state(**overrides):
    base = {
        "thread_id": "t1",
        "client_profile": {
            "risk_level": "Moderate",
            "target_annual_return_pct": 5.0,
            "shariah": False,
            "experience": "experienced",
            "upfront_capital_rm": 50000,
        },
        "fundmaster_path": "fm.xlsx",
        "portfolio": [{"abbr": "PIX", "role": "core", "allocation_pct": 40}],
        "cfs_scores": [{"abbr": "PIX", "composite": 88, "alpha_n": 90}],
    }
    base.update(overrides)
    return base


def test_artifact_has_three_blocks(tmp_path):
    state = _make_state()
    art = build_proposed_allocation(state)
    assert set(art) >= {"context", "constraints", "allocation", "review"}
    assert art["constraints"]["allocations_sum_to_pct"] == 100
    p = write_artifact(tmp_path, "t1", art)
    assert json.loads(p.read_text())["allocation"][0]["abbr"] == "PIX"


def test_constraints_derive_from_invariants_for_moderate(tmp_path):
    """Moderate profile: per_fund_cap=50, fund_count={min:4,max:4} from invariants."""
    state = _make_state()
    art = build_proposed_allocation(state)
    assert art["constraints"]["per_fund_cap_pct"] == 50
    assert art["constraints"]["fund_count"] == {"min": 4, "max": 4}


def test_html_preview_is_written_and_contains_abbrev(tmp_path):
    """write_artifact must also write a .html file containing the abbr."""
    state = _make_state()
    art = build_proposed_allocation(state)
    json_path = write_artifact(tmp_path, "t1", art)
    html_path = json_path.with_suffix(".html")
    assert html_path.exists(), "HTML preview file must be written alongside JSON"
    html_content = html_path.read_text()
    assert "PIX" in html_content, "HTML must contain the fund abbreviation"


def test_allocation_entry_fields(tmp_path):
    """Each allocation entry must have abbr, role, allocation_pct, cfs, rank, risk_level, eligible."""
    state = _make_state(
        portfolio=[{"abbr": "PIX", "role": "core", "allocation_pct": 40}],
        cfs_scores=[{"abbr": "PIX", "composite": 88, "alpha_n": 90}],
        filtered_funds=[{"abbr": "PIX", "risk_level": 3}],
    )
    art = build_proposed_allocation(state)
    entry = art["allocation"][0]
    assert entry["abbr"] == "PIX"
    assert entry["role"] == "core"
    assert entry["allocation_pct"] == 40
    assert entry["cfs"] == 88
    assert entry["rank"] == 1
    assert entry["risk_level"] == 3
    assert entry["eligible"] is True


def test_cfs_and_rank_none_when_not_in_scores(tmp_path):
    """A structural fund not in cfs_scores gets cfs=None, rank=None, eligible=False."""
    state = _make_state(
        portfolio=[
            {"abbr": "PIX", "role": "core", "allocation_pct": 40},
            {"abbr": "PGOLD", "role": "structural:gold", "allocation_pct": 60},
        ],
        cfs_scores=[{"abbr": "PIX", "composite": 88, "alpha_n": 90}],
        filtered_funds=[{"abbr": "PIX", "risk_level": 3}],
    )
    art = build_proposed_allocation(state)
    gold_entry = next(e for e in art["allocation"] if e["abbr"] == "PGOLD")
    assert gold_entry["cfs"] is None
    assert gold_entry["rank"] is None
    assert gold_entry["eligible"] is False


def test_artifact_schema_version_and_review_block():
    """Artifact must carry schema_version='1.0' and review block default."""
    state = _make_state()
    art = build_proposed_allocation(state)
    assert art["schema_version"] == "1.0"
    assert art["review"]["decision"] == "approve"
    assert art["review"]["note"] == ""


def test_thread_id_in_artifact():
    state = _make_state(thread_id="my-thread-42")
    art = build_proposed_allocation(state)
    assert art["thread_id"] == "my-thread-42"


def test_write_artifact_creates_directory(tmp_path):
    """write_artifact must create nested directories if they don't exist."""
    state = _make_state()
    art = build_proposed_allocation(state)
    nested = tmp_path / "deep" / "nested" / "dir"
    p = write_artifact(nested, "t1", art)
    assert p.exists()
    assert p.name == "t1.json"


# ---------------------------------------------------------------------------
# Task 2.2 — apply_resume tests (write FIRST, run RED before implementing)
# ---------------------------------------------------------------------------

def test_overcap_edit_is_rejected():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [{"abbr": "PIX", "alpha_n": 90}, {"abbr": "PeDiv", "alpha_n": 80}],
             "_universe": {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"abbr": "PIX", "allocation_pct": 60},        # over the cap
        {"abbr": "PeDiv", "allocation_pct": 20},
        {"abbr": "PeEMAS", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "allocation_pct": 10}]}
    out = apply_resume(state, payload)
    assert out["violations"]                              # re-validation caught the cap breach


def test_clean_edit_accepted():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [{"abbr": "PIX", "alpha_n": 90}, {"abbr": "PeDiv", "alpha_n": 80}],
             "_universe": {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"abbr": "PIX", "allocation_pct": 40},
        {"abbr": "PeDiv", "allocation_pct": 40},
        {"abbr": "PeEMAS", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "allocation_pct": 10}]}
    out = apply_resume(state, payload)
    assert out.get("violations", []) == []
    assert {h["abbr"] for h in out["portfolio"]} == {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}


def test_bare_approve_returns_empty():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [],
             "_universe": set()}
    out = apply_resume(state, {"decision": "approve"})
    assert out == {}


def test_apply_resume_accepts_abbrev_key():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [], "_universe": {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"abbrev": "PIX", "allocation_pct": 40},
        {"abbrev": "PeDiv", "allocation_pct": 40},
        {"abbrev": "PeEMAS", "allocation_pct": 10},
        {"abbrev": "PeCDF-A", "allocation_pct": 10}]}
    out = apply_resume(state, payload)
    assert out.get("violations", []) == []
    assert {h["abbr"] for h in out["portfolio"]} == {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}


def test_apply_resume_malformed_edit_does_not_crash():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [], "_universe": {"PIX", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"allocation_pct": 40},                       # no abbr/abbrev key at all
        {"abbrev": "PeEMAS", "allocation_pct": 10}]}
    out = apply_resume(state, payload)            # must NOT raise KeyError
    assert any(v["code"] == "malformed_edit" for v in out["violations"])


def test_build_portfolio_persists_universe_for_structural_reapproval(fundmaster_4fund):
    from consultant_engine.nodes.load_profile import load_profile
    from consultant_engine.nodes.load_funds import load_funds
    from consultant_engine.nodes.filter_universe import filter_universe
    from consultant_engine.nodes.score_cfs import score_cfs
    from consultant_engine.nodes.build_portfolio import build_portfolio

    s = {"client_profile": {"risk_level": "Moderate", "shariah": False},
         "fundmaster_path": fundmaster_4fund, "macro_context": {"source": "fixture"}}
    for step in (load_profile, load_funds, filter_universe, score_cfs, build_portfolio):
        s.update(step(s))

    # build_portfolio must have published the universe it validated against.
    assert "_universe" in s and s["_universe"], "build_portfolio must persist _universe"

    # A plain re-approval of the engine's own portfolio must be violation-free,
    # even though the structural sleeves are outside eligible_funds.
    payload = {"allocation": [
        {"abbrev": h["abbr"], "allocation_pct": h["allocation_pct"]}
        for h in s["portfolio"]]}
    out = apply_resume(s, payload)
    assert out.get("violations", []) == [], out

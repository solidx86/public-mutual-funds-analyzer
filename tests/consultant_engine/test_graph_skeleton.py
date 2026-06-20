from langgraph.checkpoint.memory import MemorySaver
from consultant_engine.graph import build_graph
import pytest
from langgraph.types import Command


def test_macro_runs_before_build_portfolio(fundmaster_4fund):
    """I2: macro_context must run BEFORE build_portfolio so exposure_gaps from the
    macro contract actually reach the gap-substitution branch (which was dead when
    build ran first)."""
    app = build_graph(MemorySaver())
    edges = {(e.source, e.target) for e in app.get_graph().edges}

    assert ("score_cfs", "macro_context") in edges
    assert ("macro_context", "build_portfolio") in edges
    # The old order must be gone — build no longer feeds macro_context.
    assert ("build_portfolio", "macro_context") not in edges
    assert ("score_cfs", "build_portfolio") not in edges


def test_graph_runs_end_to_end_with_stubs(fundmaster_4fund, tmp_path):
    # Use fundmaster_4fund (not tiny_fundmaster): the real build_portfolio node
    # requires ≥2 equity funds + PeEMAS + PeCDF-A to pass invariants.
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}}
    # no_review=True skips the interrupt so a single invoke runs to emit
    out = app.invoke(
        {"thread_id": "t1", "no_review": True, "fundmaster_path": fundmaster_4fund,
         "client_profile": {"risk_level": "Moderate"},
         "output_dir": str(tmp_path)},
        cfg,
    )
    assert out["output_path"]  # emit now produces a real versioned path
    assert "FundProposal_Moderate_" in out["output_path"]
    assert "_v0.1.0.html" in out["output_path"]  # version from proposal_html stamp
    assert out["proposal_html"]


def test_interrupt_pauses_then_resumes(fundmaster_4fund, tmp_path):
    # Use fundmaster_4fund (not tiny_fundmaster): the real build_portfolio node
    # requires ≥2 equity funds + PeEMAS + PeCDF-A to pass invariants.
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t2"}}
    out = app.invoke({"thread_id": "t2", "client_profile": {"risk_level": "Moderate"},
                      "fundmaster_path": fundmaster_4fund,
                      "output_dir": str(tmp_path)}, cfg)
    assert "__interrupt__" in out                      # paused at review_gate
    out2 = app.invoke(Command(resume={"decision": "approve"}), cfg)
    assert out2["output_path"]  # emit now produces a real versioned path
    assert "FundProposal_Moderate_" in out2["output_path"]
    assert "_v0.1.0.html" in out2["output_path"]  # version from proposal_html stamp


# --- payloads for the second-round review tests (fundmaster_4fund universe) ---
# Universe = {PGA, PBA, PSCA, PeEMAS, PeCDF-A}; PeEMAS=gold, PeCDF-A=money-market.
_VIOLATING_EDIT = {
    "allocation": [
        {"abbr": "PGA", "allocation_pct": 40},
        {"abbr": "PBA", "allocation_pct": 40},
        {"abbr": "PeEMAS", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "allocation_pct": 5},   # sums to 95 → sum violation
    ]
}
_VALID_EDIT = {
    "allocation": [
        {"abbr": "PGA", "allocation_pct": 30},
        {"abbr": "PBA", "allocation_pct": 30},
        {"abbr": "PeEMAS", "allocation_pct": 25},
        {"abbr": "PeCDF-A", "allocation_pct": 15},  # sums to 100, all within cap
    ]
}


def test_violating_edit_repauses_then_valid_correction_is_applied(fundmaster_4fund, tmp_path):
    """I3 regression: a violating resumed edit must re-pause, and a second valid
    correction must be applied (not silently dropped)."""
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t3"}}
    out = app.invoke({"thread_id": "t3", "client_profile": {"risk_level": "Moderate"},
                      "fundmaster_path": fundmaster_4fund,
                      "output_dir": str(tmp_path)}, cfg)
    assert "__interrupt__" in out                      # paused at review_gate

    # First resume: a violating edit (sum != 100) must re-pause, not finish.
    out2 = app.invoke(Command(resume=_VIOLATING_EDIT), cfg)
    assert "__interrupt__" in out2, "violating edit must re-pause for correction"
    assert "output_path" not in out2, "must not emit a proposal on a violating edit"

    # Second resume: a valid correction must complete AND be applied.
    out3 = app.invoke(Command(resume=_VALID_EDIT), cfg)
    assert out3.get("output_path"), "valid correction must let the run complete"
    corrected = {h["abbr"]: h["allocation_pct"] for h in out3["portfolio"]}
    assert corrected == {"PGA": 30, "PBA": 30, "PeEMAS": 25, "PeCDF-A": 15}, (
        "final portfolio must reflect the corrected holdings, not the stale build"
    )


def test_repeated_violating_edits_fail_loud_after_cap(fundmaster_4fund, tmp_path):
    """Fail-loud cap: MAX_REVIEW_ROUNDS violating edits in a row must raise, never
    emit a broken proposal."""
    from consultant_engine.graph import MAX_REVIEW_ROUNDS

    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t4"}}
    out = app.invoke({"thread_id": "t4", "client_profile": {"risk_level": "Moderate"},
                      "fundmaster_path": fundmaster_4fund,
                      "output_dir": str(tmp_path)}, cfg)
    assert "__interrupt__" in out

    # Resume with a violating edit up to (but not past) the cap; each re-pauses.
    for _ in range(MAX_REVIEW_ROUNDS):
        out = app.invoke(Command(resume=_VIOLATING_EDIT), cfg)
        assert "__interrupt__" in out

    # One more violating edit exhausts the cap → fail loudly.
    with pytest.raises(RuntimeError, match=r"did not validate after \d+ rounds"):
        app.invoke(Command(resume=_VIOLATING_EDIT), cfg)

from langgraph.checkpoint.memory import MemorySaver
from consultant_engine.graph import build_graph


def test_graph_runs_end_to_end_with_stubs(fundmaster_4fund):
    # Use fundmaster_4fund (not tiny_fundmaster): the real build_portfolio node
    # requires ≥2 equity funds + PeEMAS + PeCDF-A to pass invariants.
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}}
    # no_review=True skips the interrupt so a single invoke runs to emit
    out = app.invoke(
        {"thread_id": "t1", "no_review": True, "fundmaster_path": fundmaster_4fund,
         "client_profile": {"risk_level": "Moderate"}},
        cfg,
    )
    assert out["output_path"] == "STUB"
    assert out["proposal_html"]


import pytest
from langgraph.types import Command


def test_interrupt_pauses_then_resumes(fundmaster_4fund):
    # Use fundmaster_4fund (not tiny_fundmaster): the real build_portfolio node
    # requires ≥2 equity funds + PeEMAS + PeCDF-A to pass invariants.
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t2"}}
    out = app.invoke({"thread_id": "t2", "client_profile": {"risk_level": "Moderate"},
                      "fundmaster_path": fundmaster_4fund}, cfg)
    assert "__interrupt__" in out                      # paused at review_gate
    out2 = app.invoke(Command(resume={"decision": "approve"}), cfg)
    assert out2["output_path"] == "STUB"               # resumed to completion

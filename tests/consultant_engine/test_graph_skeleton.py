from langgraph.checkpoint.memory import MemorySaver
from consultant_engine.graph import build_graph


def test_graph_runs_end_to_end_with_stubs():
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}}
    # no_review=True skips the interrupt so a single invoke runs to emit
    out = app.invoke(
        {"thread_id": "t1", "no_review": True, "fundmaster_path": "x", "client_profile": {}},
        cfg,
    )
    assert out["output_path"] == "STUB"
    assert out["proposal_html"]


import pytest
from langgraph.types import Command


def test_interrupt_pauses_then_resumes():
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t2"}}
    out = app.invoke({"thread_id": "t2", "client_profile": {}, "fundmaster_path": "x"}, cfg)
    assert "__interrupt__" in out                      # paused at review_gate
    out2 = app.invoke(Command(resume={"decision": "approve"}), cfg)
    assert out2["output_path"] == "STUB"               # resumed to completion

"""Task 4.3 — repair node + fail-loud integration.

Tests:
  1. Unit: repair() increments the counter and replaces the proposal HTML.
  2. Graph: with a persistently-broken proposal (fake LLM), the graph raises
     RuntimeError after exactly MAX_REPAIR (3) repair attempts (fail-loud).
"""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from consultant_engine.nodes.repair import repair
from consultant_engine.graph import build_graph
import consultant_engine.nodes.generate_proposal as gp_mod


# ── Unit test ────────────────────────────────────────────────────────────────

def test_repair_increments_and_replaces():
    """repair() must increment repair_iterations and set proposal_html."""
    out = repair({
        "violations": [{"code": "x", "msg": "y"}],
        "proposal_html": "<old>",
        "repair_iterations": 1,
    })
    assert out["repair_iterations"] == 2
    assert "proposal_html" in out
    # The returned HTML must differ from the stub "<old>" (LLM produced something)
    # In fake-LLM mode (set by conftest autouse fixture) it returns <!--FAKE_LLM-->
    assert out["proposal_html"] != "<old>"


# ── Graph fail-loud test ──────────────────────────────────────────────────────

def test_fail_loud_after_max_repairs(fundmaster_4fund, monkeypatch, tmp_path):
    """With a persistently-broken proposal the graph must raise RuntimeError
    after exactly MAX_REPAIR (3) repair iterations."""
    # Inject a generate_proposal that always returns invalid HTML (no sections)
    monkeypatch.setattr(
        "consultant_engine.nodes.generate_proposal.generate_proposal",
        lambda state: {"proposal_html": "<html><body>broken — no sections</body></html>"},
    )

    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "fail1"}}

    with pytest.raises(RuntimeError):
        app.invoke(
            {
                "thread_id": "fail1",
                "no_review": True,
                "fundmaster_path": fundmaster_4fund,
                "client_profile": {"risk_level": "Moderate", "shariah": False},
                "macro_context": {"source": "fixture"},
                "output_dir": str(tmp_path),
            },
            cfg,
        )

    # Verify repair_iterations reached MAX_REPAIR (3) by inspecting the checkpoint
    final_state = app.get_state(cfg)
    assert final_state.values.get("repair_iterations", 0) >= 3

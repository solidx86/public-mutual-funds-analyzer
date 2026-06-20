"""Integration test for the build_portfolio node (Task 1.16 L1 capstone).

Runs the full real pipeline on the fundmaster_4fund fixture — no mocks,
real Excel parsing, real CFS scoring, real invariant gate.
"""

import pytest

from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.nodes.build_portfolio import build_portfolio


def test_build_portfolio_full_pipeline(fundmaster_4fund):
    s = {
        "client_profile": {"risk_level": "Moderate", "shariah": False},
        "fundmaster_path": fundmaster_4fund,
        "macro_context": {},
    }
    s.update(load_profile(s))
    s.update(load_funds(s))
    s.update(filter_universe(s))
    s.update(score_cfs(s))
    out = build_portfolio(s)

    port = out["portfolio"]
    roles = {h["role"] for h in port}

    # Exactly 4 holdings
    assert len(port) == 4, f"Expected 4 holdings, got {len(port)}: {port}"

    # Both structural roles present
    assert "structural:gold" in roles, f"Missing structural:gold in roles {roles}"
    assert "structural:money_market" in roles, f"Missing structural:money_market in roles {roles}"

    # Allocations sum to 100
    total = sum(h["allocation_pct"] for h in port)
    assert round(total) == 100, f"Allocations sum to {total}, not 100"

    # proposed_allocation key is present
    assert "proposed_allocation" in out

    # No invariant violations were raised (no exception) — implicit by reaching here

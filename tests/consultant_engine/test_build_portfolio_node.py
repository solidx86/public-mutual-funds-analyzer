"""Integration test for the build_portfolio node (Task 1.16 L1 capstone).

Runs the full real pipeline on the fundmaster_4fund fixture — no mocks,
real Excel parsing, real CFS scoring, real invariant gate.
"""

import pytest

from conftest import _row
from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.nodes.macro_context import macro_context
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


# ── I2: exposure-gap substitution is LIVE + Shariah-safe ─────────────────────

def _scored_state(fundmaster_4fund, *, risk_level, shariah, macro_in):
    """Run the real load→filter→score→macro_context nodes, mirroring the graph
    order (macro BEFORE build). ``macro_in`` is the caller-supplied macro contract
    that macro_context resolves into state["macro_context"].

    Returns a state ready for build_portfolio with filtered_funds / eligible_funds
    / cfs_scores from real parsing+scoring and macro_context resolved by the node.
    """
    s = {
        "client_profile": {"risk_level": risk_level, "shariah": shariah},
        "fundmaster_path": fundmaster_4fund,
        "macro_context": macro_in,
    }
    s.update(load_profile(s))
    s.update(load_funds(s))
    s.update(filter_universe(s))
    s.update(score_cfs(s))
    s.update(macro_context(s))
    return s


# A live macro contract that declares an exposure gap. It carries events so the
# macro_context node routes it through model_validate (preserving exposure_gaps)
# rather than discarding it for the gapless fixture.
_LIVE_GAP_CONTRACT = {
    "events": [
        {"date": "2026-06-12", "theme": "china", "claim": "China A-share rally",
         "source_url": "https://example.com/china"},
    ],
    "exposure_gaps": ["China"],
}


def test_exposure_gap_fires_when_macro_declares_gaps(fundmaster_4fund):
    """Liveness (I2 Fix A): a live macro contract carrying exposure_gaps, resolved
    by the macro_context node that now runs BEFORE build_portfolio, must trigger the
    swap. Aggressive → alpha_outlier skips, so the discretionary slot is free.

    Before Fix A the contract's gaps never reach build (macro ran after build, and
    the fixture is gapless), so no exposure_gap holding appears.
    """
    s = _scored_state(
        fundmaster_4fund,
        risk_level="Aggressive",
        shariah=False,
        macro_in=_LIVE_GAP_CONTRACT,
    )
    assert s["macro_context"]["exposure_gaps"] == ["China"]  # contract carried through
    out = build_portfolio(s)
    roles = [h["role"] for h in out["portfolio"]]
    assert "exposure_gap" in roles, f"expected an exposure_gap holding, got roles {roles}"
    assert "satellite" not in roles, "Aggressive must not fire a satellite"


def test_exposure_gap_respects_shariah_filter(tmp_path):
    """Shariah safety (I2 Fix B): the gap pick must come from filtered_funds (Shariah
    + risk-ceiling compliant), never from the broader eligible_funds — even when a
    higher-3Y-alpha NON-Shariah fund exists in eligible_funds.

    Before Fix B (candidates=eligible_funds) the higher-alpha conventional fund is
    picked, leaking a non-compliant fund into a Shariah client's portfolio.
    """
    import openpyxl

    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Master"
    ws.cell(3, 1, "Fund Name")

    # Two Shariah equity cores (the only funds that survive the Shariah filter).
    _row(ws, 4, "Public Islamic Growth", "PIGA", "Yes", "Equity", 3, "Qualified", 4.0,
         c15=20.0, c16=15.0, c17=5.0,
         c18=18.0, c19=13.0, c20=5.0,
         c21=15.0, c22=11.0, c23=4.0,
         c24=12.0, c25=9.0,  c26=3.0,
         c27=10.0, c28=8.0,  c29=2.0,
         c35=75.0, c36=10.0,
         c72=-5.0, c73=20)
    _row(ws, 5, "Public Islamic Balanced", "PIBA", "Yes", "Equity", 3, "Qualified", 3.0,
         c15=18.0, c16=14.0, c17=4.0,
         c18=16.0, c19=12.0, c20=4.0,
         c21=12.0, c22=9.0,  c23=3.0,
         c24=10.0, c25=7.5,  c26=2.5,
         c27=9.0,  c28=7.5,  c29=1.5,
         c35=75.0, c36=10.0,
         c72=-5.0, c73=30)
    # A Shariah gap candidate with a MODEST 3Y alpha (the only compliant pick).
    _row(ws, 6, "Public Islamic Asia", "PIAS", "Yes", "Equity", 3, "Qualified", 2.0,
         c15=15.0, c16=12.0, c17=3.0,
         c18=13.0, c19=10.0, c20=3.0,
         c21=10.0, c22=8.0,  c23=2.0,    # 3Y alpha = +2.0
         c24=8.0,  c25=6.5,  c26=1.5,
         c27=7.0,  c28=6.0,  c29=1.0,
         c35=75.0, c36=10.0,
         c72=-5.0, c73=45)
    # A NON-Shariah fund with the HIGHEST 3Y alpha — must NEVER be picked for a
    # Shariah client. It is in eligible_funds but filtered out of filtered_funds.
    _row(ws, 7, "Public Conventional Tech", "PCTECH", "No", "Equity", 3, "Qualified", 9.0,
         c15=30.0, c16=15.0, c17=15.0,
         c18=28.0, c19=13.0, c20=15.0,
         c21=25.0, c22=11.0, c23=14.0,   # 3Y alpha = +14.0 (highest)
         c24=22.0, c25=9.0,  c26=13.0,
         c27=20.0, c28=8.0,  c29=12.0,
         c35=75.0, c36=10.0,
         c72=-5.0, c73=15)
    # Structurals (Shariah-compliant so they survive the filter).
    _row(ws, 8, "Public e-Islamic EMAS", "PeEMAS", "Yes", "Gold", 3, "Qualified", 0.5,
         c15=5.0, c16=4.0, c17=1.0,
         c18=4.0, c19=3.5, c20=0.5,
         c21=3.0, c22=2.5, c23=0.5,
         c40=95.0,
         c72=-2.0, c73=10)
    _row(ws, 9, "Public Islamic Money Market", "PIMMF-A", "Yes", "Money Market", 1, "Qualified", 0.1,
         c15=2.0, c16=2.0, c17=0.0,
         c18=2.0, c19=2.0, c20=0.0,
         c21=2.0, c22=2.0, c23=0.0,
         c38=100.0,
         c72=-1.0, c73=5)
    p = tmp_path / "PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx"
    wb.save(p)

    s = _scored_state(
        str(p),
        risk_level="Aggressive",
        shariah=True,
        macro_in=_LIVE_GAP_CONTRACT,
    )
    # Sanity: the high-alpha conventional fund IS in eligible but NOT in filtered.
    elig = {f["abbr"] for f in s["eligible_funds"]}
    filt = {f["abbr"] for f in s["filtered_funds"]}
    assert "PCTECH" in elig and "PCTECH" not in filt

    out = build_portfolio(s)
    gap = next((h for h in out["portfolio"] if h["role"] == "exposure_gap"), None)
    assert gap is not None, f"expected an exposure_gap holding, got {out['portfolio']}"
    assert gap["abbr"] != "PCTECH", "Shariah leak: non-Shariah fund picked for the gap"
    assert gap["abbr"] in filt, f"gap pick {gap['abbr']} must come from filtered_funds"

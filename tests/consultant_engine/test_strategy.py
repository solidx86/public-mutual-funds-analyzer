"""Group 5 — §7 Investment Strategy: Python owns the RSP table; the other three
sub-sections stay LLM prose but render as bullet lists.

The RSP "Regular Savings Plan" sub-section is pure arithmetic (allocation % →
ringgit split of a RM 1,000/mo commitment), so it is a Python-rendered table — never
the LLM's. Distribution / Rebalancing / Dip-capture stay LLM-owned prose, now in a
``<ul>`` container.

Runs offline via the autouse fake-LLM fixture in tests/conftest.py.
"""
import re

from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.macro_context import macro_context
from consultant_engine.nodes.generate_proposal import generate_proposal, _build_rsp_table


def _pipeline(fundmaster_4fund):
    """Build a proposal from the real pipeline with macro events populated."""
    s = {"client_profile": {"risk_level": "Moderate", "shariah": False},
         "fundmaster_path": fundmaster_4fund, "macro_context": {"source": "fixture"}}
    for step in (load_profile, load_funds, filter_universe, score_cfs,
                 macro_context, build_portfolio, generate_proposal):
        s.update(step(s))
    return s


def _html(fundmaster_4fund):
    return _pipeline(fundmaster_4fund)["proposal_html"]


def _section7(html: str) -> str:
    """Return the §7 Investment Strategy section div (used to scope §7-only assertions)."""
    m = re.search(
        r'<div class="section-num">7</div>.*?(?=<div class="section-num">8</div>)',
        html, re.DOTALL,
    )
    assert m, "expected §7 to be present"
    return m.group(0)


# ── _build_rsp_table unit tests — one row per holding + a summed Total row ────

def test_build_rsp_table_synthetic_40_30_20_10():
    """A 40/30/20/10 portfolio → RM 400/300/200/100, Total 100% / RM 1000."""
    portfolio = [
        {"abbr": "PGA", "allocation_pct": 40},
        {"abbr": "PBA", "allocation_pct": 30},
        {"abbr": "PSCA", "allocation_pct": 20},
        {"abbr": "PeCDF-A", "allocation_pct": 10},
    ]
    table = _build_rsp_table(portfolio)

    # Reuses the perf-table style, wrapped in table-wrap.
    assert '<div class="table-wrap"><table class="perf-table">' in table
    # Header columns.
    assert "<th>Fund</th><th>Allocation %</th><th>per RM 1,000 / mo</th>" in table

    # One body row per holding, ringgit == allocation_pct * 10.
    assert "<tr><td>PGA</td><td>40%</td><td>RM 400</td></tr>" in table
    assert "<tr><td>PBA</td><td>30%</td><td>RM 300</td></tr>" in table
    assert "<tr><td>PSCA</td><td>20%</td><td>RM 200</td></tr>" in table
    assert "<tr><td>PeCDF-A</td><td>10%</td><td>RM 100</td></tr>" in table

    # Total row summed from the actual data (not hardcoded 100 / 1000).
    assert (
        "<tr><td><strong>Total</strong></td><td><strong>100%</strong></td>"
        "<td><strong>RM 1000</strong></td></tr>" in table
    )

    # Six <tr> total: 1 header + 4 holding rows + 1 Total row.
    assert table.count("<tr>") == 6


def test_build_rsp_table_fractional_allocation_renders_whole_ringgit():
    """12.5% → RM 125, with no spurious decimals on the ringgit cell."""
    portfolio = [
        {"abbr": "A", "allocation_pct": 12.5},
        {"abbr": "B", "allocation_pct": 87.5},
    ]
    table = _build_rsp_table(portfolio)
    assert "<tr><td>A</td><td>12.5%</td><td>RM 125</td></tr>" in table
    assert "<tr><td>B</td><td>87.5%</td><td>RM 875</td></tr>" in table
    # Total: 100% / RM 1000 summed from the data.
    assert (
        "<tr><td><strong>Total</strong></td><td><strong>100%</strong></td>"
        "<td><strong>RM 1000</strong></td></tr>" in table
    )


def test_build_rsp_table_total_is_summed_not_hardcoded():
    """A partial portfolio (allocs not summing to 100) → Total reflects the actual sum."""
    portfolio = [
        {"abbr": "A", "allocation_pct": 30},
        {"abbr": "B", "allocation_pct": 20},
    ]
    table = _build_rsp_table(portfolio)
    assert (
        "<tr><td><strong>Total</strong></td><td><strong>50%</strong></td>"
        "<td><strong>RM 500</strong></td></tr>" in table
    )


# ── Pipeline tests — §7 RSP table renders; old prose key is gone ─────────────

def test_pipeline_rsp_table_in_section7(fundmaster_4fund):
    """§7 carries a Python perf-table with the per-RM-1000 column; the table marker
    and the old strategy.rsp prose key are both gone."""
    html = _html(fundmaster_4fund)
    section7 = _section7(html)

    assert '<table class="perf-table">' in section7
    assert "per RM 1,000" in section7
    # The static intro sentence stays.
    assert "Dollar-cost average into the portfolio" in section7

    # The new table marker is consumed; the old prose key never appears anywhere.
    assert "slot:strategy.rsp_table" not in html
    assert "slot:strategy.rsp" not in html
    assert "[strategy.rsp narrative]" not in html


def test_pipeline_rsp_rows_match_portfolio(fundmaster_4fund):
    """Each holding renders one RSP row with ringgit == allocation_pct * 10."""
    state = _pipeline(fundmaster_4fund)
    html = state["proposal_html"]
    for h in state["portfolio"]:
        ringgit = f"{h['allocation_pct'] * 10:.0f}"
        assert (
            f"<tr><td>{h['abbr']}</td><td>{h['allocation_pct']}%</td>"
            f"<td>RM {ringgit}</td></tr>" in html
        )


# ── The other three §7 sub-sections stay LLM prose, now in <ul> ──────────────

def test_pipeline_other_strategy_slots_are_ul_wrapped_prose(fundmaster_4fund):
    """Distribution / rebalancing / dip_capture remain LLM-owned (still rendered as
    fake-LLM placeholders), now wrapped in <ul>…</ul> (mirroring watch.<FUND>)."""
    html = _html(fundmaster_4fund)
    for key in ("strategy.distribution", "strategy.rebalancing", "strategy.dip_capture"):
        # Still LLM-owned prose (fake mode emits the placeholder), inside a <ul>.
        assert f"<ul>[{key} narrative]</ul>" in html
        # Not Python-substituted away / not a leftover marker.
        assert f"slot:{key}" not in html

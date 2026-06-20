"""Adversarial guard for the Track-0 determinism thesis (findings C1 + C2).

Each test pairs a *positive* assertion (real pipeline output is consistent by
construction) with an *adversarial* one (a single corrupted figure trips the
guard). These tests would have caught the original bugs:

  C1 — ``check_cfs_consistency`` was vacuous on engine output because the
       composite was not wrapped in ``<span class="cfs-score">``.
  C2 — performance rows, fund metadata, and macro Event/Date cells were routed
       through the LLM as prose, so a hallucinated figure/date passed silently.
       They are now engine-rendered facts.

Runs offline via the autouse fake-LLM fixture in tests/conftest.py.
"""
import re

import consultant_engine
from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.macro_context import macro_context
from consultant_engine.nodes.generate_proposal import generate_proposal
from consultant_engine.templates import render_structural_card
from consultant_engine.rules.validation import (
    check_alpha_warning,
    check_cfs_consistency,
    check_perf_consistency,
    check_summary_consistency,
    validate_html,
    workbook_index,
)


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


# ── C1 — CFS-transcription guard is live (not vacuous) ───────────────────────

def test_c1_cfs_score_span_present_and_consistent(fundmaster_4fund):
    """Engine output wraps the composite in a cfs-score span, so the guard
    actually fires, and the numbers it recomputes are consistent."""
    html = _html(fundmaster_4fund)
    assert 'class="cfs-score"' in html
    assert check_cfs_consistency(html) == []


def test_c1_corrupted_composite_is_caught(fundmaster_4fund):
    """Knock one composite off by >2 → cfs_recompute violation.

    Before the C1 fix this test FAILS: the composite lived in a bare
    cfs-title div with no cfs-score span, so check_cfs_consistency skipped
    every card and returned [] even on corruption.
    """
    html = _html(fundmaster_4fund)

    def _bump(m):
        return f'<span class="cfs-score">{float(m.group(1)) + 30}</span>'

    corrupted, n = re.subn(
        r'<span class="cfs-score">([\d.]+)</span>', _bump, html, count=1
    )
    assert n == 1, "expected at least one cfs-score span to corrupt"

    codes = {v["code"] for v in check_cfs_consistency(corrupted)}
    assert "cfs_recompute" in codes

    idx = workbook_index(fundmaster_4fund)
    codes_full = {v["code"] for v in
                  validate_html(corrupted, consultant_engine.__version__, idx)}
    assert "cfs_recompute" in codes_full


# ── C2a — per-fund performance rows are Python-rendered ──────────────────────

def test_c2a_perf_rows_are_rendered_facts(fundmaster_4fund):
    """The perf table holds real numeric cells (no prose placeholder, no
    leftover slot marker) and Alpha == Fund - Bench by construction."""
    html = _html(fundmaster_4fund)
    assert '<table class="perf-table">' in html
    assert "perf.PGA.rows" not in html          # no prose marker survives
    assert "narrative]" not in _first_perf_table(html)
    assert re.search(r"<td>3Y</td>", html)       # a real period label row
    assert check_perf_consistency(html) == []


def test_c2a_corrupted_perf_alpha_is_caught(fundmaster_4fund):
    """Corrupt one Fund cell so Alpha no longer equals Fund - Bench →
    perf_recompute violation. Before C2a these were LLM prose, so a wrong
    figure would never have been recomputed."""
    html = _html(fundmaster_4fund)
    # PGA 3Y row: fund=15, bench=11, alpha=+4. Break the fund cell to 25.
    corrupted, n = re.subn(
        r"(<tr><td>3Y</td><td>)15(</td>)", r"\g<1>25\g<2>", html, count=1
    )
    assert n == 1, "expected the PGA 3Y perf row to be present"
    codes = {v["code"] for v in check_perf_consistency(corrupted)}
    assert "perf_recompute" in codes


# ── C2b — fund metadata is Python-rendered ───────────────────────────────────

def test_c2b_meta_cells_are_rendered_facts(fundmaster_4fund):
    """Type / Shariah / Lipper / VF render real values, no prose markers."""
    html = _html(fundmaster_4fund)
    assert "<strong>Type:</strong> Equity" in html
    assert "<strong>Shariah:</strong> Conventional" in html   # fixture funds are conventional
    assert "meta.PGA.type" not in html
    assert "meta.PGA.shariah" not in html
    assert "meta.PGA.lipper" not in html


# ── C2c — macro Event + Date cells are Python-rendered ───────────────────────

def test_c2c_macro_rows_carry_real_event_and_date(fundmaster_4fund):
    """Macro rows carry the fixture's real claim text and a formatted date;
    the Implication cell stays a prose slot (filled by the fake LLM)."""
    html = _html(fundmaster_4fund)
    # A known claim substring from consultant_engine/assets/macro_fixture.json:
    assert "BNM held the OPR at 3.00%" in html
    # ISO date 2026-06-01 formatted as "01 Jun 2026":
    assert "01 Jun 2026" in html
    # The events-row marker is consumed (not left as a prose placeholder):
    assert "macro.events_rows" not in html
    assert "[macro.events_rows narrative]" not in html


# ── M-new — Portfolio Summary CFS is cross-checked against the fund cards ─────

def test_m_new_summary_cfs_cross_checked(fundmaster_4fund):
    """The Portfolio Summary CFS column is consistent with each fund card's
    composite by construction; corrupting a summary cell trips summary_mismatch."""
    html = _html(fundmaster_4fund)
    assert check_summary_consistency(html) == []           # consistent by construction

    # Corrupt PGA's Portfolio Summary CFS cell (4th <td>) so it disagrees with its card.
    corrupted, n = re.subn(
        r"(<tr><td>PGA</td><td>[^<]*</td><td>[^<]*</td><td>)[\d.]+(</td>)",
        r"\g<1>1.0\g<2>", html, count=1,
    )
    assert n == 1, "expected a PGA Portfolio Summary row to corrupt"

    codes = {v["code"] for v in check_summary_consistency(corrupted)}
    assert "summary_mismatch" in codes

    idx = workbook_index(fundmaster_4fund)
    codes_full = {v["code"] for v in
                  validate_html(corrupted, consultant_engine.__version__, idx)}
    assert "summary_mismatch" in codes_full


# ── Structural alpha-warning disclosure gate is Python-owned (not LLM-repaired) ─

def test_structural_disqualified_card_satisfies_gate_without_llm():
    """A Disqualified *structural* fund's card satisfies check_alpha_warning by
    Python render alone — no LLM repair needed.

    Before Fix A the structural templates emitted no warning div, so a disqualified
    gold/MM sleeve (PeEMAS is Disqualified in the live Jun-2026 book) tripped the
    `alpha_warning` gate and only the real-LLM repair step could inject the div — a
    hole in the determinism thesis that FAKE_LLM runs could not converge through.
    """
    card = render_structural_card(
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeEMAS", "name": "Public e-EMAS", "status": "Disqualified"},
    )
    idx = {"PeEMAS": {"status": "Disqualified", "name": "Public e-EMAS"}}
    # Python emitted the div, so the disclosure gate passes with zero LLM involvement.
    assert check_alpha_warning(card, idx) == []

    # Adversarial inverse: strip the div Python emitted → the gate must fire.
    stripped = card.replace(
        '<div class="alpha-warning"><!--slot:alpha_warning.PeEMAS--></div>', ""
    )
    codes = {v["code"] for v in check_alpha_warning(stripped, idx)}
    assert "alpha_warning" in codes


def _first_perf_table(html: str) -> str:
    m = re.search(r'<table class="perf-table">.*?</table>', html, re.DOTALL)
    return m.group(0) if m else ""

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
from consultant_engine.templates import render_alpha_warning, render_structural_card
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
    Python render alone — no LLM repair, and now with no LLM prose slot either.

    Before Fix A the structural templates emitted no warning div, so a disqualified
    gold/MM sleeve (PeEMAS is Disqualified in the live Jun-2026 book) tripped the
    `alpha_warning` gate and only the real-LLM repair step could inject the div — a
    hole in the determinism thesis that FAKE_LLM runs could not converge through.
    Group 3 then made the inner text a static Python string (no `<!--slot:--> marker).
    """
    card = render_structural_card(
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeEMAS", "name": "Public e-EMAS", "status": "Disqualified"},
    )
    idx = {"PeEMAS": {"status": "Disqualified", "name": "Public e-EMAS"}}
    # Python emitted the div, so the disclosure gate passes with zero LLM involvement.
    assert check_alpha_warning(card, idx) == []

    # The div now carries static Python text, not an LLM prose slot marker.
    assert "<!--slot:alpha_warning" not in card
    assert "Disqualified" in card
    assert "10%" in card                       # allocation interpolated by Python

    # Adversarial inverse: strip the whole alpha-warning div → the gate must fire.
    stripped = re.sub(r'<div class="alpha-warning">.*?</div>', "", card, flags=re.DOTALL)
    assert '<div class="alpha-warning">' not in stripped
    codes = {v["code"] for v in check_alpha_warning(stripped, idx)}
    assert "alpha_warning" in codes


def test_render_alpha_warning_role_specific_clauses():
    """render_alpha_warning emits the disqualification lead plus the role-specific
    clause, with the allocation interpolated — and never an LLM prose slot marker."""
    lead = "weighted alpha &le; 0%"

    gold = render_alpha_warning("structural:gold", 10)
    assert gold.startswith('<div class="alpha-warning">') and gold.endswith("</div>")
    assert lead in gold
    assert "Held at 10% as a structural gold / inflation hedge" in gold
    assert "<!--slot:alpha_warning" not in gold

    mm = render_alpha_warning("structural:money_market", 5)
    assert lead in mm
    assert "Held at 5% as a structural liquidity reserve" in mm
    assert "<!--slot:alpha_warning" not in mm

    # Any other role (core/alpha) → generic diversifier clause.
    for role in ("core", "alpha:equity"):
        core = render_alpha_warning(role, 30)
        assert lead in core
        assert "Included at 30% as a diversifier" in core
        assert "<!--slot:alpha_warning" not in core


def test_pipeline_disqualified_structural_shows_static_text_no_slot():
    """A full proposal whose portfolio holds a Disqualified structural (gold) fund
    shows the static Python disclosure text and carries NO alpha_warning slot marker
    anywhere — the key never reaches the LLM / FAKE_LLM fill."""
    state = {
        "client_profile": {
            "risk_level": "Moderate", "shariah": False, "experience": "new",
            "target_annual_return_pct": 8.0,
        },
        "fundmaster_path": "/x/PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
        "portfolio": [
            {"abbr": "PGA", "role": "core", "allocation_pct": 90},
            {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        ],
        "cfs_scores": [{"abbr": "PGA", "composite": 80, "alpha_n": 70}],
        "eligible_funds": [
            {"abbr": "PGA", "name": "Public Growth A", "risk_level": 3,
             "status": "Qualified"},
            {"abbr": "PeEMAS", "name": "Public e-Islamic EMAS", "risk_level": 3,
             "status": "Disqualified"},
        ],
        "macro_context": {"events": []},
    }
    html = generate_proposal(state)["proposal_html"]

    # No alpha_warning slot marker survives anywhere in the document.
    assert "<!--slot:alpha_warning" not in html
    assert "alpha_warning" not in html          # not even as a FAKE_LLM placeholder key

    # The static Python disclosure text is present, scoped to the gold sleeve.
    assert '<div class="alpha-warning">' in html
    assert "weighted alpha &le; 0%" in html
    assert "Held at 10% as a structural gold / inflation hedge" in html


def test_cover_data_source_month_is_workbook_not_llm(fundmaster_4fund):
    """Cover 'Data Source: FundMaster <month>' = the source workbook's vintage, Python-
    derived from its filename — never an LLM-authored guess (which used to stamp today's
    month onto the cover and break workbook resolution in the proposal validator)."""
    from consultant_engine.nodes.generate_proposal import _workbook_month_year
    assert _workbook_month_year("/x/PublicMutual_FundMaster_Apr2026_v1.7.xlsx") == "Apr 2026"
    html = _html(fundmaster_4fund)               # fixture workbook is ..._Jun2026_v0.1.0.xlsx
    assert "FundMaster Jun 2026" in html
    assert "slot:cover.fundmaster_month_year" not in html   # not left to the LLM


def _first_perf_table(html: str) -> str:
    m = re.search(r'<table class="perf-table">.*?</table>', html, re.DOTALL)
    return m.group(0) if m else ""


# ── Group 4 — §9 Sources & References are Python-owned (not LLM prose) ────────

def test_sources_fundmaster_is_python_owned(fundmaster_4fund):
    """The §9 FundMaster citation carries the source workbook basename + its 'Jun
    2026' vintage as a Python-rendered <code> fact — never an LLM prose slot."""
    html = _html(fundmaster_4fund)
    # fixture workbook is ..._Jun2026_v0.1.0.xlsx
    assert "<code>PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx</code>" in html
    assert "(MFR data, Jun 2026)" in html
    assert "slot:sources.fundmaster" not in html               # not left to the LLM
    assert "[sources.fundmaster narrative]" not in html        # no FAKE_LLM placeholder


def test_sources_phs_list_is_one_li_per_fund(fundmaster_4fund):
    """One <li> PHS citation per portfolio holding, abbr-keyed; marker consumed."""
    state = _pipeline(fundmaster_4fund)
    html = state["proposal_html"]
    portfolio = state["portfolio"]
    for h in portfolio:
        assert (
            f"<li>Product Highlight Sheet &mdash; <code>{h['abbr']}_PHS.pdf</code></li>"
            in html
        )
    # Exactly one PHS <li> per fund (no duplicates, no missing).
    assert html.count("Product Highlight Sheet &mdash; <code>") == len(portfolio)
    assert "slot:sources.phs_list" not in html
    assert "[sources.phs_list narrative]" not in html


def test_sources_web_urls_render_each_unique_macro_url(fundmaster_4fund):
    """Each macro event's real source_url renders once as an <a href=…>; marker gone."""
    state = _pipeline(fundmaster_4fund)
    html = state["proposal_html"]
    urls = [ev["source_url"] for ev in state["macro_context"]["events"]]
    assert urls, "fixture should carry macro events"
    for url in dict.fromkeys(urls):                # unique, order-preserving
        assert f'<a href="{url}">' in html
        assert html.count(f'href="{url}"') == 1    # exactly once
    assert "slot:sources.web_urls" not in html
    assert "[sources.web_urls narrative]" not in html


# ── _source_facts unit tests — dedup + empty-events behavior ──────────────────

def _state_with_events(events):
    return {
        "fundmaster_path": "/x/PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
        "portfolio": [{"abbr": "PGA", "role": "core", "allocation_pct": 100}],
        "macro_context": {"events": events},
    }


def test_source_facts_dedupes_shared_url():
    """Two events sharing one URL → a single <li>, labelled by the first event."""
    from consultant_engine.nodes.generate_proposal import _source_facts
    events = [
        {"date": "2026-06-01", "theme": "rates",
         "claim": "x", "source_url": "https://example.com/a"},
        {"date": "2026-06-10", "theme": "ringgit",
         "claim": "y", "source_url": "https://example.com/a"},   # same URL
    ]
    web = _source_facts(_state_with_events(events))["<!--slot:sources.web_urls-->"]
    assert web.count("<li>") == 1
    assert web.count('href="https://example.com/a"') == 1
    # first-seen event supplies the label
    assert "rates (2026-06-01)" in web
    assert "ringgit" not in web


def test_source_facts_empty_events_renders_nothing():
    """No macro events → empty web_urls string (no <li>, no invented URL, no crash)."""
    from consultant_engine.nodes.generate_proposal import _source_facts
    facts = _source_facts(_state_with_events([]))
    assert facts["<!--slot:sources.web_urls-->"] == ""
    # the other two facts still render
    assert "PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx" in facts["<!--slot:sources.fundmaster-->"]
    assert "PGA_PHS.pdf" in facts["<!--slot:sources.phs_list-->"]


def test_source_facts_missing_macro_context_does_not_crash():
    """A state with no macro_context key → web_urls empty, no KeyError."""
    from consultant_engine.nodes.generate_proposal import _source_facts
    state = {
        "fundmaster_path": "/x/PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
        "portfolio": [{"abbr": "PGA", "role": "core", "allocation_pct": 100}],
    }
    assert _source_facts(state)["<!--slot:sources.web_urls-->"] == ""


# ── Group 2 — the display-only portfolio-VF surface is removed ────────────────

def test_portfolio_vf_surface_removed_but_per_fund_vf_kept(fundmaster_4fund):
    """The portfolio-level VF surface was display-only (its data-slot was a hardcoded
    dash and the class/range were LLM-invented decoration). Group 2 removes it
    entirely — no leftover slot markers, no exec/footer VF labels — while the per-fund
    card VF (a real workbook value) stays."""
    html = _html(fundmaster_4fund)

    # None of the three portfolio-VF slot markers survive anywhere.
    assert "portfolio.volatility_factor" not in html
    assert "portfolio.volatility_class" not in html
    assert "profile.target_vf_range" not in html

    # Neither the §1 exec clause nor the §5 footer label remains.
    assert "Portfolio VF" not in html          # also covers "Weighted Portfolio VF"
    assert "Weighted Portfolio VF" not in html

    # The per-fund card VF (a real workbook value) is preserved.
    assert "<strong>VF:</strong>" in html

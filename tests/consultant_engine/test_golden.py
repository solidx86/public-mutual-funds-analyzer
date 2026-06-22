"""tests/consultant_engine/test_golden.py — Task 5.3

Golden structural-parity anchor.  Generates a proposal via the engine
(fake-LLM) and asserts it shares the canonical golden's LOCKED structure —
9 sections in order, 4 disclaimer headings, 9 section divs.

Complements tests/test_proposal_validation.py (cross-checks real output files
against the FundMaster workbook). This test targets the *engine path* itself
so that structural drift is caught before any file is written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.generate_proposal import generate_proposal
from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.macro_context import macro_context
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.rules.validation import (
    LOCKED_SECTIONS,
    check_sections,
)

GOLDEN = Path("output/examples/fund_proposals/FundProposal_generic_Moderate_2026-06-22_v0.1.0.html")

_DISCLOSURE_HEADINGS = [
    "AI-Generated Document",
    "Regulatory Disclaimer",
    "Cooling-Off Right",
    "Conflict of Interest",
]


def _engine_html(fundmaster_4fund: str) -> str:
    """Run the engine pipeline (fake-LLM) and return the generated proposal HTML."""
    s: dict = {
        "client_profile": {"risk_level": "Moderate", "shariah": False},
        "fundmaster_path": fundmaster_4fund,
        "macro_context": {"source": "fixture"},
    }
    for step in (
        load_profile,
        load_funds,
        filter_universe,
        score_cfs,
        build_portfolio,
        macro_context,
        generate_proposal,
    ):
        s.update(step(s))
    return s["proposal_html"]


def test_golden_itself_passes_section_check():
    """Sanity-check: the golden file itself must satisfy check_sections."""
    golden_html = GOLDEN.read_text(encoding="utf-8")
    violations = check_sections(golden_html)
    assert violations == [], f"Golden failed check_sections: {violations}"


def test_engine_matches_golden_section_order(fundmaster_4fund):
    """Both golden and engine output must contain all 9 LOCKED_SECTIONS in order."""
    golden_html = GOLDEN.read_text(encoding="utf-8")
    engine_html = _engine_html(fundmaster_4fund)

    # Use the same extraction the validator uses (section-title divs, ordered)
    def _section_titles(html: str) -> list[str]:
        return re.findall(r'<div class="section-title">([^<]+)</div>', html)

    golden_titles = _section_titles(golden_html)
    engine_titles = _section_titles(engine_html)

    assert golden_titles == LOCKED_SECTIONS, (
        f"Golden section titles drifted from LOCKED_SECTIONS: {golden_titles}"
    )
    assert engine_titles == LOCKED_SECTIONS, (
        f"Engine section titles drifted from LOCKED_SECTIONS: {engine_titles}"
    )


def test_engine_matches_golden_disclaimer_and_section_count(fundmaster_4fund):
    """Engine and golden must both have 4 disclosure headings and 9 section divs."""
    engine_html = _engine_html(fundmaster_4fund)
    golden_html = GOLDEN.read_text(encoding="utf-8")

    # 4 disclosure headings present in both
    for heading in _DISCLOSURE_HEADINGS:
        assert heading in engine_html, f"Engine missing disclosure heading: {heading!r}"
        assert heading in golden_html, f"Golden missing disclosure heading: {heading!r}"

    # Exactly 9 <div class="section"> divs in both
    engine_div_count = engine_html.count('<div class="section"')
    golden_div_count = golden_html.count('<div class="section"')
    assert engine_div_count == 9, (
        f"Engine has {engine_div_count} section divs, expected 9"
    )
    assert golden_div_count == 9, (
        f"Golden has {golden_div_count} section divs, expected 9"
    )


def test_engine_passes_check_sections(fundmaster_4fund):
    """Engine output must pass the validator's check_sections rule with zero violations."""
    engine_html = _engine_html(fundmaster_4fund)
    violations = check_sections(engine_html)
    assert violations == [], f"Engine proposal failed check_sections: {violations}"

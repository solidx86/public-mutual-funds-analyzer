"""Tests for consultant_engine/nodes/generate_proposal.py — Task 3.5.

Run under fake-LLM (CONSULTANT_ENGINE_FAKE_LLM=1) so CI stays offline.
"""
import re

import pytest

from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.generate_proposal import generate_proposal
from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.macro_context import macro_context
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.rules.validation import check_exposure_consistency


def _state():
    return {
        "client_profile": {
            "risk_level": "Moderate",
            "experience": "experienced",
            "shariah": False,
            "e_target": 5.0,
            "upfront_capital_rm": 50000,
        },
        "fundmaster_path": "output/fundmasters/PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
        "macro_context": {"events": []},
        "portfolio": [
            {"abbr": "PGA", "role": "core", "allocation_pct": 41.0},
            {"abbr": "PBA", "role": "core", "allocation_pct": 33.0},
            {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 11.0},
            {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 15.0},
        ],
        "cfs_scores": [
            {
                "abbr": "PGA",
                "composite": 88.0,
                "alpha_n": 95,
                "returnfit_n": 90,
                "efficiency_n": 80,
                "momentum_n": 95,
                "derived_class": "Equity-equivalent",
                "weights": {"alpha": 28, "returnfit": 40, "efficiency": 20, "momentum": 12},
            },
            {
                "abbr": "PBA",
                "composite": 80.0,
                "alpha_n": 70,
                "returnfit_n": 85,
                "efficiency_n": 60,
                "momentum_n": 90,
                "derived_class": "Equity-equivalent",
                "weights": {"alpha": 28, "returnfit": 40, "efficiency": 20, "momentum": 12},
            },
        ],
        "eligible_funds": [
            {"abbr": "PGA", "name": "Public Growth A", "risk_level": 3},
            {"abbr": "PBA", "name": "Public Balanced A", "risk_level": 3},
            {"abbr": "PeEMAS", "name": "Public e-EMAS", "risk_level": 3},
            {"abbr": "PeCDF-A", "name": "Public e-Cash Deposit A", "risk_level": 1},
        ],
    }


def _state_new_investor():
    s = _state()
    s["client_profile"]["experience"] = "new"
    return s


class TestGenerateProposalFakeLLM:
    """Core contract under fake-LLM mode (offline)."""

    def test_generate_under_fake_llm(self, monkeypatch):
        """generate_proposal returns a valid HTML string with 9 sections, version stamp,
        PGA composite number, and no unresolved template placeholders."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]

        assert "<div class=\"section\"" in html
        assert html.count("<div class=\"section\"") == 9          # 9 numbered sections
        assert "0.1.0" in html                                     # version stamp present
        assert "{{" not in html                                    # no unresolved {{...}} placeholders
        assert "<!--slot:" not in html                             # no unfilled prose slot markers
        assert "88" in html                                        # PGA composite number transcribed

    def test_returns_dict_with_proposal_html_key(self, monkeypatch):
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        assert isinstance(out, dict)
        assert "proposal_html" in out
        assert isinstance(out["proposal_html"], str)
        assert len(out["proposal_html"]) > 1000  # not a stub

    def test_no_prose_slot_markers_remain(self, monkeypatch):
        """All <!--slot:KEY--> prose markers must be replaced (not left as-is)."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]
        assert "<!--slot:" not in html, (
            "Unresolved <!--slot:--> prose markers remain in output"
        )

    def test_experienced_investor_excludes_foundation_block(self, monkeypatch):
        """Experienced investor proposals must NOT include the Foundation block."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]
        assert "<!--FOUNDATION_START-->" not in html
        assert "<!--FOUNDATION_END-->" not in html
        assert "Before We Start" not in html  # Foundation h2

    def test_new_investor_includes_foundation_block(self, monkeypatch):
        """New investor proposals MUST include the Foundation block content."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state_new_investor())
        html = out["proposal_html"]
        # Markers stripped but content kept
        assert "<!--FOUNDATION_START-->" not in html
        assert "<!--FOUNDATION_END-->" not in html
        assert "Before We Start" in html  # Foundation h2 present

    def test_portfolio_allocation_percentages_present(self, monkeypatch):
        """Allocation percentages from the portfolio must appear in the HTML."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]
        assert "41" in html   # PGA allocation
        assert "33" in html   # PBA allocation
        assert "11" in html   # PeEMAS allocation
        assert "15" in html   # PeCDF-A allocation

    def test_structural_cards_present(self, monkeypatch):
        """Gold and money-market structural cards must be rendered (from render_structural_card)."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]
        assert "PeEMAS" in html       # gold fund present
        assert "PeCDF-A" in html      # money-market fund present
        assert "Public e-EMAS" in html

    def test_cover_e_target_slot_filled(self, monkeypatch):
        """cover.e_target numeric slot must be filled with the client's e_target."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]
        # Should show 5.0 (the e_target from state)
        assert "5.0" in html or "5%" in html

    def test_html_is_valid_document(self, monkeypatch):
        """Output must be a complete HTML document starting with DOCTYPE."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]
        assert html.strip().startswith("<!DOCTYPE html")
        assert "</html>" in html


def _engine_html(fundmaster_path: str) -> str:
    """Run the deterministic node pipeline (fake-LLM) end-to-end."""
    s: dict = {
        "client_profile": {"risk_level": "Moderate", "shariah": False},
        "fundmaster_path": fundmaster_path,
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


class TestPortfolioExposureSection:
    """Deterministic Portfolio Exposure (Section 6) — Python owns the numbers."""

    def test_exposure_pies_rendered_in_both_blocks(self, monkeypatch, fundmaster_exposure):
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        # Both exposure blocks must carry a real conic-gradient pie.
        assert html.count("conic-gradient(") >= 2
        # No leftover prose-slot markers for exposure.
        assert "<!--slot:exposure" not in html
        assert "exposure.asset_class.pie_chart narrative]" not in html
        assert "exposure.geo.legend_items narrative]" not in html

    def test_asset_class_pcts_are_real_numbers(self, monkeypatch, fundmaster_exposure):
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        # The 5 asset-class data-slot spans must be real "NN.N%" — never "—".
        spans = re.findall(
            r'data-slot="exposure\.asset\.[a-z_]+_pct"\s*>([^<]*)<', html
        )
        assert len(spans) == 5
        for val in spans:
            assert "—" not in val and "&mdash;" not in val, spans
            assert re.fullmatch(r"\d+(?:\.\d+)?%", val.strip()), spans

    def test_geo_legend_has_real_country_labels(self, monkeypatch, fundmaster_exposure):
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        # Malaysia (dom-equity proxy) and at least one foreign country must appear.
        assert ">Malaysia<" in html
        assert ">USA<" in html

    def test_exposure_blocks_pass_consistency_guard(self, monkeypatch, fundmaster_exposure):
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        assert check_exposure_consistency(html) == []

    def test_exposure_graceful_without_geo_or_assets(self, monkeypatch, fundmaster_4fund):
        """The 4-fund fixture has assets but blank geo headers — must still render
        consistent blocks (no crash, guard clean)."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_4fund)
        assert html.count("conic-gradient(") >= 2
        assert check_exposure_consistency(html) == []

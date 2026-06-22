"""Tests for consultant_engine/nodes/generate_proposal.py — Task 3.5.

Run under fake-LLM (CONSULTANT_ENGINE_FAKE_LLM=1) so CI stays offline.
"""
import re

import pytest

from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.generate_proposal import (
    _compute_portfolio_metrics,
    generate_proposal,
)
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
            "target_annual_return_pct": 5.0,
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

    def test_cover_target_annual_return_pct_slot_filled(self, monkeypatch):
        """cover.target_annual_return_pct numeric slot must be filled with the client's target_annual_return_pct."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal(_state())
        html = out["proposal_html"]
        # Should show 5.0 (the target_annual_return_pct from state)
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


def _exposure_block(html: str, title: str) -> str:
    """Isolate one ``.exposure-chart-block`` (Asset Class / Geographic) by title."""
    m = re.search(
        r'exposure-chart-title">' + re.escape(title) + r'<.*?'
        r'(?=<div class="exposure-chart-block">|</div>\s*</div>\s*<!--|$)',
        html,
        re.DOTALL,
    )
    assert m, f"exposure block {title!r} not found"
    return m.group(0)


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
        # The asset-class legend (now a generated block) must carry real "NN.N%"
        # percentages — never "—". Read from inside the Asset Class chart block.
        block = _exposure_block(html, "Asset Class")
        pcts = re.findall(r'class="legend-pct">([^<]*)<', block)
        assert pcts, "Asset Class legend has no percentage rows"
        for val in pcts:
            assert "—" not in val and "&mdash;" not in val, pcts
            assert re.fullmatch(r"\d+(?:\.\d+)?%", val.strip()), pcts

    def test_geo_legend_has_real_country_labels(self, monkeypatch, fundmaster_exposure):
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        # Malaysia (dom-equity proxy) and at least one foreign country must appear.
        assert ">Malaysia<" in html
        assert ">USA<" in html

    def test_geo_not_collapsed_to_all_other(self, monkeypatch, fundmaster_exposure):
        """Bug 1 regression: geo headers carry a ' (%)' suffix in the real workbook;
        the look-through must still hit real country buckets, not dump 100% into
        'Other'. (The bare-name lookup used to miss every suffixed key.)"""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        block = _exposure_block(html, "Geographic")
        rows = re.findall(
            r'legend-label">([^<]*)</span><span class="legend-pct">([^<]*)<', block
        )
        by_label = {lbl: float(pct.rstrip("%")) for lbl, pct in rows}
        # Real countries must be populated and 'Other' must not be ~100.
        assert by_label.get("USA", 0.0) > 0.0, by_label
        assert by_label.get("Other", 100.0) < 50.0, by_label
        assert abs(sum(by_label.values()) - 100.0) <= 2.0, by_label

    def test_gold_attributed_via_structural_role(self, monkeypatch, fundmaster_exposure):
        """Bug 2 regression: PeEMAS (structural:gold) must contribute its full
        weighted allocation to the Gold slice — not leak into foreign equity — and
        the Gold slice must be non-zero."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        block = _exposure_block(html, "Asset Class")
        rows = re.findall(
            r'legend-label">([^<]*)</span><span class="legend-pct">([^<]*)<', block
        )
        by_label = {lbl: float(pct.rstrip("%")) for lbl, pct in rows}
        assert by_label.get("Gold / Other", 0.0) > 0.0, by_label
        assert abs(sum(by_label.values()) - 100.0) <= 2.0, by_label

    def test_zero_pct_legend_rows_omitted(self, monkeypatch, fundmaster_exposure):
        """Bug 3 regression: truly-0% rows must not render in either legend."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        html = _engine_html(fundmaster_exposure)
        for title in ("Asset Class", "Geographic"):
            block = _exposure_block(html, title)
            pcts = re.findall(r'class="legend-pct">([^<]*)<', block)
            assert "0.0%" not in pcts, (title, pcts)

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


class TestWeightedAlpha3Y:
    """The reported '3Y Alpha' is the allocation-weighted 3Y alpha RETURN, not the
    alpha_n CFS score (a 0–100 percentile) — guards a prior mislabel where the score
    was rendered as '88.4% p.a.'."""

    def _funds(self, pga_alpha, gold_alpha):
        return [
            {"abbr": "PGA", "name": "Public Growth A", "risk_level": 3,
             "returns": {"3y": {"alpha": pga_alpha}}},
            {"abbr": "PeEMAS", "name": "Public e-EMAS", "risk_level": 3,
             "returns": {"3y": {"alpha": gold_alpha}}},
        ]

    def _portfolio(self):
        return [
            {"abbr": "PGA", "role": "core", "allocation_pct": 50.0},
            {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 50.0},
        ]

    def test_uses_return_not_alpha_n_score(self):
        cfs = [{"abbr": "PGA", "composite": 88.0, "alpha_n": 95}]  # score is high
        m = _compute_portfolio_metrics(self._portfolio(), cfs, self._funds(10.0, -2.0))
        # 0.5*10 + 0.5*(-2) = 4.0 — the structural gold sleeve's negative alpha drags it down.
        assert m["weighted_alpha_3y"] == "4.0"
        # NOT the alpha_n blend (0.5*95 = 47.5) nor the lone core score.
        assert m["weighted_alpha_3y"] != "47.5"
        assert "weighted_alpha" not in m  # old score key is gone

    def test_missing_3y_alpha_contributes_zero(self):
        funds = self._funds(12.0, None)
        funds[1]["returns"] = {}  # gold sleeve has no 3y track record
        m = _compute_portfolio_metrics(self._portfolio(), [], funds)
        assert m["weighted_alpha_3y"] == "6.0"  # 0.5*12 + 0.5*0

    def test_summary_alpha_is_plausible_return_not_percentile(self, monkeypatch, fundmaster_4fund):
        """End-to-end: the rendered '3Y Alpha' must be a believable return (single-
        digit-to-teens here), never an 80–100 percentile, and must not claim 'p.a.'."""
        monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
        out = generate_proposal({
            "client_profile": {"risk_level": "Moderate", "experience": "experienced",
                               "shariah": False, "target_annual_return_pct": 5.0,
                               "upfront_capital_rm": 50000},
            "fundmaster_path": fundmaster_4fund,
            "macro_context": {"events": []},
            "portfolio": [
                {"abbr": "PGA", "role": "core", "allocation_pct": 60.0},
                {"abbr": "PBA", "role": "core", "allocation_pct": 40.0},
            ],
            "cfs_scores": [
                {"abbr": "PGA", "composite": 88.0, "alpha_n": 95, "returnfit_n": 90,
                 "efficiency_n": 80, "momentum_n": 95, "derived_class": "Equity-equivalent",
                 "weights": {"alpha": 28, "returnfit": 40, "efficiency": 20, "momentum": 12}},
                {"abbr": "PBA", "composite": 80.0, "alpha_n": 70, "returnfit_n": 85,
                 "efficiency_n": 60, "momentum_n": 90, "derived_class": "Equity-equivalent",
                 "weights": {"alpha": 28, "returnfit": 40, "efficiency": 20, "momentum": 12}},
            ],
            "eligible_funds": load_funds({"fundmaster_path": fundmaster_4fund})["eligible_funds"],
        })["proposal_html"]
        # 3y alphas in the 4-fund fixture: PGA=4.0, PBA=3.0 → 0.6*4 + 0.4*3 = 3.6
        m = re.search(r"3Y Alpha:</strong>\s*<span[^>]*>([\d.]+)</span>%", out)
        assert m, "summary 3Y Alpha line not found"
        assert float(m.group(1)) == 3.6
        # The alpha figure must NOT carry a 'p.a.' annualization claim (the target
        # annual return elsewhere legitimately does — so scope the check to alpha).
        assert not re.search(r"3Y Alpha:</strong>\s*<span[^>]*>[\d.]+</span>%\s*p\.a\.", out)


def test_prepared_for_renders_escaped_when_named(monkeypatch):
    monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
    s = _state()
    s["client_profile"]["client_name"] = "Tan <b>Wei</b> Ming"
    html_out = generate_proposal(s)["proposal_html"]
    assert 'class="cover-prepared-for"' in html_out
    assert "Prepared for <strong>Tan &lt;b&gt;Wei&lt;/b&gt; Ming</strong>" in html_out
    assert "<!--slot:cover.prepared_for_block-->" not in html_out


def test_prepared_for_absent_when_generic(monkeypatch):
    monkeypatch.setenv("CONSULTANT_ENGINE_FAKE_LLM", "1")
    html_out = generate_proposal(_state())["proposal_html"]   # _state() has no client_name
    # CSS embeds ".cover-prepared-for" always; check the *element* is absent, not the class name
    assert '<div class="cover-prepared-for">' not in html_out
    assert "Prepared for <strong>" not in html_out
    assert "<!--slot:cover.prepared_for_block-->" not in html_out

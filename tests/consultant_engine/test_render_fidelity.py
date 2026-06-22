"""Tests for the render-fidelity reconciliation check (runtime ``validate`` node).

The determinism boundary reserves every number/structure/meta value for Python;
the LLM authors only prose. BUT the repair pass round-trips the WHOLE document
through the LLM ("return the complete HTML"), so the model CAN corrupt a
Python-owned value (a CFS number, a Shariah label, an allocation %). The
``validate`` node sees the final post-repair HTML AND holds the authoritative
engine state in memory — so ``check_render_fidelity(html, state)`` reconciles the
rendered Python-owned values against the engine's OWN single source of truth.

This is reconciliation, NOT re-derivation: authoritative values come from state
(cfs_scores, portfolio, eligible_funds) or by REUSING the production compute
functions (compute_asset_exposure / compute_geo_exposure / _compute_portfolio_metrics).
"""

import re

import pytest

from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.macro_context import macro_context
from consultant_engine.nodes.generate_proposal import generate_proposal
from consultant_engine.nodes.validate import validate
from consultant_engine.rules.validation import check_render_fidelity


def _pipeline(fundmaster_path):
    """Run the deterministic node pipeline (fake-LLM) end-to-end; return final state."""
    s = {
        "client_profile": {"risk_level": "Moderate", "shariah": False},
        "fundmaster_path": fundmaster_path,
        "macro_context": {"source": "fixture"},
    }
    for step in (
        load_profile,
        load_funds,
        filter_universe,
        score_cfs,
        macro_context,
        build_portfolio,
        generate_proposal,
    ):
        s.update(step(s))
    return s


# ── Clean run: zero render-fidelity violations (false-positive guard) ──────────


def test_clean_proposal_has_no_render_fidelity_violations(fundmaster_exposure):
    s = _pipeline(fundmaster_exposure)
    assert check_render_fidelity(s["proposal_html"], s) == []


def test_clean_proposal_validate_node_clean(fundmaster_exposure):
    """The validate node (which calls check_render_fidelity with state) is clean."""
    s = _pipeline(fundmaster_exposure)
    out = validate(s)
    codes = {v["code"] for v in out["violations"]}
    assert "RENDER_FIDELITY" not in codes, out["violations"]
    assert out["violations"] == [], out["violations"]


def test_clean_proposal_4fund_no_render_fidelity(fundmaster_4fund):
    """The 4-fund fixture (assets, blank geo) also reconciles clean."""
    s = _pipeline(fundmaster_4fund)
    assert check_render_fidelity(s["proposal_html"], s) == []


# ── Adversarial: corrupt ONE Python-owned value, assert the check fires ────────


def test_corrupted_cfs_composite_is_caught(fundmaster_exposure):
    """A fund-card CFS composite drifted from state["cfs_scores"] → RENDER_FIDELITY."""
    s = _pipeline(fundmaster_exposure)
    html = s["proposal_html"]
    # PGA's composite is 79.4 in the good render — shove it to 19.4 (a real corruption,
    # well outside tolerance). Use the cfs-score span anchor.
    corrupted = html.replace(
        '<span class="cfs-score">79.4</span>',
        '<span class="cfs-score">19.4</span>',
        1,
    )
    assert corrupted != html, "fixture changed — update the CFS corruption anchor"
    violations = check_render_fidelity(corrupted, s)
    assert any(v["code"] == "RENDER_FIDELITY" for v in violations), violations


def test_corrupted_allocation_is_caught(fundmaster_exposure):
    """A fund-card allocation % drifted from state["portfolio"] → RENDER_FIDELITY."""
    s = _pipeline(fundmaster_exposure)
    html = s["proposal_html"]
    pga_alloc = next(h["allocation_pct"] for h in s["portfolio"] if h["abbr"] == "PGA")
    # The fund-card header renders the alloc as `<span class="alloc">40.6%</span>`.
    corrupted = html.replace(
        f'<span class="alloc">{pga_alloc}%</span>',
        '<span class="alloc">90.6%</span>',
        1,
    )
    assert corrupted != html, "fixture changed — update the allocation corruption anchor"
    violations = check_render_fidelity(corrupted, s)
    assert any(v["code"] == "RENDER_FIDELITY" for v in violations), violations


def test_corrupted_exposure_legend_pct_is_caught(fundmaster_exposure):
    """An exposure legend % drifted from compute_*_exposure → RENDER_FIDELITY.

    Note this is distinct from the existing ``exposure_sum`` check: here we swap
    TWO complementary slices so the legend still sums to 100 (sum check passes),
    but each slice no longer matches its authoritative computed value.
    """
    s = _pipeline(fundmaster_exposure)
    html = s["proposal_html"]
    # Find the two largest asset legend pcts and swap them — sum stays 100, but
    # each individual value now disagrees with compute_asset_exposure.
    block = re.search(
        r'exposure-chart-title">Asset Class<.*?(?=<div class="exposure-chart-block">|$)',
        html,
        re.DOTALL,
    ).group(0)
    pcts = re.findall(r'class="legend-pct">([\d.]+)%<', block)
    assert len(pcts) >= 2, pcts
    a, b = pcts[0], pcts[1]
    assert a != b, ("need two distinct legend pcts to swap", pcts)
    # Swap a<->b in the block region only (first two legend-pct spans).
    corrupted = html.replace(
        f'class="legend-pct">{a}%<', "class=\"legend-pct\">__TMP__%<", 1
    )
    corrupted = corrupted.replace(
        f'class="legend-pct">{b}%<', f'class="legend-pct">{a}%<', 1
    )
    corrupted = corrupted.replace(
        'class="legend-pct">__TMP__%<', f'class="legend-pct">{b}%<', 1
    )
    assert corrupted != html
    violations = check_render_fidelity(corrupted, s)
    assert any(v["code"] == "RENDER_FIDELITY" for v in violations), violations


def test_corrupted_shariah_label_is_caught(fundmaster_exposure):
    """A fund-card Shariah label flipped from state's bool → RENDER_FIDELITY.

    State stores ``shariah`` as a bool; HTML renders "Shariah"/"Conventional".
    The check must map before comparing.
    """
    s = _pipeline(fundmaster_exposure)
    html = s["proposal_html"]
    # The cores are conventional → rendered "Shariah:</strong> Conventional".
    # Flip the first one to "Shariah" (claims Shariah-compliant for a conventional fund).
    corrupted = html.replace(
        "<strong>Shariah:</strong> Conventional",
        "<strong>Shariah:</strong> Shariah",
        1,
    )
    assert corrupted != html, "fixture changed — update the Shariah corruption anchor"
    violations = check_render_fidelity(corrupted, s)
    assert any(v["code"] == "RENDER_FIDELITY" for v in violations), violations


def test_corrupted_weighted_aggregate_is_caught(fundmaster_exposure):
    """A weighted aggregate drifted from _compute_portfolio_metrics → RENDER_FIDELITY."""
    s = _pipeline(fundmaster_exposure)
    html = s["proposal_html"]
    # Weighted CFS renders in a data-slot span: data-slot="portfolio.cfs_composite">72.1<
    m = re.search(r'data-slot="portfolio\.cfs_composite">([\d.]+)<', html)
    assert m, "weighted CFS data-slot not found"
    val = m.group(1)
    corrupted = html.replace(
        f'data-slot="portfolio.cfs_composite">{val}<',
        'data-slot="portfolio.cfs_composite">12.1<',
    )
    assert corrupted != html
    violations = check_render_fidelity(corrupted, s)
    assert any(v["code"] == "RENDER_FIDELITY" for v in violations), violations


# ── Tolerance: display-precision rounding must NOT false-fire ──────────────────


def test_display_precision_within_tolerance_does_not_fire(fundmaster_exposure):
    """A value rendered at display precision (e.g. one extra decimal trimmed) must
    not false-fire, but a real corruption of the same field must."""
    s = _pipeline(fundmaster_exposure)
    html = s["proposal_html"]
    # PGA composite is 79.4 — nudge to 79.43 (within tolerance). Must stay clean.
    near = html.replace(
        '<span class="cfs-score">79.4</span>',
        '<span class="cfs-score">79.43</span>',
        1,
    )
    assert near != html
    assert check_render_fidelity(near, s) == [], "tolerant nudge false-fired"

    # Same field shoved 13 points off — a real corruption — MUST fire.
    far = html.replace(
        '<span class="cfs-score">79.4</span>',
        '<span class="cfs-score">66.4</span>',
        1,
    )
    assert far != html
    assert any(
        v["code"] == "RENDER_FIDELITY" for v in check_render_fidelity(far, s)
    ), "real corruption slipped through tolerance"


# ── Coverage canary: a missing / renamed fund card fails loud, not vacuously ───


def test_missing_fund_card_is_caught_by_coverage(fundmaster_exposure):
    """If a holding's card is dropped or its abbreviation mangled, the per-card
    checks would simply never visit it (a vacuous pass). The coverage canary must
    turn that gap into a loud RENDER_FIDELITY violation naming the missing holding."""
    s = _pipeline(fundmaster_exposure)
    html = s["proposal_html"]
    target = next(h["abbr"] for h in s["portfolio"])
    # Mangle only that holding's card-TITLE abbr so fund_cards() yields a different
    # abbr for the chunk → the holding has no card under its real name.
    pat = re.compile(rf'(<h3>[^<]*&middot;\s*){re.escape(target)}([^<]*</h3>)')
    assert pat.search(html), ("fixture changed — card title anchor", target)
    corrupted = pat.sub(rf"\g<1>{target}X\g<2>", html, count=1)
    assert corrupted != html
    violations = check_render_fidelity(corrupted, s)
    assert any(
        v["code"] == "RENDER_FIDELITY" and target in v["msg"] for v in violations
    ), violations


def test_em_dash_meta_does_not_false_fire(fundmaster_4fund):
    """Meta cells rendered as an em-dash / empty (no authoritative value) are skipped,
    not flagged. The 4-fund fixture renders VF as '&mdash;' (no volatility_factor)."""
    s = _pipeline(fundmaster_4fund)
    html = s["proposal_html"]
    assert "<strong>VF:</strong> &mdash;" in html, "fixture changed — VF anchor"
    assert check_render_fidelity(html, s) == []

"""Tests for the shared validation rule module.

RED phase: these tests import from consultant_engine.rules.validation which
does not yet exist. They must fail with ImportError or AttributeError.
"""

from pathlib import Path

import pytest

from consultant_engine.rules.validation import (
    check_cfs_consistency,
    check_exposure_consistency,
    check_prepared_for,
    check_unfilled_slots,
    fund_cards,
    validate_html,
    workbook_index,
)
from consultant_engine import __version__

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def good_html():
    return (FIXTURES / "proposal_good.html").read_text()


@pytest.fixture(scope="session")
def bad_section_html():
    return (FIXTURES / "proposal_bad_section.html").read_text()


@pytest.fixture(scope="session")
def bad_cfs_html():
    return (FIXTURES / "proposal_bad_cfs.html").read_text()


@pytest.fixture(scope="session")
def wb_index(good_html):
    """Minimal workbook index: maps every fund abbrev in the good proposal
    to an eligible (Qualified, non-retail-violating) status dict.
    Built from fund_cards() so it always matches whatever the good fixture has.
    """
    cards = fund_cards(good_html)
    index = {}
    for abbr, _ in cards:
        # PeEMAS has an alpha-warning in the example (disqualified in source WB)
        status = "Disqualified" if "PeEMAS" in abbr else "Qualified"
        index[abbr] = {"name": f"Public Fund {abbr}", "status": status}
    return index


# ── Tests ────────────────────────────────────────────────────────────────────

def test_good_proposal_has_no_violations(good_html, wb_index):
    violations = validate_html(good_html, __version__, wb_index)
    assert violations == [], f"Expected clean, got: {violations}"


def test_section_drift_is_caught(bad_section_html, wb_index):
    codes = {v["code"] for v in validate_html(bad_section_html, __version__, wb_index)}
    assert "section_order" in codes


def test_cfs_inconsistency_is_caught(bad_cfs_html, wb_index):
    codes = {v["code"] for v in validate_html(bad_cfs_html, __version__, wb_index)}
    assert "cfs_recompute" in codes


# ── CFS recompute: per-card bounding + fail-loud on a malformed scored card ────


def _scored_card(name: str, abbr: str, composite: str, rows: list[tuple[str, str]]) -> str:
    """Build a minimal fund-card chunk with a CFS bar (score + dimension rows)."""
    dims = "".join(
        f"<span>{s} / 100 &middot; {w}% weight</span>" for s, w in rows
    )
    return (
        f'<div class="fund-card"><h3>{name} &middot; {abbr}</h3>'
        f'<div class="cfs-bar"><div class="cfs-title">COMPOSITE FUND SCORE: '
        f'<span class="cfs-score">{composite}</span> / 100</div>{dims}</div></div>'
    )


def test_scored_card_with_wrong_row_count_fails_loud():
    """A card that HAS a cfs-score but not exactly 4 dimension rows breaks the
    scored-card contract — it must fail loud (``malformed_cfs_bar``), not be silently
    skipped (which would let a malformed bar pass the validator unchecked)."""
    html = _scored_card(
        "Fund A", "PFA", "50.0",
        [("50.0", "28.0"), ("50.0", "40.0"), ("50.0", "32.0")],  # only 3 rows
    )
    codes = {v["code"] for v in check_cfs_consistency(html)}
    assert "malformed_cfs_bar" in codes, codes


def test_cfs_recompute_is_bounded_and_attributed_per_card():
    """Two scored cards: a clean one and a corrupted one. The recompute must use
    each card's OWN rows (per-card bounding via fund_cards) — so exactly one
    cfs_recompute fires, attributed to the offending card, and the clean card's rows
    do not bleed into it."""
    dims4 = [("50.0", "28.0"), ("50.0", "40.0"), ("50.0", "20.0"), ("50.0", "12.0")]
    good = _scored_card("Fund A", "PFA", "50.0", dims4)            # recompute 50 == 50
    bad_rows = [("60.0", "28.0"), ("60.0", "40.0"), ("60.0", "20.0"), ("60.0", "12.0")]
    bad = _scored_card("Fund B", "PFB", "90.0", bad_rows)         # recompute 60 != 90
    recompute = [v for v in check_cfs_consistency(good + bad) if v["code"] == "cfs_recompute"]
    assert len(recompute) == 1, recompute
    assert "PFB" in recompute[0]["msg"], recompute[0]["msg"]


# ── Portfolio Exposure consistency guard ──────────────────────────────────────

def test_good_proposal_exposure_is_consistent(good_html):
    assert check_exposure_consistency(good_html) == []


def test_corrupted_exposure_legend_is_caught(good_html):
    """Corrupt one legend-pct so its block no longer sums to 100 → exposure_sum."""
    # The geographic block's USA slice in the good fixture is 39.7% — shove it to
    # 9.7% so that block sums to ~70, well outside the ±2 tolerance.
    corrupted = good_html.replace(
        '<span class="legend-pct">39.7%</span>',
        '<span class="legend-pct">9.7%</span>',
        1,
    )
    assert corrupted != good_html, "fixture changed — update the corruption anchor"
    violations = check_exposure_consistency(corrupted)
    assert any(v["code"] == "exposure_sum" for v in violations), violations


def test_corrupted_exposure_surfaces_through_validate_html(good_html, wb_index):
    corrupted = good_html.replace(
        '<span class="legend-pct">39.7%</span>',
        '<span class="legend-pct">9.7%</span>',
        1,
    )
    codes = {v["code"] for v in validate_html(corrupted, __version__, wb_index)}
    assert "exposure_sum" in codes


# ── Unfilled prose slot guard ─────────────────────────────────────────────────

def test_leftover_slot_marker_is_caught():
    """A raw <!--slot:KEY--> marker that survived prose fill is a structural leak."""
    codes = {v["code"] for v in check_unfilled_slots("<p><!--slot:why.PIX--></p>")}
    assert "unfilled_slot" in codes


def test_llm_fallback_sentinel_is_caught():
    """The real-LLM fallback sentinel [UNFILLED:KEY] is a genuine leak → must flag."""
    codes = {
        v["code"]
        for v in check_unfilled_slots("<p>[UNFILLED:strategy.dip_capture]</p>")
    }
    assert "unfilled_slot" in codes


def test_fake_mode_narrative_placeholder_is_not_flagged():
    """Fake-LLM mode fills EVERY slot with "[KEY narrative]" by design; that offline/
    eval convention must stay valid (a real leak uses the [UNFILLED:KEY] sentinel)."""
    assert check_unfilled_slots("<p>[strategy.dip_capture narrative]</p>") == []


def test_clean_prose_has_no_unfilled_violation():
    assert check_unfilled_slots("<p>Authored prose with no leftover slots.</p>") == []


def test_unfilled_slot_surfaces_through_validate_html(good_html, wb_index):
    leaked = good_html.replace(
        "</body>", "<p>[UNFILLED:strategy.dip_capture]</p></body>", 1
    )
    assert leaked != good_html, "fixture changed — update the injection anchor"
    codes = {v["code"] for v in validate_html(leaked, __version__, wb_index)}
    assert "unfilled_slot" in codes


_NAMED_BLOCK = ('<div class="cover-prepared-for">Prepared for '
                '<strong>Tan Wei Ming</strong></div>')


def test_prepared_for_named_present_is_clean():
    assert check_prepared_for(_NAMED_BLOCK, "Tan Wei Ming") == []


def test_prepared_for_named_missing_flags():
    v = check_prepared_for("<div>no prepared-for here</div>", "Tan Wei Ming")
    assert len(v) == 1 and v[0]["code"] == "prepared_for_missing"


def test_prepared_for_escaped_name_matches():
    safe = ('<div class="cover-prepared-for">Prepared for '
            "<strong>A &amp; B</strong></div>")
    assert check_prepared_for(safe, "A & B") == []


def test_prepared_for_generic_no_block_is_clean():
    assert check_prepared_for("<div class='cover'>nothing</div>", "") == []


def test_prepared_for_generic_leaked_block_flags():
    v = check_prepared_for(_NAMED_BLOCK, "")
    assert len(v) == 1 and v[0]["code"] == "prepared_for_unexpected"

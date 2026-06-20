"""Tests for the shared validation rule module.

RED phase: these tests import from consultant_engine.rules.validation which
does not yet exist. They must fail with ImportError or AttributeError.
"""

from pathlib import Path

import pytest

from consultant_engine.rules.validation import (
    check_exposure_consistency,
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

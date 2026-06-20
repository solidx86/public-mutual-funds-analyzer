"""Tests for the shared validation rule module.

RED phase: these tests import from consultant_engine.rules.validation which
does not yet exist. They must fail with ImportError or AttributeError.
"""

from pathlib import Path

import pytest

from consultant_engine.rules.validation import validate_html, fund_cards, workbook_index
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

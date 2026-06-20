"""Tests for consultant_engine/assets/ — skeleton structure and CSS copy.

Task 3.1: Move design system + build slotted skeleton.

Run red first (skeleton not yet created), then build to green.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SKELETON_PATH = REPO_ROOT / "consultant_engine" / "assets" / "proposal_skeleton.html"
CSS_PATH = REPO_ROOT / "consultant_engine" / "assets" / "design_system.css"

# The 9 locked section titles — exact strings as they appear in the HTML
# (HTML-escaped where needed, matching LOCKED_SECTIONS in test_proposal_validation.py)
LOCKED_SECTIONS = [
    "Executive Summary",
    "Global &amp; Local Macro Context",
    "Client Risk Profile",
    "Fund Recommendations",
    "Portfolio Summary",
    "Portfolio Exposure",
    "Investment Strategy",
    "Fee Disclosure",
    "Disclaimer, Sources &amp; References",
]

# The 4 disclaimer h4 headings — exact text as in Section 9 of the locked template
DISCLAIMER_HEADINGS = [
    "AI-Generated Document",
    "Regulatory Disclaimer",
    "Cooling-Off Right",
    "Conflict of Interest",
]


# ── CSS copy ──────────────────────────────────────────────────────────────────

def test_design_system_css_exists():
    assert CSS_PATH.exists(), f"Missing: {CSS_PATH}"
    # consultant_engine/assets/design_system.css is the canonical design system
    # (migrated from the retired fund-consultant skill bundle).


# ── Skeleton exists ────────────────────────────────────────────────────────────

def test_skeleton_exists():
    assert SKELETON_PATH.exists(), f"Missing: {SKELETON_PATH}"


# ── Section structure ─────────────────────────────────────────────────────────

def _skeleton_text():
    return SKELETON_PATH.read_text(encoding="utf-8")


def test_locked_sections_present_and_in_order():
    """All 9 LOCKED_SECTIONS titles must appear in order as section-title divs."""
    text = _skeleton_text()
    titles = re.findall(r'<div class="section-title">([^<]+)</div>', text)
    assert titles == LOCKED_SECTIONS, (
        f"Section titles in skeleton differ from LOCKED_SECTIONS.\n"
        f"  Found:    {titles}\n"
        f"  Expected: {LOCKED_SECTIONS}"
    )


def test_exactly_9_section_divs():
    """Cover, foundation, and footer are NOT .section blocks — only the 9 content sections are."""
    text = _skeleton_text()
    count = text.count('<div class="section"')
    assert count == 9, f"Expected 9 <div class=\"section\" blocks, found {count}"


def test_cover_div_present():
    text = _skeleton_text()
    assert '<div class="cover">' in text, "Skeleton must include the cover div"


# ── Disclaimer headings ───────────────────────────────────────────────────────

def test_disclaimer_h4_headings_present_in_order():
    """Section 9 must contain all 4 disclaimer h4 headings in the locked order."""
    text = _skeleton_text()
    # Find all h4 text within the disclaimer div
    disclaimer_match = re.search(
        r'<div class="disclaimer">(.*?)</div>\s*\n\s*<div class="sources"',
        text,
        re.DOTALL,
    )
    assert disclaimer_match, "Could not locate <div class=\"disclaimer\"> block in skeleton"
    disclaimer_block = disclaimer_match.group(1)
    h4_texts = re.findall(r"<h4>([^<]+)</h4>", disclaimer_block)
    assert h4_texts == DISCLAIMER_HEADINGS, (
        f"Disclaimer h4 headings mismatch.\n"
        f"  Found:    {h4_texts}\n"
        f"  Expected: {DISCLAIMER_HEADINGS}"
    )


# ── Template slots ────────────────────────────────────────────────────────────

def test_version_placeholder_present():
    """{{version}} must appear in place of [SKILL_VERSION] everywhere."""
    text = _skeleton_text()
    assert "{{version}}" in text, (
        "Skeleton must contain {{version}} placeholder (used for cover footer + Section 9 stamp)"
    )


def test_foundation_start_end_markers():
    """Foundation block must be clearly delimited for conditional include/strip."""
    text = _skeleton_text()
    assert "<!--FOUNDATION_START-->" in text, "Missing <!--FOUNDATION_START--> marker"
    assert "<!--FOUNDATION_END-->" in text, "Missing <!--FOUNDATION_END--> marker"


def test_foundation_block_has_3_notes_not_4():
    """The 'Why a Starter Portfolio' 4th note has been dropped — block must have exactly 3 h3s."""
    text = _skeleton_text()
    start = text.find("<!--FOUNDATION_START-->")
    end = text.find("<!--FOUNDATION_END-->")
    assert start != -1 and end != -1, "Foundation markers not found"
    block = text[start:end]
    h3_count = len(re.findall(r"<h3>", block))
    assert h3_count == 3, (
        f"Foundation block must have exactly 3 h3 notes (1. Unit Trust / 2. Returns / 3. Cooling-Off), "
        f"found {h3_count}"
    )
    assert "Why a Starter Portfolio" not in block, (
        "The 'Why a Starter Portfolio' note must be removed from the Foundation block"
    )


def test_at_least_one_numeric_data_slot():
    """At least one data-slot= attribute must be present for numeric values."""
    text = _skeleton_text()
    assert 'data-slot="' in text, (
        "Skeleton must contain at least one data-slot= numeric slot attribute"
    )


def test_at_least_one_prose_comment_slot():
    """At least one <!--slot:--> prose marker must be present."""
    text = _skeleton_text()
    assert "<!--slot:" in text, (
        "Skeleton must contain at least one <!--slot:key--> prose comment marker"
    )


def test_design_system_css_slot_present():
    """The {{design_system_css}} slot must be in the <style> block (chosen approach: slot, not inline)."""
    text = _skeleton_text()
    assert "{{design_system_css}}" in text, (
        "Skeleton must contain {{design_system_css}} slot inside the <style> block"
    )


# ── Fee table structure ───────────────────────────────────────────────────────

def test_fee_table_has_8_columns():
    """Section 8 fee disclosure table must have exactly 8 <th> columns."""
    text = _skeleton_text()
    # Find Section 8 by its section-title div
    s8_start = text.find(">Fee Disclosure<")
    assert s8_start != -1, "Section 8 'Fee Disclosure' section-title not found"
    # Grab a generous chunk after that point up to next section header
    s8_chunk = text[s8_start : s8_start + 4000]
    thead_match = re.search(r"<thead>(.*?)</thead>", s8_chunk, re.DOTALL)
    assert thead_match, "No <thead> found in Section 8 fee table"
    th_count = len(re.findall(r"<th[^>]*>", thead_match.group(1)))
    assert th_count == 8, (
        f"Fee disclosure table must have exactly 8 columns, found {th_count}"
    )

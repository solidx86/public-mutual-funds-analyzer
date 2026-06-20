"""
Tests for consultant_engine/templates.py

Task 3.2: Structural card templating + slot fill (deterministic, no LLM).
"""
import pytest
from consultant_engine.templates import render_structural_card, fill_slots


# ─── render_structural_card ────────────────────────────────────────────────────

def test_gold_card_border_no_alpha_warning():
    """Gold structural card must use #b7791f border and must NOT contain any
    alpha-qualification warning language."""
    html = render_structural_card(
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeEMAS", "name": "Public e-EMAS"},
    )
    assert "#b7791f" in html
    assert "not alpha-qualified" not in html.lower()
    assert "exposure gap" not in html.lower()


def test_gold_card_contains_fund_name_and_abbr():
    """Gold card must surface the fund name and abbreviation."""
    html = render_structural_card(
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeEMAS", "name": "Public e-EMAS"},
    )
    assert "Public e-EMAS" in html
    assert "PeEMAS" in html


def test_gold_card_shows_allocation_pct():
    """Allocation percentage must appear in the gold card HTML."""
    html = render_structural_card(
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeEMAS", "name": "Public e-EMAS"},
    )
    assert "10%" in html


def test_gold_card_uses_gold_header_class():
    """Gold structural card header must use the 'gold' CSS class (from the locked design)."""
    html = render_structural_card(
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeEMAS", "name": "Public e-EMAS"},
    )
    assert 'fund-card-header gold' in html or 'class="fund-card-header gold"' in html


def test_mm_card_no_alpha_warning():
    """Money-market structural card must NOT contain any alpha-qualification warning language."""
    html = render_structural_card(
        {"abbr": "PMMF", "role": "structural:money_market", "allocation_pct": 5},
        {"abbr": "PMMF", "name": "Public Money Market Fund"},
    )
    assert "not alpha-qualified" not in html.lower()
    assert "exposure gap" not in html.lower()


def test_mm_card_uses_money_market_header_class():
    """Money-market structural card header must use 'money-market' CSS class."""
    html = render_structural_card(
        {"abbr": "PMMF", "role": "structural:money_market", "allocation_pct": 5},
        {"abbr": "PMMF", "name": "Public Money Market Fund"},
    )
    assert "money-market" in html


def test_mm_card_contains_fund_name_and_abbr():
    """MM card must surface the fund name and abbreviation."""
    html = render_structural_card(
        {"abbr": "PMMF", "role": "structural:money_market", "allocation_pct": 5},
        {"abbr": "PMMF", "name": "Public Money Market Fund"},
    )
    assert "Public Money Market Fund" in html
    assert "PMMF" in html


def test_mm_card_shows_allocation_pct():
    """Allocation percentage must appear in the MM card HTML."""
    html = render_structural_card(
        {"abbr": "PMMF", "role": "structural:money_market", "allocation_pct": 5},
        {"abbr": "PMMF", "name": "Public Money Market Fund"},
    )
    assert "5%" in html


def test_invalid_role_raises():
    """Unknown role should raise ValueError."""
    with pytest.raises(ValueError, match="role"):
        render_structural_card(
            {"abbr": "PIX", "role": "alpha:equity", "allocation_pct": 30},
            {"abbr": "PIX", "name": "Public Index Fund"},
        )


# ─── fill_slots ────────────────────────────────────────────────────────────────

def test_fill_slots_replaces_version():
    """{{version}} placeholder must be substituted."""
    skel = '<span>fund-consultant v{{version}}</span>'
    out = fill_slots(skel, {"version": "0.1.0"})
    assert "v0.1.0" in out
    assert "{{version}}" not in out


def test_fill_slots_replaces_numeric_data_slot():
    """data-slot elements must have their text content replaced."""
    skel = '<b data-slot="cfs.PIX.composite">0</b>'
    out = fill_slots(skel, {"cfs.PIX.composite": "88.0"})
    assert ">88.0<" in out


def test_fill_slots_replaces_version_and_numeric():
    """Combined: version + numeric data-slot both replaced."""
    skel = '<span>fund-consultant v{{version}}</span><b data-slot="cfs.PIX.composite">0</b>'
    out = fill_slots(skel, {"version": "0.1.0", "cfs.PIX.composite": "88.0"})
    assert "v0.1.0" in out
    assert ">88.0<" in out


def test_fill_slots_raises_on_unfilled_numeric_slot():
    """Any data-slot element with no corresponding key in slot_values must raise ValueError."""
    skel = '<b data-slot="cfs.PIX.composite">0</b><b data-slot="alloc.PIX.pct">0</b>'
    with pytest.raises(ValueError):
        fill_slots(skel, {"cfs.PIX.composite": "88.0"})  # alloc.PIX.pct missing → raise


def test_fill_slots_does_not_raise_for_prose_slots():
    """<!--slot:key--> prose markers are NOT filled here — no ValueError for them."""
    skel = '<!--slot:exec_summary.profile--><b data-slot="cover.e_target">0</b>'
    # Must not raise — prose slots are LLM territory
    out = fill_slots(skel, {"cover.e_target": "8.0"})
    assert ">8.0<" in out
    # Prose slot comment is left intact
    assert "<!--slot:exec_summary.profile-->" in out


def test_fill_slots_replaces_design_system_css():
    """{{design_system_css}} is replaced verbatim when provided."""
    skel = '<style>{{design_system_css}}</style>'
    out = fill_slots(skel, {"design_system_css": "body { color: red; }"})
    assert "body { color: red; }" in out
    assert "{{design_system_css}}" not in out


def test_fill_slots_raises_on_leftover_double_brace_placeholder():
    """Any remaining {{...}} placeholder other than the two handled ones should raise ValueError."""
    skel = '<span>{{unknown_placeholder}}</span>'
    with pytest.raises(ValueError, match="unknown_placeholder"):
        fill_slots(skel, {})


def test_fill_slots_multiple_slots():
    """Multiple data-slot elements are all replaced correctly."""
    skel = (
        '<span data-slot="cover.e_target">0</span>'
        '<span data-slot="cover.funds_selected_n">0</span>'
        '<span data-slot="cover.funds_screened_m">0</span>'
    )
    out = fill_slots(skel, {
        "cover.e_target": "8.0",
        "cover.funds_selected_n": "5",
        "cover.funds_screened_m": "120",
    })
    assert ">8.0<" in out
    assert ">5<" in out
    assert ">120<" in out

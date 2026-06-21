"""Group 1 — profile / cover / exec-summary facts are Python-owned, not LLM prose.

These slots used to be authored by the LLM as ``<!--slot:KEY-->`` prose markers;
they are now substituted by Python in ``generate_proposal`` BEFORE the prose-fill
step, so they never reach the model. Each test asserts the real value renders and
the corresponding ``[KEY narrative]`` placeholder is absent.

Runs offline via the autouse fake-LLM fixture in tests/conftest.py.
"""
import pytest

from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.filter_universe import filter_universe, RISK_CEILING
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.nodes.macro_context import macro_context
from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.generate_proposal import (
    generate_proposal,
    _workbook_month_year,
    _profile_facts,
)


def _facts(risk_level, **client_extra):
    """_profile_facts for a given profile without needing a buildable portfolio
    (the static lookups don't depend on holdings)."""
    client = {"risk_level": risk_level, "shariah": False}
    client.update(client_extra)
    return _profile_facts({
        "client_profile": client,
        "portfolio": [],
        "eligible_funds": [],
        "fundmaster_path": "/x/PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
    })


def _pipeline(fundmaster_4fund, client_overrides=None):
    """Build a proposal from the real pipeline; client_overrides patches the profile."""
    client = {"risk_level": "Moderate", "shariah": False}
    if client_overrides:
        client.update(client_overrides)
    s = {"client_profile": client,
         "fundmaster_path": fundmaster_4fund,
         "macro_context": {"source": "fixture"}}
    for step in (load_profile, load_funds, filter_universe, score_cfs,
                 macro_context, build_portfolio, generate_proposal):
        s.update(step(s))
    return s


def _html(fundmaster_4fund, client_overrides=None):
    return _pipeline(fundmaster_4fund, client_overrides)["proposal_html"]


# ── cover.profile / exec_summary.profile render the risk level ───────────────

def test_cover_and_exec_profile_render_risk_level(fundmaster_4fund):
    html = _html(fundmaster_4fund)
    # Moderate appears on the cover meta + cover <title> + exec-summary bullet.
    assert "Moderate" in html
    # The LLM placeholders for these slots must NOT survive.
    assert "[cover.profile narrative]" not in html
    assert "[exec_summary.profile narrative]" not in html
    # No leftover prose-slot markers for either key.
    assert "slot:cover.profile" not in html
    assert "slot:exec_summary.profile" not in html


# The 4-fund fixture's cores are RL3, so only profiles with ceiling >= 3 build a
# valid portfolio (Conservative ceiling=2 excludes them). Conservative's name/
# ceiling facts are covered separately via _profile_facts below.
_BUILDABLE_PROFILES = [p for p, c in RISK_CEILING.items() if c >= 3]


@pytest.mark.parametrize("risk_level", _BUILDABLE_PROFILES)
def test_cover_profile_matches_each_risk_level(fundmaster_4fund, risk_level):
    html = _html(fundmaster_4fund, {"risk_level": risk_level})
    # Cover meta value cell carries the literal risk level.
    assert f'<div class="cover-meta-value">{risk_level}</div>' in html
    assert "[cover.profile narrative]" not in html


# ── shariah 3-way mapping ────────────────────────────────────────────────────

# Shariah=False / None are feasible through the all-conventional fixture pipeline.
@pytest.mark.parametrize("shariah,expected", [
    (False, "Conventional"),
    (None, "No preference (both)"),
])
def test_shariah_mapping_through_pipeline(fundmaster_4fund, shariah, expected):
    html = _html(fundmaster_4fund, {"shariah": shariah})
    assert expected in html
    assert "[cover.shariah narrative]" not in html
    assert "[profile.shariah narrative]" not in html
    assert "slot:cover.shariah" not in html
    assert "slot:profile.shariah" not in html


# Shariah=True can't build through the all-conventional fixture, so assert the
# full 3-way map directly on _profile_facts (the same dict generate_proposal applies).
@pytest.mark.parametrize("shariah,expected", [
    (True, "Shariah-compliant"),
    (False, "Conventional"),
    (None, "No preference (both)"),
])
def test_shariah_three_way_map_on_facts(shariah, expected):
    facts = _profile_facts({
        "client_profile": {"risk_level": "Moderate", "shariah": shariah},
        "portfolio": [],
        "eligible_funds": [],
        "fundmaster_path": "/x/PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
    })
    assert facts["<!--slot:cover.shariah-->"] == expected
    assert facts["<!--slot:profile.shariah-->"] == expected


# ── experience_level mapping ─────────────────────────────────────────────────

@pytest.mark.parametrize("experience,expected", [
    ("new", "New investor"),
    ("experienced", "Experienced investor"),
])
def test_experience_level_mapping(fundmaster_4fund, experience, expected):
    html = _html(fundmaster_4fund, {"experience": experience})
    assert f"<td>{expected}</td>" in html
    assert "[profile.experience_level narrative]" not in html
    assert "slot:profile.experience_level" not in html


# ── rl_ceiling equals RISK_CEILING[risk_level] ───────────────────────────────

# Pipeline check for a buildable profile (marker is fully consumed in real HTML)…
def test_rl_ceiling_rendered_in_html(fundmaster_4fund):
    html = _html(fundmaster_4fund, {"risk_level": "Moderate"})
    assert f"RL {RISK_CEILING['Moderate']} (per profile rule)" in html
    assert "[profile.rl_ceiling narrative]" not in html
    assert "slot:profile.rl_ceiling" not in html


# …and the value equals RISK_CEILING[risk_level] for every profile (incl. Conservative).
@pytest.mark.parametrize("risk_level", list(RISK_CEILING))
def test_rl_ceiling_equals_risk_ceiling_map(risk_level):
    assert _facts(risk_level)["<!--slot:profile.rl_ceiling-->"] == str(RISK_CEILING[risk_level])


# ── name_description static lookup ───────────────────────────────────────────

@pytest.mark.parametrize("risk_level,label_sentence", [
    ("Conservative", "Conservative — capital preservation is the priority"),
    ("Moderate", "Moderate — a balanced investor seeking steady long-term growth"),
    ("Moderately Aggressive", "Moderately Aggressive — growth-oriented"),
    ("Aggressive", "Aggressive — maximum long-term growth is the goal"),
])
def test_name_description_contains_label_sentence(risk_level, label_sentence):
    assert label_sentence in _facts(risk_level)["<!--slot:profile.name_description-->"]


def test_name_description_rendered_in_html(fundmaster_4fund):
    html = _html(fundmaster_4fund, {"risk_level": "Moderate"})
    assert "Moderate — a balanced investor seeking steady long-term growth" in html
    assert "[profile.name_description narrative]" not in html
    assert "slot:profile.name_description" not in html


# ── target_note: warning when above ceiling, static qualifier when within ────

def test_target_note_shows_ceiling_warning_when_above(fundmaster_4fund):
    # Moderate CEILING is 6.0; 9.0 exceeds it → load_profile computes a warning.
    html = _html(fundmaster_4fund, {"target_annual_return_pct": 9.0})
    assert "exceeds the realistic ceiling" in html
    assert "[profile.target_note narrative]" not in html
    assert "slot:profile.target_note" not in html


def test_target_note_shows_static_qualifier_when_within(fundmaster_4fund):
    # Moderate CEILING is 6.0; 5.0 is within range → static qualifier.
    html = _html(fundmaster_4fund, {"target_annual_return_pct": 5.0})
    assert "within the realistic range for a Moderate profile" in html
    assert "[profile.target_note narrative]" not in html
    assert "slot:profile.target_note" not in html


# ── exec_summary.composition counts built-portfolio holdings by type ─────────

def test_composition_matches_fixture_holdings(fundmaster_4fund):
    # The 4-fund fixture builds: PGA + PBA (equity cores), PeEMAS (gold),
    # PeCDF-A (money market) → "2 equity, 1 gold, 1 MM".
    html = _html(fundmaster_4fund)
    assert "2 equity, 1 gold, 1 MM" in html
    assert "[exec_summary.composition narrative]" not in html
    assert "slot:exec_summary.composition" not in html


# ── macro.month_year is the workbook vintage, not the LLM's guess ────────────

def test_macro_month_year_is_workbook_vintage(fundmaster_4fund):
    html = _html(fundmaster_4fund)
    # Fixture workbook is ..._Jun2026_v0.1.0.xlsx → "Jun 2026".
    assert _workbook_month_year(fundmaster_4fund) == "Jun 2026"
    # The macro positioning line carries the vintage, naturally phrased.
    assert "Jun 2026" in html
    assert "slot:macro.month_year" not in html
    assert "[macro.month_year narrative]" not in html

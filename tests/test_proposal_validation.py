"""Regression checks for the LLM-generated proposals.

The fund-consultant skill is prompt-driven, so its output can drift in ways
unit tests on code never see. These tests pin the contract instead: every
proposal must conform to the locked template skeleton, its scoring arithmetic
must be internally consistent, and the disclosure rules must hold against the
FundMaster workbook the proposal says it was built from.

Scope: the tracked curated samples under output/examples/fund_proposals/ AND any
live run sitting in the gitignored output/fund_proposals/. In CI the live dir is
empty (fresh checkout), so this validates exactly the committed samples; locally
it doubles as a pre-flight on real runs — a generated proposal that trips a rule
fails the suite until it's fixed or moved out. Cited FundMaster workbooks are
resolved from output/examples/fundmasters/ or the live output/fundmasters/."""

import re
from pathlib import Path

import pytest

from consultant_engine import __version__
from consultant_engine.rules.validation import (
    LOCKED_SECTIONS,  # noqa: F401 – imported for reference / direct test use
    WHOLESALE_ABBRS,  # noqa: F401 – imported for reference / direct test use
    check_alpha_warning,
    check_cfs_consistency,
    check_funds_in_workbook,
    check_retail_eligibility,
    check_sections,
    check_version_and_disclosure,
    fund_cards,
    validate_html,
    workbook_index,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Validate curated examples (tracked) and any local live run. Examples are
# listed first so a promoted-but-identical copy resolves to the live file when
# the same filename exists in both dirs.
_PROPOSAL_DIRS = (
    REPO_ROOT / "output" / "examples" / "fund_proposals",
    REPO_ROOT / "output" / "fund_proposals",
)
_FUNDMASTER_DIRS = (
    REPO_ROOT / "output" / "examples" / "fundmasters",
    REPO_ROOT / "output" / "fundmasters",
)


def _collect_proposals():
    by_name = {}
    for base in _PROPOSAL_DIRS:
        for p in base.glob("FundProposal_*.html"):
            by_name[p.name] = p  # later dir (live) wins on name collision
    return sorted(by_name.values(), key=lambda p: p.name)


PROPOSALS = _collect_proposals()

# Pinned retail-eligibility violations found in earlier published samples.
# Those samples were regenerated clean in June 2026 — the set stays so any NEW
# drift fails loudly.
KNOWN_ELIGIBILITY_VIOLATIONS = set()


def skill_version():
    return __version__


def _resolve_workbook(proposal_text: str) -> Path:
    """Resolve the FundMaster workbook path named on the proposal cover."""
    m = re.search(
        r'Data Source</div>\s*<div class="cover-meta-value">FundMaster (\w{3})\w* (\d{4})',
        proposal_text,
    )
    assert m, "cover must name its FundMaster data source"
    pattern = f"PublicMutual_FundMaster_{m.group(1)}{m.group(2)}_v*.xlsx"
    matches = [p for d in _FUNDMASTER_DIRS for p in d.glob(pattern)]
    assert matches, (
        f"workbook for {m.group(1)} {m.group(2)} not found in "
        "output/examples/fundmasters/ or output/fundmasters/"
    )
    return matches[0]


def test_proposal_samples_exist():
    assert PROPOSALS, "no tracked sample proposals found"


@pytest.mark.parametrize("path", PROPOSALS, ids=lambda p: p.name)
def test_locked_template_sections_in_order(path):
    text = path.read_text()
    violations = check_sections(text)
    assert not violations, f"section violations: {violations}"
    assert '<div class="cover">' in text


@pytest.mark.parametrize("path", PROPOSALS, ids=lambda p: p.name)
def test_version_stamp_and_ai_disclosure(path):
    text = path.read_text()
    ver = skill_version()
    assert path.name.endswith(f"_v{ver}.html"), "filename must carry the skill version"
    violations = check_version_and_disclosure(text, ver)
    assert not violations, f"version/disclosure violations: {violations}"


@pytest.mark.parametrize("path", PROPOSALS, ids=lambda p: p.name)
def test_cfs_scores_are_internally_consistent(path):
    """Each CFS bar: composite in (0,100], four dimensions in [0,100], weights sum to 100."""
    text = path.read_text()
    violations = check_cfs_consistency(text)
    assert not violations, f"CFS inconsistencies: {violations}"


@pytest.mark.parametrize("path", PROPOSALS, ids=lambda p: p.name)
def test_recommended_funds_exist_in_source_workbook(path):
    text = path.read_text()
    idx = workbook_index(_resolve_workbook(text))
    cards = fund_cards(text)
    assert cards, "no fund cards found"
    violations = check_funds_in_workbook(text, idx)
    assert not violations, f"workbook violations: {violations}"


@pytest.mark.parametrize("path", PROPOSALS, ids=lambda p: p.name)
def test_alpha_warning_iff_disqualified(path):
    """Disclosure rule: a fund card carries an ALPHA WARNING block exactly when
    the fund failed screening (weighted alpha <= 0) in the source workbook."""
    text = path.read_text()
    idx = workbook_index(_resolve_workbook(text))
    violations = check_alpha_warning(text, idx)
    assert not violations, f"alpha-warning violations: {violations}"


@pytest.mark.parametrize("path", PROPOSALS, ids=lambda p: p.name)
def test_no_new_retail_eligibility_violations(path):
    """SKILL.md Step 1b: no 'PB '-named funds, no '-B' class units, no wholesale
    funds may be recommended. Existing violations are pinned above."""
    text = path.read_text()
    idx = workbook_index(_resolve_workbook(text))
    violations = check_retail_eligibility(text, idx)
    new = {(path.name, v["msg"]) for v in violations} - KNOWN_ELIGIBILITY_VIOLATIONS
    assert not new, f"new retail-eligibility violations: {new}"


@pytest.mark.parametrize("path", PROPOSALS, ids=lambda p: p.name)
def test_validate_html_clean(path):
    """Full composite check via validate_html — must return an empty list."""
    text = path.read_text()
    idx = workbook_index(_resolve_workbook(text))
    violations = validate_html(text, skill_version(), idx)
    assert violations == [], f"validate_html found violations: {violations}"

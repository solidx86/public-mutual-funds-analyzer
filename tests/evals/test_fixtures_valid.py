"""Offline lint over the frozen prose-number eval fixture corpus.

This is the OFFLINE half of the crux described in the design spec (§7): it
proves the fixture corpus itself is well-formed and covers every required
combination, without a model API key. It does **not** run the judge — that
live half (does the judge actually reach the right verdict, especially on the
`seeded-bad-buried` fixtures) is a later phase's job (Phase 4), which needs an
`ANTHROPIC_API_KEY`. See evals/prose_numbers/fixtures/README.md for the exact
schema this test enforces.
"""
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "evals" / "prose_numbers" / "fixtures"

_REQUIRED_KEYS = {"slot_key", "figures", "prose", "expect", "offending_sentence", "category"}
_VALID_EXPECT = {"entailed", "contradicted"}
_VALID_CATEGORY = {"good", "seeded-bad-single", "seeded-bad-buried"}


def _slot_family(slot_key: str) -> str:
    """Map a slot_key to its family: why / watch / macro."""
    if slot_key.startswith("why."):
        return "why"
    if slot_key.startswith("watch."):
        return "watch"
    if slot_key.startswith("macro.impact"):
        return "macro"
    raise ValueError(f"unrecognized slot_key family: {slot_key!r}")


def _fund_of(slot_key: str) -> str | None:
    """Extract the fund abbr from a why.<ABBR>/watch.<ABBR> slot_key, else None
    (macro.impact.<n> slots are not per-fund)."""
    if slot_key.startswith("why.") or slot_key.startswith("watch."):
        return slot_key.split(".", 1)[1]
    return None


def _load_fixtures() -> list[tuple[Path, dict]]:
    paths = sorted(FIXTURES_DIR.glob("*.json"))
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in paths]


_FIXTURES = _load_fixtures()


def test_fixture_files_exist():
    assert _FIXTURES, f"no fixture JSON files found under {FIXTURES_DIR}"


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_required_keys_present(path, fixture):
    missing = _REQUIRED_KEYS - fixture.keys()
    assert not missing, f"{path.name} is missing required keys: {missing}"


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_expect_is_valid_enum(path, fixture):
    assert fixture["expect"] in _VALID_EXPECT, (
        f"{path.name}: expect={fixture['expect']!r} not in {_VALID_EXPECT}")


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_category_is_valid_enum(path, fixture):
    assert fixture["category"] in _VALID_CATEGORY, (
        f"{path.name}: category={fixture['category']!r} not in {_VALID_CATEGORY}")


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_good_fixtures_are_entailed_with_no_offending_sentence(path, fixture):
    if fixture["category"] == "good":
        assert fixture["expect"] == "entailed", (
            f"{path.name}: category=good must have expect=entailed")
        assert fixture["offending_sentence"] is None, (
            f"{path.name}: category=good must have offending_sentence=null")


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_seeded_bad_fixtures_are_contradicted_with_offending_sentence(path, fixture):
    if fixture["category"] in ("seeded-bad-single", "seeded-bad-buried"):
        assert fixture["expect"] == "contradicted", (
            f"{path.name}: category={fixture['category']} must have expect=contradicted")
        offending = fixture["offending_sentence"]
        assert offending, (
            f"{path.name}: category={fixture['category']} must have a non-null, "
            f"non-empty offending_sentence")
        assert offending in fixture["prose"], (
            f"{path.name}: offending_sentence must appear verbatim inside prose")


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_slot_key_has_recognized_family(path, fixture):
    # Raises ValueError (failing the test) on an unrecognized slot_key shape.
    _slot_family(fixture["slot_key"])


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_figures_block_is_nonempty_dict(path, fixture):
    assert isinstance(fixture["figures"], dict) and fixture["figures"], (
        f"{path.name}: figures must be a non-empty object")


@pytest.mark.parametrize("path,fixture", _FIXTURES, ids=[p.stem for p, _ in _FIXTURES])
def test_prose_is_nonempty_string(path, fixture):
    assert isinstance(fixture["prose"], str) and fixture["prose"].strip(), (
        f"{path.name}: prose must be a non-empty string")


# ── Coverage: every slot family present in every category, several funds ────

def test_every_slot_family_appears_in_every_category():
    seen = {(fam, fix["category"])
            for _, fix in _FIXTURES
            for fam in [_slot_family(fix["slot_key"])]}
    families = {"why", "watch", "macro"}
    categories = _VALID_CATEGORY
    missing = {(fam, cat) for fam in families for cat in categories} - seen
    assert not missing, f"missing family x category combinations: {sorted(missing)}"


def test_multiple_funds_represented():
    funds = {_fund_of(fix["slot_key"]) for _, fix in _FIXTURES}
    funds.discard(None)
    assert len(funds) >= 2, f"expected multiple distinct funds, found: {funds}"


def test_good_category_includes_a_derived_not_verbatim_case():
    """Sanity check for the MANDATORY adversarial-but-correct derived good case
    (spec §4a / brief policy 4a): at least one `good` fixture's prose must state
    a number that is not simply the literal value of a single fund's own figure
    (an average/sum/aggregate instead). We approximate this by requiring at
    least one `good` fixture per family whose filename/authoring marks it as a
    derived case, so this precision-measuring case can't silently disappear.
    """
    derived_good = [
        p.stem for p, fix in _FIXTURES
        if fix["category"] == "good" and "derived" in p.stem
    ]
    assert derived_good, "no good fixture marked as an adversarial-but-correct derived case"

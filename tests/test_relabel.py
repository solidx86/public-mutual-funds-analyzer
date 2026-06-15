"""Offline validator for the Step 1.5 relabel of mfr_results.json.

Runs against the tracked mfr_results.json at the repo root (read-only), mirroring
the existing offline-test pattern. The in-session relabel (SKILL.md Step 1.5) is
what makes these assertions pass; this file is the regression guard.
"""
import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MFR_PATH = os.path.join(REPO_ROOT, "data", "cache", "mfr_results.json")

# --- Bounded enums (single source of truth) ---------------------------------
ASSET_CLASS = {
    "Equity - Malaysia", "Equity - Foreign", "Bond / Fixed Income",
    "Bond / Sukuk", "Mixed Asset", "Balanced", "Money Market",
}
GEOGRAPHY = {
    "Malaysia", "Greater China", "ASEAN", "Asia Pacific", "Asia", "Global",
    "United States", "India", "Indonesia", "Japan", "Australia", "Vietnam",
    "Singapore",
}
OBJECTIVE_CLASS = {"Capital Growth", "Income", "Capital Growth + Income"}
PHS_FUND_TYPE = {
    "Equity", "Fixed Income", "Mixed Asset / Balanced", "Money Market",
    "Fund of Funds",
}
ENUMS = {
    "asset_class": ASSET_CLASS,
    "geography": GEOGRAPHY,
    "objective_class": OBJECTIVE_CLASS,
    "phs_fund_type": PHS_FUND_TYPE,
}
RELABEL_FIELDS = list(ENUMS.keys())

# Permitted residue when no enum fits (documented domain facts, not bug pins).
COMMODITY_ALLOWLIST = {"PeEMAS"}  # gold/commodity fund — no asset_class enum applies

# --- Geography foreign-default predicate ------------------------------------
# A lipper string signals a foreign default only when it (a) is non-empty,
# (b) carries no domestic marker, and (c) names a foreign region. "Bond MYR"
# and "Mixed Asset MYR Domestic" are Malaysian; "Consistent" / commodity name
# no region.
DOMESTIC_MARKERS = ("malaysia", "myr", "domestic")
FOREIGN_REGION_TOKENS = (
    "asia", "china", "global", "asean", "pacific", "india", "indonesia",
    "japan", "australia", "vietnam", "singapore", "europe", "emerging",
    "far east", "united states",
)


def lipper_names_foreign_region(lipper):
    l = (lipper or "").lower()
    if not l or any(m in l for m in DOMESTIC_MARKERS):
        return False
    return any(tok in l for tok in FOREIGN_REGION_TOKENS)

# Numeric / transcribed fields the relabel must never touch.
PROTECTED_FIELDS = [
    "performance", "ytd", "weighted_alpha", "asset_allocation",
    "top5_holdings", "top5_sectors", "annual_returns",
]


@pytest.fixture(scope="module")
def funds():
    with open(MFR_PATH) as fp:
        data = json.load(fp)
    return data["all_funds"]


def test_relabeled_values_are_in_enum(funds):
    """Any field carrying a _source flag must hold an in-enum value."""
    violations = []
    for f in funds:
        for field in RELABEL_FIELDS:
            if f.get(f"{field}_source") == "llm-relabel":
                if f.get(field) not in ENUMS[field]:
                    violations.append((f["abbr"], field, f.get(field)))
    assert not violations, f"relabeled values out of enum: {violations}"


def test_source_flags_are_valid(funds):
    """_source flags appear only on the four fields and equal 'llm-relabel'."""
    bad = []
    for f in funds:
        for key, val in f.items():
            if key.endswith("_source"):
                base = key[: -len("_source")]
                if base not in RELABEL_FIELDS or val != "llm-relabel":
                    bad.append((f["abbr"], key, val))
    assert not bad, f"invalid _source flags: {bad}"


def test_no_residual_other_asset_class(funds):
    """After relabel, asset_class == 'Other' only for allowlisted commodity funds."""
    leftovers = [
        f["abbr"] for f in funds
        if f.get("asset_class") == "Other" and f["abbr"] not in COMMODITY_ALLOWLIST
    ]
    assert not leftovers, f"unexpected 'Other' asset_class: {leftovers}"


def test_geography_not_defaulted_for_foreign_lipper(funds):
    """No fund keeps geography 'Malaysia' when its lipper names a foreign region
    and carries no domestic (MYR/Domestic/Malaysia) marker. MYR/Domestic funds
    are legitimately Malaysian and must be left alone."""
    bad = []
    for f in funds:
        if f.get("geography") == "Malaysia" and lipper_names_foreign_region(f.get("lipper_class")):
            bad.append((f["abbr"], f.get("lipper_class")))
    assert not bad, f"geography still defaulted to Malaysia on foreign-region funds: {bad}"


def test_protected_fields_present(funds):
    """Relabel must not have dropped any numeric/holdings field that Step 1 produced."""
    missing = []
    for f in funds:
        for field in ("performance", "weighted_alpha", "top5_holdings"):
            if field not in f:
                missing.append((f["abbr"], field))
    assert not missing, f"protected fields missing: {missing}"


@pytest.mark.parametrize("abbr,field,expected", [
    ("PIMMF-A", "asset_class", "Money Market"),
    ("PFEDF", "asset_class", "Equity - Foreign"),
    ("PGCF", "asset_class", "Equity - Foreign"),
    ("PASGF", "asset_class", "Equity - Foreign"),
    ("PCIF", "geography", "Greater China"),
    ("PAIF", "geography", "Asia"),
])
def test_pinned_bug_fixes(funds, abbr, field, expected):
    """The unambiguous keyword-bug cases are corrected."""
    match = next((f for f in funds if f["abbr"] == abbr), None)
    assert match is not None, f"{abbr} not found in mfr_results.json"
    assert match.get(field) == expected, (
        f"{abbr}.{field} = {match.get(field)!r}, expected {expected!r}"
    )

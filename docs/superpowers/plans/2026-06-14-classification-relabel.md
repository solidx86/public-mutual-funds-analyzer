# Classification Relabel (Step 1.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-session LLM relabel step (Step 1.5) to the fund-screener skill that corrects only the low-confidence classification fields in `mfr_results.json`, guarded by an offline regression test.

**Architecture:** No new pipeline scripts and no edits to `extract_mfr.py`. Step 1.5 is an instruction block in `fund-screener-skill/SKILL.md` that Claude executes during the normal skill run: it reads each flagged fund's `name`/`lipper_class`/`objective_text` from `mfr_results.json`, rewrites only `asset_class`/`geography`/`objective_class`/`phs_fund_type` from a bounded enum, and stamps a `<field>_source` audit flag. A new `tests/test_relabel.py` validates the committed `mfr_results.json` offline (enum conformance, source-flag integrity, non-interference, and pinned bug-fix corrections).

**Tech Stack:** Python 3, pytest, JSON. No new runtime dependencies.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `fund-screener-skill/SKILL.md` | Add Step 1.5 procedure + pipeline table row + sanity check + extract note + version/changelog | Modify |
| `tests/test_relabel.py` | Offline validator for the relabeled `mfr_results.json` (enums, source flags, non-interference, pinned fixes) | Create |
| `mfr_results.json` | Tracked extraction output; receives the relabeled values + `_source` flags | Modify (data) |

**Source of truth for enums:** the constants live at the top of `tests/test_relabel.py`. SKILL.md Step 1.5 reproduces them in prose for the in-session relabel; the test enforces them in code.

---

## Reference data (ground truth for this MFR set)

The current tracked `mfr_results.json` (171 funds) has these flagged funds. Use this table when performing the relabel in Task 4.

**`asset_class == "Other"` (8 funds):**

| Abbr | Name | lipper_class | Correct asset_class |
|---|---|---|---|
| PIMMF-A | Public Islamic MoneyMarket Fund -Class A | (empty) | Money Market |
| PFEDF | Public Far-East Dividend Fund | Asia | Equity - Foreign |
| PGCF | Public Greater China Fund | Greater China | Equity - Foreign |
| PASGF | Public ASEAN Growth Fund | ASEAN | Equity - Foreign |
| PIRESGF | Public Islamic Regional ESG Fund | (empty) | Equity - Foreign |
| PISGSGF | Public Islamic Global Sustainable Growth Fund | (empty) | Equity - Foreign |
| PISGRTF | Public Islamic Sustainable Growth Fund | (empty) | Equity - Foreign *(confirm from objective_text; sustainable/ESG mandates are global)* |
| PeEMAS | Public e-EMAS Gold Fund | Commodity Precious Fund-of-Funds | **leave "Other"** — gold/commodity, no enum fits (see commodity allowlist) |

**Geography foreign-defaults (geography `"Malaysia"` with a foreign-region lipper — the predicate set).** These 13 funds match the refined predicate and must be relabeled; target picked from `lipper_class` + `geo_breakdown` holdings:

| Abbr | Name | lipper_class | geo_breakdown (top) | Correct geography |
|---|---|---|---|---|
| POEF | Public Optimal Equity Fund | Equity Asia Pacific Asia | Taiwan/Korea/China/USA | Asia Pacific |
| PRSEC | Public Regional Sector Fund | Equity Asia Pacific Asia | Taiwan/Korea/China/Japan/SG | Asia Pacific |
| PLTF | Public Lifestyle & Technology Fund | Equity Global Global | USA 53% | Global |
| PAIF | Public Asia Ittikal Fund | Equity Asia Pacific Asia | Korea/Taiwan/Japan/China | Asia |
| PIOEF | Public Islamic Optimal Equity Fund | Equity Asia Pacific Asia | Taiwan/Korea/China/USA | Asia Pacific |
| PCIF | Public China Ittikal Fund | Equity Greater China Greater China | Taiwan/China | Greater China |
| PeAITF | Public e-Artificial Intelligence Technology Fund | Equity Sector Global | USA 70% | Global |
| PeCEF | Public e-Carbon Efficient Fund | Equity Global Global | USA 49% | Global |
| PePEF | Public e-Pioneer Entrepreneur Fund | Equity Global Global | USA 44% | Global |
| PeISITF | Public e-Islamic Innovative Technology Fund | Equity Sector Global | USA 61% | Global |
| PeIPE40F | Public e-Islamic Pioneer Entrepreneur 40 Fund | Equity Global Global | USA 58% | Global |
| PeISMF | Public e-Islamic Sustainable Millennial Fund | Equity Global | USA 67% | Global |
| PBEPEF | PB Euro Pacific Equity Fund | Equity Global Asia | Korea/China/Taiwan/USA/France | Global |

**Empty-lipper ESG funds (judgment — not enforced by the test, but correct to relabel):**

| Abbr | Name | lipper_class | geo_breakdown (top) | Correct geography |
|---|---|---|---|---|
| PISGRTF | Public Islamic Sustainable Growth Fund | (empty) | USA/Taiwan/China | Global |
| PIRESGF | Public Islamic Regional ESG Fund | (empty) | Korea/Taiwan/Japan/USA | Asia Pacific |

**Stay Malaysian — do NOT relabel** (lipper carries `MYR`/`Domestic`, or names no region): all `Bond MYR` and `Mixed Asset MYR [Domestic|Global]` funds (P BOND, PSBF, PBF, PSMACF, PIMXAF, PBBF, …, ~31 funds), plus `PI INCOME` (`Consistent`), `PIMMF-A` (domestic money market), and `PeEMAS` (gold).

**Pinned, unambiguous corrections** (enforced by the acceptance test):
PIMMF-A→Money Market · PFEDF→Equity - Foreign · PGCF→Equity - Foreign · PASGF→Equity - Foreign · PCIF→Greater China · PAIF→Asia.

---

### Task 1: Add Step 1.5 and ancillary edits to SKILL.md

**Files:**
- Modify: `fund-screener-skill/SKILL.md`

- [ ] **Step 1: Insert the Step 1.5 section** immediately after the Step 1 section (after the line reporting `Expected: mfr_results.json with ~171 funds.`).

Insert this Markdown block:

```markdown
## Step 1.5: Relabel low-confidence classifications (Claude Code, in-session — no script)

`extract_mfr.py` classifies four fields with keyword matching, which silently defaults hard cases.
After Step 1, Claude (not a script) relabels ONLY the funds the keyword classifier punted on. No API
key, no console spend — this runs in the skill session under the Max plan.

**Relabel a field only when its value is low-confidence:**

| Field | Relabel when… |
|---|---|
| `asset_class` | `== "Other"` |
| `objective_class` | `== ""` |
| `phs_fund_type` | `== ""` |
| `geography` | `== "Malaysia"` AND `lipper_class` names a foreign region AND carries no domestic marker (predicate below) |

> **Geography predicate (important):** a fund is a foreign-default only when its lowercased `lipper_class`
> (a) is non-empty, (b) contains **none** of the domestic markers `malaysia` / `myr` / `domestic`, and
> (c) contains at least one foreign-region token (`asia`, `china`, `global`, `asean`, `pacific`, `india`,
> `indonesia`, `japan`, `australia`, `vietnam`, `singapore`, `europe`, `emerging`, `far east`,
> `united states`). `Bond MYR` and `Mixed Asset MYR Domestic` are **Malaysian** (the "MYR"/"Domestic"
> marker is the home signal) — never relabel them. `Consistent` (a Lipper performance tag, not a region)
> and `Commodity Precious Fund-of-Funds` (gold) name no region — leave them. Funds with an **empty**
> lipper but clearly-foreign `geo_breakdown`/`objective_text` (e.g. the Islamic ESG funds) may still be
> relabeled by judgment, but the test does not require it.

**For each flagged fund:** read its `name`, `lipper_class`, `objective_text` (already in `mfr_results.json`),
choose the corrected value from the bounded enum below, write it back, and add a sibling
`"<field>_source": "llm-relabel"`.

**Bounded enums (choose only these values):**
- `asset_class`: Equity - Malaysia · Equity - Foreign · Bond / Fixed Income · Bond / Sukuk · Mixed Asset · Balanced · Money Market
- `geography`: Malaysia · Greater China · ASEAN · Asia Pacific · Asia · Global · United States · India · Indonesia · Japan · Australia · Vietnam · Singapore
- `objective_class`: Capital Growth · Income · Capital Growth + Income
- `phs_fund_type`: Equity · Fixed Income · Mixed Asset / Balanced · Money Market · Fund of Funds  (one combined value — NOT split, unlike asset_class)

**Rules:**
- NEVER modify `performance`, `ytd`, `weighted_alpha`, `asset_allocation`, `top5_holdings`, `top5_sectors`,
  or any other field. Numbers and holdings are deterministic and authoritative.
- If no enum fits (e.g. a gold/commodity fund), leave the original value and do NOT set `_source`.
- If `objective_text` is empty and the objective can't be resolved, leave it and do NOT set `_source`.
- Never invent an out-of-enum value.

**Verify:** run `pytest tests/test_relabel.py -v` — it must pass.
```

- [ ] **Step 2: Add the pipeline-overview table row.** In the "Pipeline overview" table (the `| Step | Script | Output |` table near line 55), add a row after the Step 1 row:

```markdown
| 1.5 | (Claude Code, in-session — no script) | mfr_results.json (relabeled) |
```

- [ ] **Step 3: Add a sanity-check row.** In the "Sanity checks" table (near line 210), add:

```markdown
| mfr_results.json — asset_class == "Other" | ~0 after Step 1.5 (gold/commodity funds excepted) |
```

- [ ] **Step 4: Annotate the extraction note.** In "What the scripts extract per fund" (near line 158), change the Fund Objective row's method text and add a note that asset class, geography, objective, and PHS fund type are "keyword classification, refined in Step 1.5".

- [ ] **Step 5: Bump version + changelog.** In the SKILL.md frontmatter, bump `version` by a minor increment. Add a changelog row at the top of the Changelog table:

```markdown
| <new-version> | 2026-06-14 | Feature | Step 1.5: in-session LLM relabel of low-confidence classifications (asset_class/geography/objective_class/phs_fund_type), guarded by tests/test_relabel.py |
```

- [ ] **Step 6: Verify the edits landed.**

Run: `grep -c "Step 1.5" fund-screener-skill/SKILL.md`
Expected: `>= 2` (section heading + pipeline row reference)

Run: `grep -n "llm-relabel" fund-screener-skill/SKILL.md`
Expected: at least one match (in the Step 1.5 block)

- [ ] **Step 7: Commit.**

```bash
git add fund-screener-skill/SKILL.md
git commit -m "feat(screener): add Step 1.5 in-session classification relabel to SKILL.md"
```

---

### Task 2: Write the failing relabel validator test

**Files:**
- Create: `tests/test_relabel.py`

- [ ] **Step 1: Write the test file.**

```python
"""Offline validator for the Step 1.5 relabel of mfr_results.json.

Runs against the tracked mfr_results.json at the repo root (read-only), mirroring
the existing offline-test pattern. The in-session relabel (SKILL.md Step 1.5) is
what makes these assertions pass; this file is the regression guard.
"""
import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MFR_PATH = os.path.join(REPO_ROOT, "mfr_results.json")

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
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `pytest tests/test_relabel.py -v`
Expected: FAIL — `test_no_residual_other_asset_class` reports the 8 `Other` funds (minus PeEMAS allowlist → 7), `test_geography_not_defaulted_for_foreign_lipper` reports the 13 foreign-region funds (POEF/PRSEC/PLTF/PAIF/PCIF/…), and `test_pinned_bug_fixes` fails for PIMMF-A/PFEDF/PGCF/PASGF/PCIF/PAIF (current data is uncorrected).

- [ ] **Step 3: Commit the failing test.**

```bash
git add tests/test_relabel.py
git commit -m "test(screener): add relabel validator for mfr_results.json (failing)"
```

---

### Task 3: Verify the test integrates with the existing suite

**Files:**
- (none — run only)

- [ ] **Step 1: Run the full suite to confirm collection works and only relabel tests fail.**

Run: `pytest -v`
Expected: existing `tests/test_pipeline.py` and `tests/test_proposal_validation.py` pass; `tests/test_relabel.py` fails as in Task 2 Step 2. No import/collection errors.

---

### Task 4: Perform the in-session relabel pass (make the tests pass)

**Files:**
- Modify: `mfr_results.json` (data only — the four classification fields + `_source` flags)

> This task IS the Step 1.5 procedure. Apply it by editing `mfr_results.json` directly, following SKILL.md Step 1.5 and the Reference data table above. Do NOT edit `extract_mfr.py`.

> **Full relabel set for this MFR.** `objective_class` and `phs_fund_type` have **no** empty values in the current data, so no relabel is needed for those two fields — only `asset_class` and `geography`. Each value set must be accompanied by its sibling `"<field>_source": "llm-relabel"`.

- [ ] **Step 1: `asset_class` relabels (7 funds → add `asset_class_source`).**
  - `PIMMF-A` → `"Money Market"`  *(pinned)*
  - `PFEDF`, `PGCF`, `PASGF` → `"Equity - Foreign"`  *(pinned)*
  - `PISGRTF`, `PIRESGF`, `PISGSGF` → `"Equity - Foreign"`  *(Islamic sustainable/ESG global-equity mandates)*
  - `PeEMAS` → leave `"Other"`, **no** `_source` (gold/commodity, no enum fits).

- [ ] **Step 2: `geography` relabels — predicate set (13 funds → add `geography_source`).** Foreign-region lipper, no domestic marker:
  - `PLTF`, `PeAITF`, `PeCEF`, `PePEF`, `PeISITF`, `PeIPE40F`, `PeISMF`, `PBEPEF` → `"Global"`
  - `POEF`, `PRSEC`, `PIOEF` → `"Asia Pacific"`
  - `PAIF` → `"Asia"`  *(pinned)*
  - `PCIF` → `"Greater China"`  *(pinned)*

- [ ] **Step 3: `geography` relabels — empty-lipper ESG funds (2 funds → add `geography_source`).** Judge from `geo_breakdown`/`objective_text`:
  - `PISGRTF` → `"Global"`  (holdings USA/Taiwan/China — global mandate)
  - `PIRESGF` → `"Asia Pacific"`  (holdings Korea/Taiwan/Japan — regional Asia)
  - `PIMMF-A`: geography stays `"Malaysia"` (domestic money market) — **no** `geography_source`.

> After Steps 1–3: `PISGRTF` and `PIRESGF` carry **both** `asset_class_source` and `geography_source`. No other fund's `geography` is `"Malaysia"` with a foreign-region lipper, so the geography test will pass. Do not touch any `Bond MYR` / `Mixed Asset MYR Domestic` fund — those are correctly Malaysian.

- [ ] **Step 4: Run the relabel tests to verify they pass.**

Run: `pytest tests/test_relabel.py -v`
Expected: PASS (all tests green).

- [ ] **Step 5: Verify non-interference against Step 1 output.**

Run:
```bash
git stash push mfr_results.json && \
python3 fund-screener-skill/scripts/extract_mfr.py >/dev/null 2>&1 && \
python3 - <<'PY'
import json
base = json.load(open("mfr_results.json"))["all_funds"]
PROT = ["performance","ytd","weighted_alpha","asset_allocation","top5_holdings","top5_sectors","annual_returns"]
json.dump({f["abbr"]:{k:f.get(k) for k in PROT} for f in base}, open("/tmp/base_prot.json","w"))
print("baseline captured:", len(base), "funds")
PY
git checkout mfr_results.json 2>/dev/null; git stash pop && \
python3 - <<'PY'
import json
base = json.load(open("/tmp/base_prot.json"))
cur = {f["abbr"]:f for f in json.load(open("mfr_results.json"))["all_funds"]}
PROT = ["performance","ytd","weighted_alpha","asset_allocation","top5_holdings","top5_sectors","annual_returns"]
diffs = [(a,k) for a,b in base.items() for k in PROT if cur.get(a,{}).get(k) != b[k]]
print("PROTECTED FIELD DIFFS:", diffs or "none")
assert not diffs, "relabel altered protected fields!"
PY
```
Expected: `PROTECTED FIELD DIFFS: none`. (If `extract_mfr.py` needs the MFR PDFs and they are absent, skip the regen and instead diff the relabeled JSON against `git show HEAD:mfr_results.json` for the protected fields.)

- [ ] **Step 6: Commit the relabeled data.**

```bash
git add mfr_results.json
git commit -m "data: apply Step 1.5 relabel to mfr_results.json classification fields"
```

---

### Task 5: Full suite green + finalize

**Files:**
- (none — run only)

- [ ] **Step 1: Run the entire suite.**

Run: `pytest -v`
Expected: ALL tests pass (`test_pipeline.py`, `test_proposal_validation.py`, `test_relabel.py`).

- [ ] **Step 2: Confirm CI parity.** The CI workflow runs `pytest`; nothing else to wire. Verify no new dependency was introduced.

Run: `git diff --name-only HEAD~4 HEAD`
Expected: only `fund-screener-skill/SKILL.md`, `tests/test_relabel.py`, `mfr_results.json`, and the spec/plan docs.

- [ ] **Step 3: Final commit (if any uncommitted finalization remains).**

```bash
git status --short   # expect clean
```

---

## Notes for the implementer

- **Do not edit `extract_mfr.py`.** The two keyword bugs (MONEYMARKET space, ITTIKAL ordering) are intentionally fixed by the relabel pass, not by patching the classifier (locked decision).
- **`mfr_results.json` is tracked** — committing the relabeled data is correct and expected (it gives a fresh clone working data and lets the test run offline in CI).
- **Reproducibility:** re-running Step 1 (`extract_mfr.py`) overwrites `mfr_results.json` and wipes the relabel; the relabel must be re-applied (Step 1.5) on each full regeneration. The committed state always reflects a post-relabel JSON.
- **`KNOWN_*` discipline:** `COMMODITY_ALLOWLIST` is a documented domain fact (gold fund has no equity/bond enum), not a mechanism to pin away a misclassification. Keep it minimal; do not add funds to silence a fixable relabel.

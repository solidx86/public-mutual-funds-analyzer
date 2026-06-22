# Track 0 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Important + Minor findings from the full-branch code review of `consultant_engine` (branch `track0-headless-consultant-engine-spec`), so the branch is correct and honest enough to merge to `main`.

**Architecture:** `consultant_engine` is a headless LangGraph `load → score → build → macro → generate → validate → repair → emit` pipeline with a Python-owned determinism boundary (Python owns every number; the LLM writes prose and assembles a locked HTML skeleton). The fixes are surgical: a deterministic cap-clamp in the portfolio builder, two HITL resume-path corrections, a unicode-safe filename, documentation honesty around the prose-number boundary, test-gap closures, minor cleanups, and regenerated public examples (no version bump this branch).

**Tech Stack:** Python 3.14, LangGraph + langgraph-checkpoint-sqlite, pydantic, openpyxl, pytest. Offline via `CONSULTANT_ENGINE_FAKE_LLM=1`.

## Global Constraints

- **Python interpreter:** always run tests with `.venv/bin/python -m pytest`. Bare `python` / system `python3.14` lack pytest. Single-test runs set the env var explicitly: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest <node> -v`.
- **Full offline suite:** `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine tests/test_proposal_validation.py -q` (the root conftest auto-sets FAKE_LLM for any test whose path contains `consultant_engine`, but a bare `tests/test_proposal_validation.py` run wants the env var too).
- **TDD, adversarial:** every behavioral fix lands with an adversarial test that **fails on the pre-fix code** and passes after. The standing lesson of this branch: convenient narrow-spread fixtures hid real bugs — wide-spread / spec-shaped fixtures are mandatory for the cap and HITL fixes.
- **`KNOWN_*` pin sets stay empty.** `tests/test_proposal_validation.py` declares `KNOWN_ELIGIBILITY_VIOLATIONS`, `KNOWN_SECTION_DEVIATIONS`, `KNOWN_CFS_INCONSISTENCIES` — if a regenerated example trips a rule, fix the proposal, never pin it.
- **Version source:** `consultant_engine.__version__` in `consultant_engine/__init__.py` (currently `"0.1.0"`). The filename/footer stamp is the literal `fund-consultant v<ver>`.
- **Filename convention:** `FundProposal_<ClientName|generic>_<RiskProfile>_<YYYY-MM-DD>_v<consultant-version>.html` where `<ClientName>` is the client name with non-word chars removed (case preserved) or the literal `generic`.
- **Examples are public.** `output/examples/` is the only committed output tree; `output/fund_proposals/` + `output/fundmasters/` are gitignored private mounts. Never run a verification/fake-LLM proposal into the default dir — examples are regenerated explicitly into `output/examples/fund_proposals/`.
- **Conventional commits**, each ending with a trailing `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` line. Commit after every green step group.
- **IMP-7 is already done** (commit `1dd8530`: `<title>` separator + regression guard + golden-path fix; suite 325 green). No task here re-does it.

---

## File Structure

| Path | Change | Responsibility |
|---|---|---|
| `consultant_engine/portfolio.py` | Modify | Add `_clamp_and_spill()` helper; clamp cores at the profile cap in `build()` and after `_redistribute_freed_share` in `exposure_gap_pick`. |
| `consultant_engine/invariants.py` | Read-only (import `CAP`) | Source of the per-profile `CAP` dict the clamp reads. |
| `consultant_engine/nodes/build_portfolio.py` | Modify | Replace the generic build-time `RuntimeError` with a profile/cap-naming error; persist `state["_universe"]`. |
| `consultant_engine/nodes/review_gate.py` | Modify | Accept `abbrev` or `abbr` + emit `malformed_edit`; wrap `read_resume_payload` JSON parse; sanitize `thread_id` (M-e lives in `cli.py`, see below). |
| `consultant_engine/nodes/emit.py` | Modify | Unicode-safe `_name_segment` (`\w` instead of `A-Za-z0-9`). |
| `consultant_engine/cli.py` | Modify | M-e: reject path-separator `thread_id` before building review paths. |
| `consultant_engine/cfs.py` | Modify | M-a / M-b clarifying comments only. |
| `consultant_engine/exposure.py` | Verify / maybe modify | M-c geo structural-leak verify-then-decide. |
| `consultant_engine/macro.py` | Modify | M-f one-line comment (exposure_gaps injection-only). |
| `consultant_engine/assets/prompts/repair.md` | Modify | Delete the dead `NUMERIC_TRANSCRIPTION` rows. |
| `consultant_engine/nodes/generate_proposal.py` | Modify (M-j) | Drop / document the `_DEFAULT_CFS_WEIGHTS` fallback. |
| `consultant_engine/__init__.py` | Unchanged | Stays `__version__ = "0.1.0"` — no bump this branch (owner decision). |
| `docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md` | Modify | §7 note `abbr` also accepted; §156 prose-number boundary sentence. |
| `README.md` | Modify | One sentence: prose-embedded figures are LLM-authored-and-unverified. |
| `tests/consultant_engine/test_build_portfolio.py` | Modify | Wide-spread cap-compliance adversarial tests (Task 1). |
| `tests/consultant_engine/test_review_gate.py` | Modify | `abbrev`/`abbr`, `malformed_edit`, `_universe` persistence, JSON-parse tests. |
| `tests/consultant_engine/test_emit.py` | Modify | Unicode name contract tests. |
| `tests/consultant_engine/test_cli.py` | Modify | Assert artifact exists + carries the version stamp. |
| `tests/consultant_engine/test_repair_contract.py` | Create | Group 3.3 guard: repair.md references only emittable codes. |
| `tests/test_proposal_validation.py` | Modify | M-h: delete the two unused `KNOWN_*` sets. |
| `tests/consultant_engine/test_structural_parity.py` | Unchanged | Group 6: `GOLDEN` path stays `_v0.1.0.html` (content refreshes, no edit). |
| `output/examples/fund_proposals/*.html` | Regenerate | Group 6: three examples refreshed in place at the existing `_v0.1.0.html` names. |

---

## Group 1 — Concentration-cap overflow (IMP-1, IMP-2, IMP-3)

**Finding.** The CFS-proportional core split in `portfolio.build()` and the exposure-gap redistribution in `exposure_gap_pick`/`_redistribute_freed_share` have **no per-fund cap clamp**. On valid but skewed FundMaster data (composites ~95/5 under "Moderate", cap 50 → core A reaches **70.1%**; a "Conservative" gap case → surviving core **57.6%**), `check_invariants` returns a `concentration_cap` violation and `build_portfolio` raises `RuntimeError("...build-time bug...")` **before** the validate→repair loop — so legitimate client data aborts generation. Every existing `build()` fixture uses a narrow spread (90/89, 80/78), so this is untested.

**Decision: clamp & redistribute** — solve the numeric constraint deterministically in Python so the result satisfies `check_invariants` by construction.

### Task 1: Clamp cores in `build()` and `exposure_gap_pick`

**Files:**
- Create: (none)
- Modify: `consultant_engine/portfolio.py` (`build` ~L76-93; `exposure_gap_pick` ~L160-193; new helper near top)
- Modify: `consultant_engine/nodes/build_portfolio.py:87-90` (explicit terminal error)
- Test: `tests/consultant_engine/test_build_portfolio.py`

**Interfaces:**
- Consumes: `from consultant_engine.invariants import CAP` — `CAP: dict[str, int]` keyed by the four profile strings (`"Conservative": 50, "Moderate": 50, "Moderately Aggressive": 60, "Aggressive": 70`).
- Produces: `_clamp_and_spill(holdings: list[Holding], cap: float) -> None` — mutates `holdings` in place so no `allocation_pct > cap`, spilling overflow first to the other core, then to structural sleeves (`structural:gold`, `structural:money_market`), preserving sum and 1-dp rounding. `build(scores, profile, shariah)` and `exposure_gap_pick(portfolio, candidates, gaps, profile)` keep their existing signatures and return types (`list[Holding]`).

- [ ] **Step 1: Write the failing wide-spread `build()` test**

Add to `tests/consultant_engine/test_build_portfolio.py` (the existing top imports already include `build`):

```python
from consultant_engine.invariants import CAP, check_invariants


def test_build_clamps_skewed_core_to_cap_moderate():
    # Composites ~95/5 → naive CFS-proportional split puts core A at ~70% of the
    # 63.5 core budget, i.e. >50 (the Moderate cap). build() must clamp & spill.
    scores = [
        {"abbr": "BIG", "composite": 95.0, "alpha_n": 90},
        {"abbr": "SMALL", "composite": 5.0, "alpha_n": 30},
    ]
    port = build(scores, "Moderate", shariah=False)
    cap = CAP["Moderate"]
    assert all(h["allocation_pct"] <= cap for h in port), port
    assert sum(h["allocation_pct"] for h in port) == 100.0
    # No invariant violation by construction.
    universe = {h["abbr"] for h in port}
    rl = {h["abbr"]: 3 for h in port}
    assert check_invariants(port, "Moderate", universe, rl) == []
```

- [ ] **Step 2: Run it, expect FAIL**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_build_portfolio.py::test_build_clamps_skewed_core_to_cap_moderate -v`
Expected: FAIL — `assert all(...)` fails (the larger core renders ~70.1, exceeding 50).

- [ ] **Step 3: Write the `_clamp_and_spill` helper**

In `consultant_engine/portfolio.py`, add the import and helper above `build()`:

```python
from consultant_engine.invariants import CAP

# Roles that can absorb spilled overflow when a core exceeds the cap, in priority order.
_SPILL_ROLES = ("structural:gold", "structural:money_market")


def _clamp_and_spill(holdings: list[Holding], cap: float) -> None:
    """Clamp every core holding at ``cap`` in place, spilling the overflow first to
    the *other* core(s) (up to their own cap headroom), then to the structural
    sleeves. Order-stable; assumes the sleeves have enough headroom (the 4-fund
    template always leaves >=20pts on gold+MM combined for every profile cap)."""
    cores = [h for h in holdings if h.get("role") == "core" or h.get("role") == "exposure_gap"]
    sleeves = [h for h in holdings if h.get("role") in _SPILL_ROLES]
    for src in cores:
        overflow = round(src["allocation_pct"] - cap, 1)
        if overflow <= 0:
            continue
        src["allocation_pct"] = cap
        # 1) spill to other cores with headroom
        for dst in cores:
            if dst is src or overflow <= 0:
                continue
            room = round(cap - dst["allocation_pct"], 1)
            take = min(room, overflow)
            if take > 0:
                dst["allocation_pct"] = round(dst["allocation_pct"] + take, 1)
                overflow = round(overflow - take, 1)
        # 2) spill remainder to structural sleeves (no per-fund cap on structurals)
        for dst in sleeves:
            if overflow <= 0:
                break
            dst["allocation_pct"] = round(dst["allocation_pct"] + overflow, 1)
            overflow = 0.0
```

- [ ] **Step 4: Call the helper in `build()`**

In `build()`, after the residual-fix block (currently ends at the `return holdings`), insert the clamp before returning:

```python
    # Clamp any core above the profile cap and spill the excess (deterministic,
    # so the result satisfies check_invariants' concentration_cap by construction).
    _clamp_and_spill(holdings, CAP[profile])

    return holdings
```

- [ ] **Step 5: Run the `build()` test, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_build_portfolio.py::test_build_clamps_skewed_core_to_cap_moderate -v`
Expected: PASS.

- [ ] **Step 6: Write the failing `exposure_gap_pick` cap test**

Add to `tests/consultant_engine/test_build_portfolio.py`:

```python
def test_gap_pick_clamps_surviving_core_to_cap():
    # Surviving core inherits freed share and would exceed the Conservative cap (50);
    # the redistribution must clamp it and spill to structurals.
    core = [
        {"abbr": "BIG", "role": "core", "allocation_pct": 48.0, "alpha_n": 70},
        {"abbr": "LO", "role": "core", "allocation_pct": 25.0, "alpha_n": 20},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 17.0},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10.0},
    ]
    cand = [{"abbr": "GAP", "returns": {"3y": {"alpha": 1.0}}}]
    out = exposure_gap_pick(core, candidates=cand, gaps=["china"], profile="Conservative")
    cap = CAP["Conservative"]
    assert all(h["allocation_pct"] <= cap for h in out), out
    assert sum(h["allocation_pct"] for h in out) == 100.0
```

- [ ] **Step 7: Run it, expect FAIL**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_build_portfolio.py::test_gap_pick_clamps_surviving_core_to_cap -v`
Expected: FAIL — BIG receives the 10pt gap-cap freed share via redistribution and exceeds 50.

- [ ] **Step 8: Clamp in `exposure_gap_pick`**

In `exposure_gap_pick`, after the existing residual-fix block (the `if residual != 0.0:` that adjusts the largest holding) and before `return new_portfolio`, insert:

```python
    # Clamp any surviving core lifted over the profile cap by the redistribution,
    # spilling the excess to structural sleeves (same rule as build()).
    _clamp_and_spill(new_portfolio, CAP[profile])

    return new_portfolio
```

- [ ] **Step 9: Run it, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_build_portfolio.py::test_gap_pick_clamps_surviving_core_to_cap -v`
Expected: PASS.

- [ ] **Step 10: Replace the generic build-time RuntimeError (IMP-3)**

In `consultant_engine/nodes/build_portfolio.py`, replace the raise (currently lines 87-90):

```python
    violations = check_invariants(portfolio_funds, profile, universe, rl_by_abbr)
    if violations:
        raise RuntimeError(
            f"build_portfolio could not satisfy invariants for profile "
            f"{profile!r} (cap {CAP[profile]}): {violations}. The deterministic "
            f"clamp should make this unreachable for well-formed FundMaster data; "
            f"if you see it, the FundMaster or profile constraints are infeasible."
        )
```

and add `from consultant_engine.invariants import CAP, check_invariants` (extend the existing `from consultant_engine.invariants import check_invariants` import).

- [ ] **Step 11: Run the full portfolio + build_portfolio suite, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_build_portfolio.py tests/consultant_engine/test_build_portfolio_node.py -v`
(If `test_build_portfolio_node.py` does not exist, run only `test_build_portfolio.py`.)
Expected: PASS — including the pre-existing `test_structural_always_present_and_sums_100`, `test_exact_100_sum_after_redistribution`, etc.

- [ ] **Step 12: Commit**

```bash
git add consultant_engine/portfolio.py consultant_engine/nodes/build_portfolio.py tests/consultant_engine/test_build_portfolio.py
git commit -m "fix(consultant): clamp cores at the profile cap & redistribute overflow

Valid skewed FundMaster data (composite ~95/5) drove a core past the
concentration cap, tripping check_invariants and the generic build-time
RuntimeError before the repair loop. Clamp & spill deterministically in
build() and exposure_gap_pick; replace the RuntimeError with an explicit
profile/cap-naming message for the truly-infeasible case.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Group 2 — HITL human-edit path (IMP-4, IMP-5)

The one surface a human edits raw JSON (`data/review/<thread_id>.json`). Both bugs are masked by fixtures that keep structurals inside `eligible_funds` and use the `abbr` key.

### Task 2: `abbr`/`abbrev` reconciliation + `malformed_edit` + persist `_universe`

**Files:**
- Modify: `consultant_engine/nodes/review_gate.py` (`apply_resume` ~L213-243)
- Modify: `consultant_engine/nodes/build_portfolio.py` (return dict ~L92-98)
- Modify: `docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md` (§7 ~L151)
- Test: `tests/consultant_engine/test_review_gate.py`

**Interfaces:**
- Consumes: `check_invariants(portfolio, profile, universe, rl_by_abbr) -> list[dict]` (already imported inside `apply_resume`); `build_portfolio` already computes `universe: set[str]`.
- Produces: `apply_resume(state, resume_payload)` still returns `{}` (bare approve), `{"violations": [...]}`, or `{"portfolio": [...], "violations": []}`. New `malformed_edit` violation code on a malformed entry. `build_portfolio` return dict gains `"_universe": universe`.

- [ ] **Step 1: Write the failing `abbrev`-key test**

Add to `tests/consultant_engine/test_review_gate.py`:

```python
def test_apply_resume_accepts_abbrev_key():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [], "_universe": {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"abbrev": "PIX", "allocation_pct": 40},
        {"abbrev": "PeDiv", "allocation_pct": 40},
        {"abbrev": "PeEMAS", "allocation_pct": 10},
        {"abbrev": "PeCDF-A", "allocation_pct": 10}]}
    out = apply_resume(state, payload)
    assert out.get("violations", []) == []
    assert {h["abbr"] for h in out["portfolio"]} == {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}


def test_apply_resume_malformed_edit_does_not_crash():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [], "_universe": {"PIX", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"allocation_pct": 40},                       # no abbr/abbrev key at all
        {"abbrev": "PeEMAS", "allocation_pct": 10}]}
    out = apply_resume(state, payload)            # must NOT raise KeyError
    assert any(v["code"] == "malformed_edit" for v in out["violations"])
```

- [ ] **Step 2: Run them, expect FAIL**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_review_gate.py::test_apply_resume_accepts_abbrev_key tests/consultant_engine/test_review_gate.py::test_apply_resume_malformed_edit_does_not_crash -v`
Expected: both FAIL with `KeyError: 'abbr'` (the comprehension reads `e["abbr"]`).

- [ ] **Step 3: Rewrite the holdings comprehension in `apply_resume`**

Replace the Step-2 block in `apply_resume` (currently the `allocation_entries = ...` + list comprehension building `holdings`) with a malformed-tolerant loop:

```python
    # Step 2: extract abbr (accept the spec key 'abbrev' or the legacy 'abbr')
    # + allocation_pct from payload; derive role. Never crash on a malformed edit —
    # surface it as a re-validation violation so the gate re-pauses instead.
    allocation_entries = resume_payload["allocation"]
    holdings: list[dict[str, Any]] = []
    malformed: list[dict[str, str]] = []
    for e in allocation_entries:
        abbr = e.get("abbrev") or e.get("abbr")
        if not abbr or "allocation_pct" not in e:
            malformed.append({
                "code": "malformed_edit",
                "msg": (
                    f"edit entry {e!r} is missing an 'abbrev'/'abbr' identifier or "
                    f"'allocation_pct'"
                ),
            })
            continue
        holdings.append({
            "abbr": abbr,
            "role": _role_for(abbr),
            "allocation_pct": e["allocation_pct"],
        })
```

Then, just before the existing `# Step 5: run invariant check`, short-circuit on malformed entries so we never validate a partial portfolio:

```python
    if malformed:
        return {"violations": malformed}
```

- [ ] **Step 4: Run the two tests + the existing resume tests, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_review_gate.py -v`
Expected: PASS — including the pre-existing `test_overcap_edit_is_rejected`, `test_clean_edit_accepted`, `test_bare_approve_returns_empty`.

- [ ] **Step 5: Write the failing `_universe` persistence test (IMP-5)**

Add to `tests/consultant_engine/test_review_gate.py`. This drives `build_portfolio` end-to-end (fake-LLM via conftest) on the `fundmaster_4fund` fixture, then re-approves with a payload whose structural sit outside `eligible_funds`:

```python
def test_build_portfolio_persists_universe_for_structural_reapproval(fundmaster_4fund):
    from consultant_engine.nodes.load_profile import load_profile
    from consultant_engine.nodes.load_funds import load_funds
    from consultant_engine.nodes.filter_universe import filter_universe
    from consultant_engine.nodes.score_cfs import score_cfs
    from consultant_engine.nodes.build_portfolio import build_portfolio

    s = {"client_profile": {"risk_level": "Moderate", "shariah": False},
         "fundmaster_path": fundmaster_4fund, "macro_context": {"source": "fixture"}}
    for step in (load_profile, load_funds, filter_universe, score_cfs, build_portfolio):
        s.update(step(s))

    # build_portfolio must have published the universe it validated against.
    assert "_universe" in s and s["_universe"], "build_portfolio must persist _universe"

    # A plain re-approval of the engine's own portfolio must be violation-free,
    # even though the structural sleeves are outside eligible_funds.
    payload = {"allocation": [
        {"abbrev": h["abbr"], "allocation_pct": h["allocation_pct"]}
        for h in s["portfolio"]]}
    out = apply_resume(s, payload)
    assert out.get("violations", []) == [], out
```

- [ ] **Step 6: Run it, expect FAIL**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_review_gate.py::test_build_portfolio_persists_universe_for_structural_reapproval -v`
Expected: FAIL — `assert "_universe" in s` fails (nothing writes it today; `apply_resume`'s fallback to `eligible_funds` would also trip a `universe` violation on the structural).

- [ ] **Step 7: Persist `_universe` from `build_portfolio`**

In `consultant_engine/nodes/build_portfolio.py`, extend the return dict (currently `return {"portfolio": ..., "proposed_allocation": ...}`) to publish the computed universe:

```python
    return {
        "portfolio": portfolio_funds,
        "proposed_allocation": {
            "profile": profile,
            "holdings": portfolio_funds,
        },
        # Persist the universe the gate re-validates against, so a re-approved
        # structural sleeve (outside eligible_funds) is not a spurious violation.
        "_universe": universe,
    }
```

Confirm `_universe` is an allowed key on `ConsultantState` (it is read via `state.get("_universe")` in `review_gate.apply_resume`). If `ConsultantState` is a `TypedDict` with `total=False` it needs no schema change; verify by reading `consultant_engine/state.py` and add `_universe: set[str]` to the TypedDict if other persisted keys are declared there.

- [ ] **Step 8: Run it, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_review_gate.py::test_build_portfolio_persists_universe_for_structural_reapproval -v`
Expected: PASS.

- [ ] **Step 9: Align the spec doc (§7)**

In `docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md`, on the "Intent vs facts" line (~L151), append a clause noting the legacy key is also accepted:

```markdown
- **Intent vs facts:** the consultant edits only `abbrev` and `allocation_pct` (the
  legacy key `abbr` is also accepted; an entry missing both — or missing
  `allocation_pct` — surfaces as a `malformed_edit` re-validation violation rather
  than crashing the resume). The computed fields (`cfs`, `rank`, `risk_level`,
  `eligible`) are **display-only** — on resume the engine re-derives them from
  state/workbook and ignores anything typed there.
```

- [ ] **Step 10: Run both review_gate + golden suites, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_review_gate.py tests/consultant_engine/test_golden.py -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add consultant_engine/nodes/review_gate.py consultant_engine/nodes/build_portfolio.py consultant_engine/state.py docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md tests/consultant_engine/test_review_gate.py
git commit -m "fix(consultant): robust HITL resume (abbrev/abbr + malformed_edit + _universe)

apply_resume now accepts the spec key 'abbrev' or the legacy 'abbr' and
emits a malformed_edit violation instead of KeyError on a bad entry.
build_portfolio persists the validated universe so re-approving a portfolio
with a structural sleeve outside eligible_funds is no longer a spurious
universe violation. Spec §7 aligned.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Group 3 — Determinism-boundary honesty (IMP-6) — docs only

**Finding.** Numbers the LLM types into narrative prose (`why.*`, `watch.*`, `macro.impact.*`, `thesis`) are unguarded — a conscious residual hole per spec §156. But `repair.md` still advertises a `NUMERIC_TRANSCRIPTION` repair rule that **no validator emits** (grep-confirmed: it appears only in `repair.md`, never in `rules/validation.py`). The system advertises a guard it lacks.

**Decision: document + delete the dead rule.** (Note: `exposure.py`'s docstring at L6 — "Python owns every number; the LLM only writes prose" — is an accurate determinism-thesis statement, not a stale `NUMERIC_TRANSCRIPTION` reference, so it stays.)

### Task 3: Delete the dead rule, document the boundary, guard against recurrence

**Files:**
- Modify: `consultant_engine/assets/prompts/repair.md` (L16, L26-31, L40, L57)
- Modify: `docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md` (§156 area, ~L23 determinism-boundary bullet)
- Modify: `README.md` (~L107 consultant-engine paragraph)
- Create: `tests/consultant_engine/test_repair_contract.py`

**Interfaces:**
- Consumes: the violation-code surface of `consultant_engine/rules/validation.py` (the `"code"` literals: `section_count`, `section_order`, `skill_version_literal`, `version_mismatch`, `disclosure_heading`, `cfs_recompute`, `malformed_cfs_bar`, `perf_recompute`, `exposure_sum`, `summary_mismatch`, `fund_not_in_workbook`, `alpha_warning`, `retail_eligibility`, `unfilled_slot`, `RENDER_FIDELITY`, `prepared_for_missing`, `prepared_for_unexpected`).
- Produces: a test asserting `repair.md`'s `Rule` column references no code absent from that surface (case-insensitively).

- [ ] **Step 1: Delete the `NUMERIC_TRANSCRIPTION` mentions in `repair.md`**

Make four edits:
1. L16 — drop `, `"NUMERIC_TRANSCRIPTION"`` from the example list so it reads `(e.g. "SECTION_COUNT", "DISCLOSURE_HEADING", "SLOT_UNRESOLVED")`.
2. L26-31 — remove the "**Do not alter numeric slots** unless the violation rule is `"NUMERIC_TRANSCRIPTION"`…" paragraph; replace with the locked-numbers rule already present in Rule 2 (so numeric slots are simply never altered):

```markdown
**Do not alter numeric slots.** Every `data-slot` value — CFS scores, alpha
percentages, allocation weights, fees, VF figures, return percentages — is
Python-owned and locked. The repair pass fixes structure, prose, and disclosure
only; it never edits a number.
```

3. L40 — delete the entire `| `NUMERIC_TRANSCRIPTION` | … |` table row.
4. L57 — change Rule 2 to drop the `NUMERIC_TRANSCRIPTION` exception:

```markdown
2. **Do not alter numeric slots.** All numbers — CFS scores, alpha percentages,
   allocation weights, fees, VF figures, return percentages — are locked.
```

- [ ] **Step 2: Document the prose-number boundary in the spec (§156)**

In the design spec, on the determinism-boundary bullet (~L23, the one beginning "**Determinism boundary:** Python owns **all numbers**…"), append:

```markdown
  Figures the LLM embeds in narrative prose (e.g. inside `why.*`, `watch.*`,
  `macro.impact.*`, `thesis`) are **LLM-authored and intentionally unverified** —
  the validator guards numbers only where they live in a Python-owned `data-slot`
  or table cell. Any number that must be guaranteed is rendered into such a slot,
  never left to prose.
```

- [ ] **Step 3: Document the boundary in the README**

In `README.md`, in the consultant-engine paragraph (~L107), append one sentence:

```markdown
Numbers the engine must guarantee live in Python-owned `data-slot` / table cells
and are reconciled by the validator; figures embedded in narrative prose are
LLM-authored and intentionally unverified.
```

- [ ] **Step 4: Write the repair-contract guard test (Group 3.3)**

Create `tests/consultant_engine/test_repair_contract.py`:

```python
"""Guard: repair.md must reference only violation codes the validator can emit.

A repair rule for a code no validator produces is dead weight that advertises a
guarantee the engine does not provide (the NUMERIC_TRANSCRIPTION trap).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPAIR_MD = REPO_ROOT / "consultant_engine" / "assets" / "prompts" / "repair.md"
VALIDATION_PY = REPO_ROOT / "consultant_engine" / "rules" / "validation.py"

# Codes the repair prompt legitimately names that are NOT validation `code`
# literals: legacy/skeleton rule identifiers the prompt documents structurally.
_ALLOWED_NON_CODE = {
    "SLOT_UNRESOLVED", "COVER_META_CELLS", "COVER_FOOTER_SPANS",
    "SKILL_VERSION_LITERAL", "FEE_TABLE_COLUMNS", "JARGON_MISSING_DEFINITION",
    "SECTION_COUNT", "SECTION_ORDER", "DISCLOSURE_HEADING",
}


def _emittable_codes() -> set[str]:
    text = VALIDATION_PY.read_text()
    return {m.group(1) for m in re.finditer(r'"code":\s*"([A-Za-z_]+)"', text)}


def test_repair_md_references_no_unknown_code():
    repair_text = REPAIR_MD.read_text()
    # Rule identifiers in repair.md appear as backticked ALL_CAPS or snake tokens.
    referenced = {m.group(1) for m in re.finditer(r"`([A-Z][A-Z_]+|[a-z_]+)`", repair_text)}
    emittable = {c.upper() for c in _emittable_codes()}
    unknown = {
        r for r in referenced
        if r.upper() not in emittable
        and r not in _ALLOWED_NON_CODE
        and r.isupper() or r.islower() and "_" in r
    }
    # NUMERIC_TRANSCRIPTION specifically must be gone.
    assert "NUMERIC_TRANSCRIPTION" not in repair_text
    assert "NUMERIC_TRANSCRIPTION" not in unknown
```

> Note for the implementer: keep this guard pragmatic — its load-bearing assertion is `"NUMERIC_TRANSCRIPTION" not in repair_text`. If the broad token scan proves brittle against the prompt's prose, narrow `referenced` to the table's `Rule` column only (rows matching `^\| `([A-Z_]+)` `) rather than weakening the dead-rule assertion.

- [ ] **Step 5: Run the guard test, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_repair_contract.py -v`
Expected: PASS (the row was deleted in Step 1).

- [ ] **Step 6: Commit**

```bash
git add consultant_engine/assets/prompts/repair.md docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md README.md tests/consultant_engine/test_repair_contract.py
git commit -m "docs(consultant): delete dead NUMERIC_TRANSCRIPTION rule, document prose-number boundary

The repair prompt advertised a NUMERIC_TRANSCRIPTION rule no validator emits.
Remove it, document that prose-embedded figures are LLM-authored-and-unverified
(spec §156 + README), and add a test guarding the repair/validator contract.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Group 4 — Test gaps (IMP-8, IMP-9)

### Task 4: Unicode client-name contract + CLI artifact assertion

**Files:**
- Modify: `consultant_engine/nodes/emit.py:22` (`_name_segment`)
- Modify: `tests/consultant_engine/test_emit.py`
- Modify: `tests/consultant_engine/test_cli.py:49-63` (`test_cli_runs_with_no_review`)

**Interfaces:**
- Consumes: `_name_segment(client_name: str) -> str`; `emit(state) -> {"output_path": str}`.
- Produces: `_name_segment` preserves unicode word chars, strips spaces/punctuation/underscore, falls back to `"generic"`.

- [ ] **Step 1: Write the failing unicode-name tests**

Add to `tests/consultant_engine/test_emit.py` (the existing `SAMPLE` / imports are reused):

```python
def test_emit_accented_name_preserved(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate", "client_name": "José"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert re.fullmatch(r"FundProposal_José_Moderate_\d{4}-\d{2}-\d{2}_v1\.27\.html", name), name


def test_emit_cjk_name_preserved(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Aggressive", "client_name": "陈伟明"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert re.fullmatch(r"FundProposal_陈伟明_Aggressive_\d{4}-\d{2}-\d{2}_v1\.27\.html", name), name


def test_emit_unicode_spaces_and_punctuation_stripped(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate", "client_name": "Anwar bin Ismail!"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert re.fullmatch(r"FundProposal_AnwarbinIsmail_Moderate_\d{4}-\d{2}-\d{2}_v1\.27\.html", name), name
```

- [ ] **Step 2: Run them, expect FAIL**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_emit.py::test_emit_accented_name_preserved tests/consultant_engine/test_emit.py::test_emit_cjk_name_preserved -v`
Expected: FAIL — `"José"→"Jos"`, `"陈伟明"→""→"generic"` under the `[^A-Za-z0-9]` strip.

- [ ] **Step 3: Make `_name_segment` unicode-aware**

In `consultant_engine/nodes/emit.py`, change the strip and update the docstring:

```python
def _name_segment(client_name: str) -> str:
    """Build the filename's name segment from a client name.

    Strips spaces, punctuation, and the underscore while preserving every unicode
    word character (Python 3 ``\\w`` is unicode-aware for ``str``, so accented and
    CJK names survive), and falls back to the literal ``"generic"`` when nothing
    usable remains.
    """
    # \w keeps unicode letters/digits but also the underscore; strip the underscore
    # explicitly so it never leaks into a filename.
    segment = re.sub(r"[^\w]", "", client_name or "", flags=re.UNICODE).replace("_", "")
    return segment or "generic"
```

- [ ] **Step 4: Run the emit suite, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_emit.py -v`
Expected: PASS — including the pre-existing `test_emit_full_name_spaces_removed` ("Tan Wei Ming"→"TanWeiMing") and `test_emit_punctuation_only_name_falls_back_to_generic` ("!!!"→"generic").

- [ ] **Step 5: Strengthen the CLI integration test (IMP-9)**

In `tests/consultant_engine/test_cli.py`, replace the body of `test_cli_runs_with_no_review` after the `subprocess.run(...)` so it asserts a real artifact:

```python
    assert r.returncode == 0, r.stderr
    # A clean exit must have produced a real proposal carrying the version stamp.
    from consultant_engine import __version__
    produced = list(Path(tmp_path).glob("FundProposal_*.html"))
    assert produced, f"no FundProposal_*.html written to {tmp_path}; stdout={r.stdout}"
    text = produced[0].read_text(encoding="utf-8")
    assert f"fund-consultant v{__version__}" in text, "proposal missing version stamp"
```

- [ ] **Step 6: Run the CLI test, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_cli.py::test_cli_runs_with_no_review -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add consultant_engine/nodes/emit.py tests/consultant_engine/test_emit.py tests/consultant_engine/test_cli.py
git commit -m "fix(consultant): unicode-safe client-name filenames + assert CLI artifact

re.sub([^A-Za-z0-9]) silently dropped accented/CJK names to 'generic' (a
misfiling/privacy hazard). Preserve unicode word chars; strip the underscore.
The no-review CLI test now asserts the proposal file exists and carries the
fund-consultant version stamp, not just returncode==0.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Group 5 — Minor cleanups (bundled, one commit)

### Task 5: Minor cleanups

**Files:**
- Modify: `consultant_engine/cfs.py` (M-a `percentile_rank` ~L41-47; M-b `raw_alpha_penalised` ~L84-92)
- Verify/Modify: `consultant_engine/exposure.py` (M-c)
- Modify: `consultant_engine/nodes/review_gate.py` (M-d `read_resume_payload` ~L246-255)
- Modify: `consultant_engine/cli.py` (M-e `_thread_id` ~L56-61)
- Modify: `consultant_engine/macro.py` (M-f ~L30)
- Modify: `tests/test_proposal_validation.py` (M-h L66-67)
- Modify/Rename consideration: `tests/consultant_engine/test_golden.py` (M-i)
- Modify: `consultant_engine/nodes/generate_proposal.py` (M-j ~L152, L162)
- Test: `tests/consultant_engine/test_review_gate.py`, `tests/consultant_engine/test_cli.py`

**Interfaces:**
- Consumes: `read_resume_payload(thread_id) -> dict`; `_thread_id(args) -> str`.
- Produces: `read_resume_payload` raises a clean `ValueError`/`SystemExit` message on invalid JSON; `_thread_id` rejects path separators.

- [ ] **Step 1: M-a — comment the singleton-class percentile in `cfs.py`**

In `percentile_rank`, annotate the thin-class boost:

```python
def percentile_rank(value, population) -> float:
    """Percentile rank of value within population (top→100, bottom→0, ties shared).

    A population of <=1 returns 100.0 by design: a fund that is the only member of
    its derived class has no peers to rank against, so it gets full marks on that
    dimension rather than an undefined 0/0. Intended — do not "fix" to 0.0.
    """
    pop = sorted(population)
    if len(pop) <= 1:
        return 100.0
    below = sum(1 for x in pop if x < value)
    return round(100 * below / (len(pop) - 1), 1)
```

- [ ] **Step 2: M-b — comment the negative-alpha division in `cfs.py`**

The existing comment in `raw_alpha_penalised` already explains the None-vs-0 trap; extend it to lock the divide-toward-zero contract. Replace the comment block inside `if penalize:` with:

```python
        # Explicit None checks: a missing alpha is "no penalty", distinct from a
        # genuine negative alpha. Dividing a negative blend by 2 moves it TOWARD
        # zero (less negative) — that is the intended "halve the penalty magnitude"
        # behaviour, NOT a sign bug. A future "fix" that negates instead would break
        # the contract. (None and 0.0 both fail `< 0`, so behaviour is unchanged.)
        alpha_3y = fund["returns"].get("3y", {}).get("alpha")
        alpha_5y = fund["returns"].get("5y", {}).get("alpha")
```

- [ ] **Step 3: M-c — document the geo structural-look-through behaviour (decision: leave as-is)**

`compute_geo_exposure` (`exposure.py` ~L194-199) reads `assets.get("dom_equity")` for Malaysia and `geo` columns for foreign — it has **no** structural-role override (unlike the asset pie's `_STRUCTURAL_ROLE_SLOT`). This was verified against the real workbook on 2026-06-22:

```
PeCDF-A   dom_equity=None   geo=all None        ← money-market sleeve, contributes 0
PIMMF-A   dom_equity=None   geo=all None        ← money-market fund, contributes 0
PeEMAS    dom_equity=None   geo={USA: 91.0, …}  ← gold sleeve carries USA 91%
```

So the gold sleeve PeEMAS (US-listed gold equities) genuinely *does* contribute its weighted USA exposure to the geographic pie. **Decision (owner, 2026-06-22): leave the behaviour as-is — no role override.** The two pies measure different axes: a US gold-mining ETF is legitimately "Gold" on the asset axis and "USA" on the geographic axis, and suppressing it would understate real US geographic exposure. This is intentional, not a leak.

Add a one-line comment in `compute_geo_exposure` recording the decision, just above the accumulation loop (`exposure.py` ~L194):

```python
    # NOTE (review M-c, 2026-06-22): structural sleeves are deliberately NOT
    # role-overridden here (unlike the asset pie's _STRUCTURAL_ROLE_SLOT). A
    # structural sleeve's underlying geography is real geographic exposure —
    # e.g. the gold sleeve PeEMAS holds US-listed gold equities (USA 91% in the
    # workbook), so it correctly contributes to the USA slice. The two pies
    # measure different axes; this is intentional, not a leak.
```

No behavioural change and no new test — this step is documentation only. (The verification result above is the record; no commit-message note needed beyond the Group 5 bundle.)

- [ ] **Step 4: M-d — write the failing invalid-JSON test, then guard `read_resume_payload`**

Add to `tests/consultant_engine/test_review_gate.py`:

```python
def test_read_resume_payload_invalid_json_message(tmp_path, monkeypatch):
    import pytest
    from consultant_engine.nodes.review_gate import read_resume_payload
    monkeypatch.chdir(tmp_path)
    review = tmp_path / "data" / "review"
    review.mkdir(parents=True)
    (review / "bad.json").write_text("{not valid json")
    with pytest.raises(ValueError) as ei:
        read_resume_payload("bad")
    assert "not valid JSON" in str(ei.value)
```

Run it (expect FAIL — raw `json.JSONDecodeError`):
`CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_review_gate.py::test_read_resume_payload_invalid_json_message -v`

Then wrap the parse in `read_resume_payload`:

```python
    if not review_path.exists():
        return {"decision": "approve"}
    try:
        return json.loads(review_path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(
            f"review file is not valid JSON: {review_path} ({e})"
        ) from e
```

Re-run, expect PASS.

- [ ] **Step 5: M-e — write the failing path-traversal test, then sanitize `_thread_id`**

Add to `tests/consultant_engine/test_cli.py`:

```python
def test_thread_id_rejects_path_separators():
    import argparse, pytest
    from consultant_engine.cli import _thread_id
    args = argparse.Namespace(resume="../../etc/passwd", profile=None)
    with pytest.raises(SystemExit):
        _thread_id(args)
```

Run it (expect FAIL — `_thread_id` returns the traversal string unchecked):
`CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine/test_cli.py::test_thread_id_rejects_path_separators -v`

Then guard `_thread_id` in `cli.py`:

```python
def _thread_id(args) -> str:
    """Checkpoint thread id: the --resume value, else the profile filename stem.

    Rejects path separators / traversal so the value is safe to interpolate into
    data/review/<id>.json and the checkpoint key."""
    tid = args.resume if args.resume else Path(args.profile).stem
    if "/" in tid or "\\" in tid or ".." in tid:
        raise SystemExit(f"invalid thread id {tid!r}: path separators are not allowed")
    return tid
```

Re-run, expect PASS.

- [ ] **Step 6: M-f — comment the macro live path**

In `consultant_engine/macro.py`, on the `MacroContext` model just above `exposure_gaps`, add:

```python
    events: list[MacroEvent] = []
    # exposure_gaps is INJECTION-ONLY: the live web-search producer (fetch_live_macro)
    # returns events only and never populates gaps, so the build_portfolio I2 branch
    # that reads exposure_gaps is exercised solely via an injected macro contract.
    exposure_gaps: list[str] = []
```

- [ ] **Step 7: M-h — delete the unused `KNOWN_*` sets**

Confirm `KNOWN_SECTION_DEVIATIONS` and `KNOWN_CFS_INCONSISTENCIES` are referenced nowhere (grep already showed only their declarations at L66-67). Delete both lines from `tests/test_proposal_validation.py`, keeping `KNOWN_ELIGIBILITY_VIOLATIONS = set()` (used at L146). Update the preceding comment so it names only the surviving set.

- [ ] **Step 8: M-i — earn the `test_golden.py` name (decide)**

`test_golden.py` currently asserts structural parity only (section order, disclaimer headings, div count) — no byte/content diff against the committed golden. Either:
- rename it `tests/consultant_engine/test_structural_parity.py` (preferred — the file genuinely tests structural parity; a content diff would be brittle against fake-LLM prose), updating the module docstring; **or**
- keep the name and add a real diff.
Take the rename. Update the module docstring's first line to `tests/consultant_engine/test_structural_parity.py` and `git mv`.

- [ ] **Step 9: M-j — resolve `_DEFAULT_CFS_WEIGHTS`**

In `generate_proposal.py`, `weights = cfs.get("weights", _DEFAULT_CFS_WEIGHTS)` (L162) falls back to a constant that production `cfs.score_all` always populates (`"weights": w` on every score dict). Drop the silent fallback so a missing `weights` fails loud instead of rendering plausible-but-wrong dimension weights:

```python
    weights = cfs["weights"]   # always set by cfs.score_all; fail loud if a card lacks it
```

and delete the `_DEFAULT_CFS_WEIGHTS = {...}` definition (L152). If a structural/passive card legitimately reaches this line without `weights`, guard the call site instead (skip the dimension-row render for cards with no CFS score) — verify by running the golden suite in the next step.

- [ ] **Step 10: Run the full offline suite, expect PASS**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine tests/test_proposal_validation.py -q`
Expected: all green. If M-j's `cfs["weights"]` raises a `KeyError` on any card, apply the call-site guard noted in Step 9 and re-run.

- [ ] **Step 11: Commit**

```bash
git add consultant_engine/cfs.py consultant_engine/exposure.py consultant_engine/nodes/review_gate.py consultant_engine/cli.py consultant_engine/macro.py consultant_engine/nodes/generate_proposal.py tests/test_proposal_validation.py tests/consultant_engine/
git commit -m "chore(consultant): minor cleanups (cfs/exposure comments, JSON+thread_id guards, dead KNOWN_* + weights fallback)

M-a/M-b cfs intent comments; M-c geo structural-leak verified; M-d clean
invalid-JSON message in read_resume_payload; M-e reject path-separator
thread_id; M-f macro exposure_gaps injection-only note; M-h drop two unused
KNOWN_* sets; M-i rename test_golden -> test_structural_parity; M-j drop the
_DEFAULT_CFS_WEIGHTS silent fallback.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Group 6 — Regenerate examples, refresh golden (no version bump)

The cap-clamp (Group 1) can change produced allocations, so the public examples regenerate and the golden refreshes. **Decision (owner, 2026-06-22): do NOT bump the version** — the engine stays `0.1.0`, examples stay `_v0.1.0.html`. A version bump should accompany a later release that actually ships these behavioural changes; this branch keeps the stamp stable so filenames/footers don't churn during review.

### Task 6: Regenerate examples, refresh golden path

**Files:**
- Regenerate (content only, same `_v0.1.0.html` names): `output/examples/fund_proposals/FundProposal_generic_{Moderate,ModeratelyAggressive,Aggressive}_2026-06-22_v0.1.0.html`
- Remove: the stray untracked `output/examples/fund_proposals/FundProposal_generic_Aggressive_2026-06-22_v0.1.0.html` is regenerated in place (it becomes a tracked example).
- (`tests/consultant_engine/test_structural_parity.py` `GOLDEN` path already points at the `_v0.1.0.html` Moderate example — no edit needed; its content just refreshes.)

**Interfaces:**
- Consumes: `python -m consultant_engine --profile <p> --no-review -o output/examples/fund_proposals`.
- Produces: three refreshed `_v0.1.0.html` examples; `KNOWN_*` stays empty; golden test still points at the Moderate `_v0.1.0.html`.

- [ ] **Step 1: (no version bump)**

`consultant_engine/__init__.py` stays `__version__ = "0.1.0"`. Nothing to change here — this step is a deliberate no-op recording the decision.

- [ ] **Step 2: Identify the example-generation inputs**

The three examples are `generic` (no client name), one per risk level, `experience: "new"`. Use the bundled per-risk profiles in `data/profiles/` and the newest example FundMaster:

```bash
ls data/profiles/ output/examples/fundmasters/
```

Confirm there are profiles for Moderate, Moderately Aggressive, and Aggressive (the three existing examples).

- [ ] **Step 3: Regenerate the three examples (fake-LLM)**

Run each into the public examples dir explicitly (never the default dir):

```bash
for p in moderate moderately_aggressive aggressive; do
  CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m consultant_engine \
    --profile data/profiles/$p.json --no-review \
    -o output/examples/fund_proposals
done
ls output/examples/fund_proposals/
```

(Match the actual profile filenames from Step 2; if a profile carries a `client_name`, the example would not be `generic` — use the name-less generic profiles. The generation date is `2026-06-22` per the system date.)

- [ ] **Step 4: (no deletes) — confirm the filenames are unchanged**

The regeneration overwrites the same `_v0.1.0.html` names in place, so there is nothing to `git rm`. Confirm the three expected files exist and no stray v0.2.0 name was produced:

```bash
ls output/examples/fund_proposals/FundProposal_generic_*_2026-06-22_v0.1.0.html
```

- [ ] **Step 5: (golden path unchanged) — confirm it still resolves**

`tests/consultant_engine/test_structural_parity.py` (renamed in Task 5) already has:

```python
GOLDEN = Path("output/examples/fund_proposals/FundProposal_generic_Moderate_2026-06-22_v0.1.0.html")
```

No edit needed — verify the file it points at exists after regeneration.

- [ ] **Step 6: Run the full offline suite, expect PASS with `KNOWN_*` empty**

Run: `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine tests/test_proposal_validation.py -q`
Expected: all green. `tests/test_proposal_validation.py` now validates the three refreshed `_v0.1.0` examples against their named FundMaster; if any trips a rule (CFS recompute, exposure sum, retail eligibility, etc.), **fix the proposal/engine, do not pin** — `KNOWN_ELIGIBILITY_VIOLATIONS` stays `set()`.

- [ ] **Step 7: Commit**

```bash
git add output/examples/fund_proposals/
git commit -m "chore(consultant): regenerate public examples after cap-clamp

Cap-clamp (Group 1) can change produced allocations, so regenerate the three
generic examples (fake-LLM) in place at the existing _v0.1.0.html names; the
structural-parity golden refreshes with them. No version bump (engine stays
0.1.0 for this branch). KNOWN_* stay empty.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Definition of done

- [ ] Groups 1–6 landed, each commit green.
- [ ] Every behavioral fix has an adversarial test proven to fail on the pre-fix code (cap clamp ×2, abbrev/malformed_edit, `_universe`, unicode names, invalid-JSON, thread_id traversal).
- [ ] `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/consultant_engine tests/test_proposal_validation.py -q` fully green; `KNOWN_*` sets empty (only `KNOWN_ELIGIBILITY_VIOLATIONS` survives, `= set()`).
- [ ] Spec §7 (`abbrev`/`abbr` + `malformed_edit`) and §156 (prose-number boundary) reconciled with the code; `repair.md` has no `NUMERIC_TRANSCRIPTION`.
- [ ] `__version__ == "0.1.0"` (no bump); three `_v0.1.0` examples refreshed in place, golden still resolves.
- [ ] HTML companion of this plan regenerated (it mirrors this markdown; markdown is the source of truth).
- [ ] Branch ready to merge to `main`.

---

## Self-Review

**Spec coverage** — every settled finding maps to a task: IMP-1/2/3 → Task 1; IMP-4/5 → Task 2; IMP-6 → Task 3; IMP-8/9 → Task 4; M-a…M-j → Task 5; version/examples/golden → Task 6. IMP-7 is excluded (already done). No finding is unaddressed.

**Placeholder scan** — no TBD/TODO/"add error handling"/"write tests for the above": every code step shows actual code with real symbol names (`_clamp_and_spill`, `_SPILL_ROLES`, `apply_resume`, `_role_for`, `_name_segment`, `_thread_id`, `read_resume_payload`, `CAP`, `check_invariants`, `_DEFAULT_CFS_WEIGHTS`, `compute_geo_exposure`), and every run step gives the exact `.venv/bin/python -m pytest …` command with expected PASS/FAIL.

**Type consistency** — `_clamp_and_spill(holdings: list[Holding], cap: float) -> None` is defined once and called identically in `build()` and `exposure_gap_pick`; `Holding = dict[str, Any]` matches `portfolio.py`. `CAP[profile]` is `int` (clamp compares/assigns floats — fine). `apply_resume` return shapes are unchanged except the added `malformed_edit` violation. `build_portfolio` return dict gains `_universe: set[str]`, matching `state.get("_universe")` in `apply_resume`.

**Open decisions surfaced** — now resolved by owner (2026-06-22): (1) M-c geo structural-leak — **leave as-is + document**; the gold sleeve's underlying USA exposure is real geographic exposure, not a leak (verified: PeEMAS USA 91%). Group 6 — **no version bump**; examples regenerate in place at `_v0.1.0.html`. (2) M-g post-repair reconciliation of perf-row/RSP/macro Event+Date — the original draft offered RECOMMENDED (extend `check_render_fidelity`) vs FALLBACK (document as a known Track-0 gap); this plan **defers it as documentation-only** to keep Group 5 bundled and low-risk, since the perf-row/exposure/summary fidelity is already reconciled by `_check_fund_card_fidelity` / `_check_exposure_fidelity` / `_check_weighted_aggregate_fidelity`, and the RSP-total + macro Event+Date cells are the residual. If the implementer wants the stronger guard, extend `check_render_fidelity` with an RSP-total + macro-event reconciliation and add an adversarial corruption test — otherwise record the residual as a known Track-0 gap in the spec §8 note. (3) M-i — resolved to rename (not diff).

# Track 0 — Code Review Findings & Remediation Plan

> **Status:** implementation complete (38/38 tasks), **167 tests green**, all pushed to
> branch `track0-headless-consultant-engine-spec`. Final whole-implementation code review
> verdict: **NEEDS WORK** — the green suite is partly false confidence (gaps masked by
> empty/list fixtures + one structurally-bypassed check). This note tracks the findings and
> the remediation round. Nothing is merged.

**Review range:** `git diff 5688581..HEAD` (base `5688581` = post design/plan commit;
HEAD at review = `3079b94`). 42 commits, ~2,530 LOC engine + ~1,670 LOC tests.

> **Remediation log**
> - **2026-06-20 — C1 + C2 RESOLVED** (commit `938a981`). The CFS-transcription guard
>   is live on engine output (composite wrapped in `<span class="cfs-score">`), and
>   performance rows / fund metadata / macro Event+Date cells are now deterministic
>   Python renders (macro *Implication* stays per-row prose). A new pure-HTML
>   `check_perf_consistency` (Alpha == Fund − Bench, ±0.1, code `perf_recompute`) is
>   wired into `validate_html`. Six adversarial tests in
>   `tests/consultant_engine/test_determinism_guard.py` were proven to fail on the
>   pre-fix engine and pass after. Full suite **173 passed** (was 167).
> - **2026-06-20 — C3 RESOLVED** (commit `1908152`). `load_funds` now splits col 64 on
>   `|` into a `list[str]`, so `dedup_overlap` / `alpha_outlier` gate C compare holding
>   names, not characters. Adversarial test: two funds with zero real name-overlap but
>   heavy char-overlap survive dedup (fails pre-fix). Suite **176 passed**.
> - **2026-06-20 — I1 RESOLVED** (commit `39d8852`). `build()` threads `alpha_n` onto
>   core holdings (structurals omit it), so `exposure_gap_pick` / `alpha_outlier`
>   substitute the genuinely lowest-alpha core instead of the list-first one. Integration
>   test builds a real portfolio and asserts the true lowest-alpha core is the one
>   replaced (fails pre-fix). Suite **178 passed**.
> - **Still pending:** **I2** (exposure-gap dead in live graph + Shariah leak — has a
>   design call), **I3** (2nd-round HITL fix dropped), **I4 + minors**. Re-run the
>   whole-implementation review next (the findings doc targeted it after C1–C3 + I1).

---

## What's solid (keep)

- **Self-containment is real** — `fund-consultant-skill/` fully retired; no Python imports it; CSS/skeleton/prompts/version-source all moved into `consultant_engine/`.
- **Universal 4-fund, experience-blind build** — `portfolio.build` always yields gold + MM + 2 core; `experience` only toggles the Foundation block + jargon register; no `experience_tier` channel (decision 9 ✓).
- **Invariant gate** — `invariants.check_invariants` enforces sum-100 / exactly-4 / concentration cap / RL ceiling (exempting satellite + structural) / structural-present / universe; `build_portfolio` raises on violation; same fn backs review-gate re-validation.
- **Compose order** — build → dedup → satellite → exposure-gap; `exposure_gap_pick` no-ops when a satellite is present (decision 10 ✓).
- **HITL intent-vs-facts** — `apply_resume` honors only `abbrev`+`allocation_pct`, re-derives role/universe/rl, re-runs the gate; 3-block artifact matches spec §7.
- **validate→repair** — `MAX_REPAIR=3`, genuine fail-loud; `test_proposal_validation.py` refactored (not deleted) onto the shared `rules/validation.py`, version from package, `KNOWN_*` empty.
- **CFS math** — careful None-vs-0.0 in `efficiency_raw`, `momentum_score`, `weighted_blend`.

---

## Critical — must fix before "done" (undermine the determinism thesis / corrupt real data)

### C1 — CFS-transcription guard is vacuous on engine output  ✓ RESOLVED 2026-06-20 (`938a981`)
- **Where:** `consultant_engine/nodes/generate_proposal.py` `_build_core_fund_card` (~L107-153) vs `consultant_engine/rules/validation.py::check_cfs_consistency` (~L173-209).
- **What:** the check looks for `<span class="cfs-score">N</span>` inside a `cfs-bar` (the curated-fixture shape), but the engine emits `<div class="cfs-title">COMPOSITE FUND SCORE: {composite} / 100</div>` with **no `cfs-score` span**. So `score_m is None` → the check `continue`s and never recomputes any engine card's composite. Reviewer corrupted a composite → `check_cfs_consistency == []`. The flagship guard (decision 2 / §8) is dead on the surface it was built to protect. `test_validate_node` passes *because* the check is vacuous; `test_broken_html_produces_violations` only corrupts the version stamp.
- **Fix:** make `_build_core_fund_card` emit the validator's `cfs-bar`/`cfs-score`/`… / 100 · W% weight` structure (the golden fixture's shape) + add an **adversarial test**: corrupt a composite in engine output → assert `cfs_recompute` fires.

### C2 — numbers the spec reserves for Python are routed through the LLM  ✓ RESOLVED 2026-06-20 (`938a981`)
- **Where:** `generate_proposal.py` (~L158,114,117,119); `consultant_engine/assets/prompts/generate_proposal.md` (~L60,79-84).
- **What:** per-fund performance tables (`<!--slot:perf.{abbr}.rows-->`), fund metadata (`meta.{abbr}.type/.shariah/.lipper`), and macro event rows (`macro.events_rows`) are **prose** slots; the prompt instructs the LLM to "transcribe" FundMaster numbers. These are Python-owned per decision 2 → carry no `data-slot` → validator-invisible → a hallucinated figure/date passes silently. In fake-LLM mode they degrade to literal `[perf.PGA.rows narrative]` text (CI proposal has no real perf/meta content).
- **Fix:** render performance rows, fund meta, and macro event rows **deterministically in Python** (all in `state`) as `data-slot`/pre-built rows; keep only genuine narrative (Why/Watch/thesis/strategy) as prose. Add adversarial test for a corrupted performance number.

### C3 — `top5` stored as delimited string, not list → overlap compares characters  ✓ RESOLVED 2026-06-20 (`1908152`)
- **Where:** `consultant_engine/nodes/load_funds.py` (~L92-93); consumed in `portfolio.py` (dedup ~L320-324, satellite gate-C ~L256-263).
- **What:** `top5 = top5_raw if top5_raw is not None else []` keeps col 64 raw (a pipe-delimited string in the real workbook). `set(top5)` on a string → **set of characters**; two funds with zero real overlap report ~12 shared "holdings" → lower-alpha fund wrongly dropped, legit satellites blocked. Masked because every fixture uses `top5=[]`.
- **Fix:** split col 64 into a list in `load_funds` (e.g. `[h.strip() for h in str(top5_raw).split("|")]`, guarding None/empty) + a dedup test with realistic string holdings.

---

## Important — should fix

### I1 — "substitute lowest-alpha core" silently picks the *first* core  ✓ RESOLVED 2026-06-20 (`39d8852`)
- **Where:** `portfolio.py` `exposure_gap_pick` (~L135) and `alpha_outlier` (~L280); `build` (~L78-81).
- **What:** both use `min(core_holdings, key=lambda h: h.get("alpha_n", 0))`, but `build()` core holdings are `{abbr,role,allocation_pct}` with **no `alpha_n`** → all resolve to 0 → `min` returns list-first, not lowest-alpha. Decision 10's "lower-alpha core" not wired end-to-end (unit tests pass because they hand-build holdings *with* `alpha_n`).
- **Fix:** carry `alpha_n` onto core holdings in `build()` (available on the score dict), or look it up from `cfs_scores` at substitution time.

### I2 — exposure-gap is dead in the live graph + Shariah leak
- **Where:** `consultant_engine/nodes/build_portfolio.py` (~L55-63).
- **What:** (a) `candidates=state["eligible_funds"]` is the *pre*-filter universe → a Shariah-noncompliant / over-RL fund could be injected; the gate catches RL but **not Shariah** (no Shariah invariant). (b) `build_portfolio` reads `macro_context["exposure_gaps"]` *before* the `macro_context` node runs (graph order build → interrupt → macro_context, §4) → in the live graph `gaps` is always `[]`, branch is dead.
- **Fix (design call, see below):** draw candidates from `filtered_funds` (or re-apply Shariah/RL to gap candidates); EITHER reconcile topology so macro gaps reach `build_portfolio`, OR explicitly document exposure-gap as **inert in Track 0** (macro fixture has no gaps anyway).

### I3 — second-round HITL fix is silently dropped
- **Where:** `consultant_engine/graph.py` `_review` (~L33-37).
- **What:** on a violating resumed edit (review ON), `_review` writes a violations-annotated artifact and calls `interrupt(artifact2)` but **ignores its resume value**, returning the stale violating `result`. A consultant who fixes their allocation and resumes again has the fix discarded; `apply_resume` never re-runs. No test covers this.
- **Fix:** loop interrupt/`apply_resume` until clean (or document a single-correction limit).

### I4 — dead `--no-review` branch in the review-ON block
- **Where:** `graph.py` `_review` (~L30-31).
- **What:** `_review` early-returns at ~L23 when `no_review` is set, so the `if state.get("no_review"): raise …` at ~L30 (post-`interrupt`) is unreachable — spec's "violating edit fails loudly (--no-review)" can't occur as written.
- **Fix:** remove the dead check, or restructure so `--no-review` resumes genuinely fail loudly.

---

## Minor — nice to have

- **M1** — duplicate `read_resume_payload` (`review_gate.py` ~L180-182 dead, shadowed by ~L260-269). Delete the stub.
- **M2** — unreachable `e_target=8.0` fallback (`generate_proposal.py` ~L264,349); `load_profile` always sets `e_target`. Harmonize/drop.
- **M3** — non-transitive sort comparator (`cfs.py` ~L211-220); the 2.0-gap tiebreaker isn't a total order. Low impact at small N; add a comment or total-order key.
- **M4** — `derived_class`/`raw_alpha_penalised` use `or 0` (`cfs.py` ~L13-14,49). Harmless now (only `0.0` falsy, comparisons `<0`) but the exact pattern the plan warns against. Prefer explicit `is not None`.
- **M5** — Cost-&-Alpha mini-grid and exposure pies hardcoded `—` (`generate_proposal.py` ~L162-168,288-293); Fee/Exposure spec'd Python-owned (§3) but ship as em-dashes. OK as a documented Track-0 gap.

---

## Remediation plan (subagent-driven, like the rest)

- [x] **C1 + C2 together** ✓ `938a981` — `_build_core_fund_card` emits the `cfs-score` span; performance rows, fund meta (Type/Shariah/Lipper/VF), and macro Event+Date cells are deterministic Python renders (macro Implication stays per-row prose `macro.impact.N`); new `check_perf_consistency` (Alpha == Fund − Bench) wired into `validate_html`; prompt updated to stop instructing the now-Python-owned slots. Six adversarial tests, fail-before/pass-after proven; suite 167 → 173.
- [x] **C3** ✓ `1908152` — `load_funds` splits col 64 on `|` into a `list[str]`; adversarial dedup test (zero name-overlap, heavy char-overlap → both survive).
- [x] **I1** ✓ `39d8852` — `build()` threads `alpha_n` onto core holdings; integration test proves the true lowest-alpha core is substituted.
- [ ] **I2** — Shariah/RL-filter the exposure-gap candidates; **decide:** make exposure-gap live (reconcile macro-before-build ordering) vs explicitly inert + documented for Track 0. *(Lean: inert + documented; live in a follow-up ENH.)*
- [ ] **I3** — loop the re-pause/apply_resume cycle (or document single-correction limit) + a full re-pause→fix→resume test.
- [ ] **I4 + minors** — fix or explicitly mark Track-0-inert.

**Guardrail for the round:** every fix lands with an adversarial test that would have caught the bug — the lesson is that empty/list fixtures + a vacuous check gave 167 green while the determinism boundary was half-real.

**Verdict to clear:** re-run the whole-implementation review after C1–C3 + I1; target "ready" (or ready-with-minor-fixes for the remaining I/M items).

# Track A — Prose-Number Entailment Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-07-06-track-a-prose-number-eval-design.md` (read it first — this plan implements it).

**Goal:** Ship the first buildable slice of Track A (ENH-10): an LLM-as-judge that checks prose-embedded numbers for entailment against the engine's deterministic figures, driven by Promptfoo, gated in CI over a frozen fixture corpus that **proves the judge itself** (via seeded good / single-error / buried-error fixtures) before it is trusted to gate.

**Architecture:** Four units — (1) a pure `figures_extractor` (`ConsultantState → flat figures dict`); (2) a frozen hand-authored fixture corpus (`good` / `seeded-bad-single` / `seeded-bad-buried`); (3) a Promptfoo config + rubric wrapping one Claude judge call per fixture; (4) a CI gate green only when every verdict matches its fixture's `expect`. The eval is an **offline regression layer** run on prompt/model change — the runtime `validate → repair` loop stays the per-run guard for structured values.

**Tech Stack:** Python 3 (extractor + its unit test) · Node / `npx` Promptfoo (harness) · an Anthropic Claude judge model · GitHub Actions (CI gate). Offline engine runs still use `CONSULTANT_ENGINE_FAKE_LLM=1`, but **the judge is a real LLM call** (see the API-key story, Phase 4).

## Global constraints

- **The judge is a real LLM call.** Fixtures-first freezes the eval's *inputs*, not the judge — running the suite needs a model API key. Do not describe or build this as "no API key needed."
- **The 1:1 mapping is load-bearing:** one fixture record ↔ one Promptfoo test case ↔ one judge call ↔ one **slot instance**. Never per-proposal, never per-fund-type. Keep every unit honoring it.
- **`figures_extractor` reuses verified state as ground truth — it does not re-verify it.** State correctness is owned by `tests/test_proposal_validation.py` (recompute from the workbook). Do not duplicate that here.
- **Offline-only over tracked outputs.** Nothing in this plan regenerates a committed example proposal. The extractor reads a `ConsultantState` (from a fixture or a fake-LLM run into a throwaway dir), never the default output dir.
- **The buried-error fixtures are the acceptance crux** (Phase 2 + Phase 4). If the judge cannot catch them, the holistic no-extraction bet is falsified — the plan's fallback is stated in Phase 3/4, not silently pinned away.
- **HTML companion.** This plan and its spec each ship a self-contained `.html` companion (same basename); regenerate it whenever the markdown changes. Markdown is the source of truth.
- **Conventional commits**, each ending with the two trailers used across this repo. Commit after every green phase.

---

## File structure

| Path | Change | Responsibility |
|---|---|---|
| `evals/track_a/` | Create | Track-A eval root (layout below). |
| `evals/track_a/figures_extractor.py` (or `consultant_engine/evals/figures_extractor.py`) | Create | Pure `extract_figures(state) -> dict`; the ground-truth surface. |
| `evals/track_a/fixtures/*.json` | Create | Frozen `(slot_key, figures, prose, expect, offending_sentence?, category)` records. |
| `evals/track_a/prompts/judge.md` | Create | The rubric prompt (JSON output contract + "check EACH numeric claim independently"). |
| `evals/track_a/promptfooconfig.yaml` | Create | One test case per fixture; parse verdict; assert against `expect`; multi-sample. |
| `evals/track_a/package.json` | Create | Promptfoo dev-dependency + an `npm run eval` script. |
| `evals/track_a/README.md` | Create | Local-run instructions + the API-key story. |
| `Makefile` (root) or `package.json` script | Modify/Create | `make eval-track-a` → runs the promptfoo suite. |
| `tests/evals/test_figures_extractor.py` (or `tests/consultant_engine/`) | Create | Python unit test for the extractor. |
| `.github/workflows/ci.yml` (or a new `track-a-eval.yml`) | Modify/Create | CI job running the promptfoo eval with the API-key secret + threshold. |

*(Resolve the extractor's exact home — `evals/track_a/` vs `consultant_engine/evals/` — in Phase 1 Step 1; the plan is written to work either way.)*

---

## Phase 0 — Scaffold & toolchain

**Goal:** stand up the `evals/track_a/` layout and make Promptfoo runnable locally with one command, before any judge logic exists.

**Steps:**

- [ ] Create the directory layout: `evals/track_a/{fixtures,prompts}/` + `evals/track_a/README.md`.
- [ ] Add `evals/track_a/package.json` with `promptfoo` as a dev-dependency and a script `"eval": "promptfoo eval -c promptfooconfig.yaml"`. Prefer `npx promptfoo` so contributors need no global install.
- [ ] Add a root convenience target — `make eval-track-a` (or an npm script) — that `cd`s into `evals/track_a` and runs the eval.
- [ ] Write `evals/track_a/README.md`: how to run locally (`npx promptfoo eval`), that it needs `ANTHROPIC_API_KEY` in the environment, and the one-line "this is an offline regression layer, not a per-run guard" framing.
- [ ] Add a placeholder `promptfooconfig.yaml` with zero tests so `npx promptfoo eval` exits cleanly (proves the toolchain is wired).

**Files touched:** `evals/track_a/package.json`, `evals/track_a/promptfooconfig.yaml` (stub), `evals/track_a/README.md`, root `Makefile`/`package.json`.

**Done when / how verified:** `make eval-track-a` (or `cd evals/track_a && npx promptfoo eval`) runs to a clean exit with no tests defined, and the README documents the local run + API-key requirement. Committed.

---

## Phase 1 — `figures_extractor`

**Goal:** a pure, unit-tested `state → figures` function exposing only the judge-relevant deterministic numbers.

**Steps:**

- [ ] Decide the extractor's home (`evals/track_a/figures_extractor.py` vs `consultant_engine/evals/figures_extractor.py`) and record it in the file header. Prefer engine-side if it must import engine types; otherwise keep it under `evals/track_a/`.
- [ ] Define the exact **figures schema** (flat dict). Concretely, at minimum:
  - **Per-fund:** `cfs`, `rank`, `weighted_alpha`, `allocation_pct`, and per-fund `exposure_pct` (asset-class / geo as available).
  - **Portfolio-level weighted aggregates:** weighted-average alpha, weighted CFS, asset-class + geo exposure totals, and the count / share of funds beating their benchmark.
- [ ] Implement `extract_figures(state: ConsultantState) -> dict` — pure, no I/O; read from `cfs_scores`, `portfolio`, and the exposure compute already in state.
- [ ] Write `tests/evals/test_figures_extractor.py`: feed a small constructed `ConsultantState` (or a fake-LLM run's state), assert the extracted dict has the schema fields with the right values, and assert the extractor is **pure** (no mutation of the input state).
- [ ] Add a docstring stating explicitly: *this reuses already-verified state figures as ground truth; it does not re-verify them against the workbook (that is `test_proposal_validation.py`'s job).*

**Files touched:** the extractor module + `tests/evals/test_figures_extractor.py`.

**Done when / how verified:** `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/evals/test_figures_extractor.py -v` is green; the schema fields are exactly those a prose judge could be checked against (per §9 of the spec). Committed.

---

## Phase 2 — Fixture corpus

**Goal:** a frozen, hand-authored corpus that proves the judge across all three categories — the buried-error set is the acceptance crux.

**Steps:**

- [ ] Document the fixture JSON schema in `evals/track_a/fixtures/README.md` (or a header comment): `{ slot_key, figures, prose, expect: "entailed"|"contradicted", offending_sentence?: string, category: "good"|"seeded-bad-single"|"seeded-bad-buried" }`.
- [ ] Author `good` fixtures — real, correct prose/figure pairs across `why.*`, `watch.*`, and `macro.impact`, spanning **several funds**. Include **at least a couple of derived-but-consistent** cases (policy 4a): prose that states, e.g., an *average* of three funds' alphas that is not literally any single slot figure but is consistent with them — so the judge is proven **not over-strict**.
- [ ] Author `seeded-bad-single` fixtures — take a good pair, plant exactly one wrong number, set `expect: "contradicted"` and fill `offending_sentence`.
- [ ] Author `seeded-bad-buried` fixtures — a slot with **several correct numbers plus exactly one** planted wrong one; `expect: "contradicted"`, `offending_sentence` = the buried-wrong one. This category is **mandatory** and is the crux.
- [ ] Make each `figures` block consistent with what `figures_extractor` would emit for that slot (hand-derive or extract-then-freeze).
- [ ] Sanity-check coverage: every slot family (`why` / `watch` / `macro.impact`) appears in every category; multiple funds represented.

**Files touched:** `evals/track_a/fixtures/*.json` + a schema note.

**Done when / how verified:** the corpus contains all three categories across all three slot families and several funds; each record is schema-valid JSON; the derived-but-consistent `good` cases and the buried-error cases both exist. (A tiny Python/`jq` lint over the fixtures confirming required keys + category coverage is worth adding.) Committed.

---

## Phase 3 — Judge prompt + Promptfoo config

**Goal:** turn each fixture into a test case, run one Claude judge call per fixture, parse the verdict, and assert it equals the fixture's `expect` — with multi-sample repeats to surface non-determinism.

**Steps:**

- [ ] Author `evals/track_a/prompts/judge.md`: give the judge the slot's prose + that slot's figures, and instruct it to **check EACH numeric claim independently before answering** (the mitigation for the holistic blind spot). Allow **derived-but-consistent** numbers (policy 4a): the judge checks *consistency, not novelty*.
- [ ] Lock the **output contract**: strict JSON `{ "entailed": boolean, "offending_sentence": string|null }`, nothing else.
- [ ] Pick and **pin** a concrete Anthropic Claude judge model (recommend a current Sonnet-class id) in `promptfooconfig.yaml`.
- [ ] Wire `promptfooconfig.yaml`: load each fixture as a test case (prose + figures → prompt vars); assert the parsed verdict. Prefer a `javascript`/`python` assertion that parses the judge JSON and checks: `entailed == (expect == "entailed")`, and for `seeded-bad-*` that `offending_sentence` is non-null (bonus: matches the fixture's). An `llm-rubric` assertion is the fallback if JSON parsing proves awkward.
- [ ] Enable **multi-sample repeats** (`repeat`/`numSamples`) so judge flakiness shows up as a pass rate, not a single verdict.
- [ ] Run locally against the fixtures and inspect: do the `good` pass, the `seeded-bad-single` fail-as-contradicted, and crucially the **`seeded-bad-buried` get caught**?

**The acceptance crux (state explicitly):** if the buried-error fixtures are **caught**, the holistic no-extraction shortcut is validated. If they are **missed**, first tighten the rubric (strengthen the "check EACH numeric claim independently" instruction / add a worked example); if still missed, escalate to a per-number extraction step. Do **not** paper over a miss by loosening the fixture.

**Files touched:** `evals/track_a/prompts/judge.md`, `evals/track_a/promptfooconfig.yaml`.

**Done when / how verified:** `cd evals/track_a && ANTHROPIC_API_KEY=… npx promptfoo eval` runs all fixtures; every `good` verdict is `entailed`, every `seeded-bad-*` is `contradicted` **including the buried-error set**, across the configured samples. Committed.

---

## Phase 4 — CI gate

**Goal:** a GitHub Actions job that runs the promptfoo eval over the fixtures and is green only when every verdict matches its fixture's `expect` within the stated threshold.

**Steps:**

- [ ] Add the job to `.github/workflows/ci.yml` (or a dedicated `track-a-eval.yml`): set up Node, `npx promptfoo eval -c evals/track_a/promptfooconfig.yaml`, fail the job on any assertion failure.
- [ ] Wire the **API-key story** (per spec §8): CI runs the judge live using an `ANTHROPIC_API_KEY` **repo secret**; the small frozen fixture set keeps cost/latency trivial. (Document the committed-response-cache alternative in the README as a fallback, noting it must be regenerated on any prompt/model change.)
- [ ] Set the **pass threshold**: the judge must catch **100% of `seeded-bad-*`** and pass **100% of `good`** across N samples; any miss fails the job. Encode the threshold in the promptfoo assertions / a small wrapper check.
- [ ] Scope the trigger honestly: this is an **offline regression layer**, so run it on changes to the generation prompt/model or the eval assets (and on demand), **not** on every unrelated push if token budget matters. Document the trigger choice.
- [ ] Make the job **required** for merge once green and stable.

**Files touched:** `.github/workflows/ci.yml` (or a new workflow), `evals/track_a/README.md` (secret + threshold note).

**Done when / how verified:** the CI job runs the eval with the secret, is green on the current fixtures, and goes **red** if a `seeded-bad-buried` fixture's planted error is missed (verify by temporarily corrupting the judge to prove the gate bites). Committed; job marked required.

---

## Deferred / phase-2 items

Called out here so the slice's boundary is unambiguous (mirrors spec §10):

- **Live multi-sample proposal regeneration** — running the real generator repeatedly and judging fresh prose (this slice freezes inputs instead).
- **The qualitative-prose judge** (tone / relevance / no-hallucination — Track A "wave a").
- **RAG / retrieval evals** (Track A "wave b") — blocked on Track B (no corpus yet).
- **Human-label calibration set** — not needed for prose-number entailment; deferred.
- **Committed-response-cache CI mode** — documented as a fallback; live judging is the recommended default.

---

## Definition of done

- [ ] Phases 0–4 landed, each commit green.
- [ ] `figures_extractor` implemented + Python-unit-tested (schema fields per spec §9); reuses verified state, does not re-verify it.
- [ ] Frozen fixture corpus spanning `good` / `seeded-bad-single` / `seeded-bad-buried`, across `why.*` / `watch.*` / `macro.impact` and several funds, including derived-but-consistent `good` cases.
- [ ] Promptfoo config + rubric with a **pinned** Claude judge model, multi-sample repeats, JSON `{entailed, offending_sentence}` verdict parsed and asserted against each fixture's `expect`.
- [ ] CI job green only when every verdict matches within threshold; the **buried-error catch is proven** to make the gate bite.
- [ ] The API-key story is stated honestly (live judge + repo secret recommended; cache documented as a brittle fallback).
- [ ] HTML companion of this plan regenerated (mirrors this markdown; markdown is the source of truth).

---

## Self-review

**Spec coverage** — every spec unit maps to a phase: `figures_extractor` → Phase 1; fixture corpus (incl. buried-error crux + derived-but-consistent `good`) → Phase 2; judge prompt + Promptfoo config (holistic policy 4b, JSON contract, multi-sample) → Phase 3; CI gate + API-key story → Phase 4; toolchain → Phase 0. The 1:1 mapping and the out-of-scope list are carried as global constraints + the deferred section.

**Acceptance crux surfaced** — the buried-error experiment is explicit in Phase 2 (author), Phase 3 (verify locally + fallback to per-number extraction), and Phase 4 (prove the gate bites). It is the falsifiable test of the holistic no-extraction bet.

**Honesty checks** — the API-key requirement is stated as a global constraint and in Phase 4 (not "no key needed"); the extractor's non-circularity (reuse ≠ re-verify) is a global constraint and Phase 1 docstring; the offline-regression-not-per-run-guard framing appears in Phase 0 README and Phase 4 trigger scope.

# Prose-Number Entailment Eval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-07-06-track-a-prose-number-eval-design.md` (read it first — this plan implements it).

**Goal:** Ship the first buildable slice of the consultant_engine evals suite (ENH-10): an LLM-as-judge that checks prose-embedded numbers for entailment against the engine's deterministic figures, driven by Promptfoo, gated in CI over a frozen fixture corpus that **proves the judge itself** (via seeded good / single-error / buried-error fixtures) before it is trusted to gate.

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
| `evals/prose_numbers/` | Create | Prose-number eval root (layout below). |
| `consultant_engine/evals/figures_extractor.py` | Create | Pure `extract_figures(state) -> dict`; the ground-truth surface. Engine-coupled Python, lives with the package (decided). |
| `evals/prose_numbers/fixtures/*.json` | Create | Frozen `(slot_key, figures, prose, expect, offending_sentence?, category)` records. |
| `evals/prose_numbers/prompts/judge.md` | Create | The rubric prompt (JSON output contract + "check EACH numeric claim independently"). |
| `evals/prose_numbers/promptfooconfig.yaml` | Create | One test case per fixture; parse verdict; assert against `expect`; multi-sample. |
| `evals/prose_numbers/package.json` | Create | Promptfoo dev-dependency + an `npm run eval` script. |
| `evals/prose_numbers/README.md` | Create | Local-run instructions + the API-key story. |
| `Makefile` (root) or `package.json` script | Modify/Create | `make eval-prose-numbers` → runs the promptfoo suite. |
| `tests/evals/test_figures_extractor.py` (or `tests/consultant_engine/`) | Create | Python unit test for the extractor. |
| `.github/workflows/ci.yml` (or a new `prose-numbers-eval.yml`) | Modify/Create | CI job running the promptfoo eval with the API-key secret + threshold. |

*(Extractor home is **decided**: `consultant_engine/evals/figures_extractor.py` — the one engine-coupled Python piece lives with the package for frictionless imports; the language-agnostic harness stays under `evals/prose_numbers/`, joined only by the frozen fixture JSON.)*

---

## Phase 0 — Scaffold & toolchain

**Goal:** stand up the `evals/prose_numbers/` layout and make Promptfoo runnable locally with one command, before any judge logic exists.

**Steps:**

- [ ] Create the directory layout: `evals/prose_numbers/{fixtures,prompts}/` + `evals/prose_numbers/README.md`.
- [ ] Add `evals/prose_numbers/package.json` with `promptfoo` as a dev-dependency and a script `"eval": "promptfoo eval -c promptfooconfig.yaml"`. Prefer `npx promptfoo` so contributors need no global install.
- [ ] Add a root convenience target — `make eval-prose-numbers` (or an npm script) — that `cd`s into `evals/prose_numbers` and runs the eval.
- [ ] Write `evals/prose_numbers/README.md`: how to run locally (`npx promptfoo eval`), that it needs `ANTHROPIC_API_KEY` in the environment, and the one-line "this is an offline regression layer, not a per-run guard" framing.
- [ ] Add a placeholder `promptfooconfig.yaml` with zero tests so `npx promptfoo eval` exits cleanly (proves the toolchain is wired).

**Files touched:** `evals/prose_numbers/package.json`, `evals/prose_numbers/promptfooconfig.yaml` (stub), `evals/prose_numbers/README.md`, root `Makefile`/`package.json`.

**Done when / how verified:** `make eval-prose-numbers` (or `cd evals/prose_numbers && npx promptfoo eval`) runs to a clean exit with no tests defined, and the README documents the local run + API-key requirement. Committed.

---

## Phase 1 — `figures_extractor`

**Goal:** a pure, unit-tested `state → figures` function exposing only the judge-relevant deterministic numbers.

**Steps:**

- [ ] Create the extractor at **`consultant_engine/evals/figures_extractor.py`** (decided — engine-coupled Python lives with the package for frictionless imports; add `consultant_engine/evals/__init__.py`). State in the file header that the language-agnostic harness lives under `evals/prose_numbers/`, joined by the frozen fixture JSON.
- [ ] Define the exact **figures schema** (flat dict). Concretely, at minimum:
  - **Per-fund:** `cfs`, `rank`, `weighted_alpha`, `allocation_pct`, and per-fund `exposure_pct` (asset-class / geo as available).
  - **Portfolio-level weighted aggregates — pre-computed on purpose (spec §4a):** weighted-average alpha, weighted CFS, per-sleeve averages, asset-class + geo exposure totals, and the count / share of funds beating their benchmark. These are the derivations a consultant states in prose; emitting them here means the judge checks a prose number for *membership* against a ready value instead of doing the arithmetic itself (the least reliable thing to delegate to an LLM). **Adding a derived field here is cheaper and safer than trusting the judge to compute it** — when in doubt, pre-compute it.
- [ ] Implement `extract_figures(state: ConsultantState) -> dict` — pure, no I/O; read from `cfs_scores`, `portfolio`, and the exposure compute already in state; compute the derived aggregates deterministically here.
- [ ] Write `tests/evals/test_figures_extractor.py`: feed a small constructed `ConsultantState` (or a fake-LLM run's state), assert the extracted dict has the schema fields with the right values **including the derived aggregates (verify the averages/shares against hand-computed expected numbers)**, and assert the extractor is **pure** (no mutation of the input state).
- [ ] Add a docstring stating explicitly: *this reuses already-verified state figures as ground truth; it does not re-verify them against the workbook (that is `test_proposal_validation.py`'s job).*

**Files touched:** the extractor module + `tests/evals/test_figures_extractor.py`.

**Done when / how verified:** `CONSULTANT_ENGINE_FAKE_LLM=1 .venv/bin/python -m pytest tests/evals/test_figures_extractor.py -v` is green; the schema fields are exactly those a prose judge could be checked against (per §9 of the spec). Committed.

---

## Phase 2 — Fixture corpus

**Goal:** a frozen, hand-authored corpus that proves the judge across all three categories — the buried-error set is the acceptance crux.

**Steps:**

- [ ] Document the fixture JSON schema in `evals/prose_numbers/fixtures/README.md` (or a header comment): `{ slot_key, figures, prose, expect: "entailed"|"contradicted", offending_sentence?: string, category: "good"|"seeded-bad-single"|"seeded-bad-buried" }`.
- [ ] Author `good` fixtures — real, correct prose/figure pairs across `why.*`, `watch.*`, and `macro.impact`, spanning **several funds**. **Mandatory: include adversarial-but-correct derived cases** (policy 4a) — prose that states an *average* / *rounding* / *subset-weighted* number that is not literally any single slot figure but is consistent with them (ideally matching a pre-computed aggregate from Phase 1). These cases **measure the judge's precision / false-positive rate**, not just recall on planted errors: a judge that flags every novel number would pass a good-set of only verbatim restatements yet be useless. Make the good-set hard enough to catch that.
- [ ] Author `seeded-bad-single` fixtures — take a good pair, plant exactly one wrong number, set `expect: "contradicted"` and fill `offending_sentence`.
- [ ] Author `seeded-bad-buried` fixtures — a slot with **several correct numbers plus exactly one** planted wrong one; `expect: "contradicted"`, `offending_sentence` = the buried-wrong one. This category is **mandatory** and is the crux.
- [ ] Make each `figures` block consistent with what `figures_extractor` would emit for that slot (hand-derive or extract-then-freeze).
- [ ] Sanity-check coverage: every slot family (`why` / `watch` / `macro.impact`) appears in every category; multiple funds represented.

**Files touched:** `evals/prose_numbers/fixtures/*.json` + a schema note.

**Done when / how verified:** the corpus contains all three categories across all three slot families and several funds; each record is schema-valid JSON; the derived-but-consistent `good` cases and the buried-error cases both exist. (A tiny Python/`jq` lint over the fixtures confirming required keys + category coverage is worth adding.) Committed.

---

## Phase 3 — Judge prompt + Promptfoo config

**Goal:** turn each fixture into a test case, run one Claude judge call per fixture, parse the verdict, and assert it equals the fixture's `expect` — with multi-sample repeats to surface non-determinism.

**Steps:**

- [ ] Author `evals/prose_numbers/prompts/judge.md`: give the judge the slot's prose + that slot's figures, and instruct it to **check EACH numeric claim independently before answering** (a mitigation for the holistic blind spot). Allow **derived-but-consistent** numbers (policy 4a): the judge checks *consistency, not novelty*. **Write the rubric as richly as an atomic-decomposition prompt would be** — spell out the per-claim procedure and a worked example; the industry holistic-vs-atomic parity result only holds when the holistic rubric is that detailed. Tell the judge to prefer the pre-computed aggregates in the figures over doing its own arithmetic.
- [ ] Lock the **output contract**: strict JSON with a **per-claim verdict list**, `{ "claims": [ { "text": string, "verdict": "entailed"|"contradicted"|"underivable" }, ... ], "entailed": boolean, "offending_sentence": string|null }`. `entailed` is reduced **in the assertion code** (false if any claim is not `entailed`); `offending_sentence` = the first failing claim's sentence. **Enumerating every claim before the boolean is the structural mitigation for the buried-error blind spot** (spec §6.3/§7) — the judge cannot return `entailed:true` without a verdict on the buried number.
- [ ] **Pin** the judge model **`claude-sonnet-5`** (promptfoo `anthropic:messages:claude-sonnet-5`) in `promptfooconfig.yaml` — pinned, not a floating "latest" alias, for reproducibility. **Record the generator model id** in a config-header comment beside it so self-preference bias stays detectable.
- [ ] Wire `promptfooconfig.yaml`: load each fixture as a test case (prose + figures → prompt vars); use a `javascript`/`python` assertion (the chosen mechanism, not a bare `llm-rubric`) that parses the per-claim JSON, reduces `entailed`, and checks `entailed == (expect == "entailed")` — and for `seeded-bad-*` that the **planted claim specifically** is the one flagged `contradicted`/`underivable` and `offending_sentence` is surfaced.
- [ ] Enable **multi-sample repeats** (`repeat`/`numSamples`) and fix the **aggregation rule explicitly** — majority-vote-of-N (or pass@k) with a stated N and k — so judge flakiness shows up as a defined pass rate, not an ad-hoc average or a single coin-flip.
- [ ] Run locally against the fixtures and inspect: do the `good` pass, the `seeded-bad-single` fail-as-contradicted, and crucially the **`seeded-bad-buried` get caught**?

**The acceptance crux (state explicitly):** the per-claim verdict list + rich rubric are already the structural defenses (baked into the contract, not a later add-on). If the buried-error fixtures are **caught**, the holistic no-regex-extraction approach is validated. If they are **missed** despite those defenses, the only remaining lever is a **deterministic per-number extraction step ahead of the judge** — do **not** paper over a miss by loosening the fixture or the threshold.

**Files touched:** `evals/prose_numbers/prompts/judge.md`, `evals/prose_numbers/promptfooconfig.yaml`.

**Done when / how verified:** `cd evals/prose_numbers && ANTHROPIC_API_KEY=… npx promptfoo eval` runs all fixtures; every `good` verdict is `entailed`, every `seeded-bad-*` is `contradicted` **including the buried-error set**, across the configured samples. Committed.

---

## Phase 4 — CI gate

**Goal:** a GitHub Actions job that runs the promptfoo eval over the fixtures and is green only when every verdict matches its fixture's `expect` within the stated threshold.

**Steps:**

- [ ] Add the job to `.github/workflows/ci.yml` (or a dedicated `prose-numbers-eval.yml`): set up Node, `npx promptfoo eval -c evals/prose_numbers/promptfooconfig.yaml`, fail the job on any assertion failure.
- [ ] Wire the **API-key story** (per spec §8): CI runs the judge live using an `ANTHROPIC_API_KEY` **repo secret**; the small frozen fixture set keeps cost/latency trivial. (Document the committed-response-cache alternative in the README as a fallback, noting it must be regenerated on any prompt/model change.)
- [ ] Set the **pass threshold** under the Phase-3 aggregation rule: the judge must catch **100% of `seeded-bad-*`** (recall) and pass **100% of `good`** (precision) across the N samples per the majority/pass@k rule; any miss fails the job. Encode the threshold in the promptfoo assertions / a small wrapper check.
- [ ] **Report both metrics, not just pass/fail** — recall on `seeded-bad-*` and precision on `good` (false-positive rate) — so a regression in either direction is visible in the job output, not hidden behind a green/red bit.
- [ ] Scope the trigger honestly: this is an **offline regression layer**, so run it on changes to the generation prompt/model or the eval assets (and on demand), **not** on every unrelated push if token budget matters. Document the trigger choice.
- [ ] Make the job **required** for merge once green and stable.

**Files touched:** `.github/workflows/ci.yml` (or a new workflow), `evals/prose_numbers/README.md` (secret + threshold note).

**Done when / how verified:** the CI job runs the eval with the secret, is green on the current fixtures, and goes **red** if a `seeded-bad-buried` fixture's planted error is missed (verify by temporarily corrupting the judge to prove the gate bites). Committed; job marked required.

---

## Deferred / phase-2 items

Called out here so the slice's boundary is unambiguous (mirrors spec §10):

- **Live multi-sample proposal regeneration** — running the real generator repeatedly and judging fresh prose (this slice freezes inputs instead).
- **The qualitative-prose judge** (tone / relevance / no-hallucination).
- **RAG / retrieval evals** — blocked on the regulatory-RAG workstream (no corpus yet).
- **Human-agreement gate (κ) — the phase-2 criterion to trust the judge beyond fixtures.** Phase 1's synthetic fixtures prove recall on *imagined* error types and precision on *hand-built* good cases, but not agreement with a human on *real generated* prose. Before live use, label a small real-generation sample and require inter-rater agreement **κ ≥ ~0.6** (the accepted meta-evaluation floor). Not a phase-1 blocker; phase 1 ships on fixtures alone.
- **Committed-response-cache CI mode** — documented as a fallback; live judging is the recommended default.

---

## Definition of done

- [ ] Phases 0–4 landed, each commit green.
- [ ] `figures_extractor` implemented + Python-unit-tested (schema fields per spec §9); reuses verified state, does not re-verify it.
- [ ] Frozen fixture corpus spanning `good` / `seeded-bad-single` / `seeded-bad-buried`, across `why.*` / `watch.*` / `macro.impact` and several funds, with **adversarial-but-correct derived `good` cases** that measure precision.
- [ ] Promptfoo config + rubric with a **pinned** Claude judge model, multi-sample repeats under an **explicit aggregation rule** (majority/pass@k), and a **per-claim** JSON verdict (`claims[]` → reduced `entailed` + `offending_sentence`) parsed and asserted against each fixture's `expect`.
- [ ] CI job green only when every verdict matches within threshold, **reporting both recall (seeded-bad) and precision (good)**; the **buried-error catch is proven** to make the gate bite.
- [ ] The API-key story is stated honestly (live judge + repo secret recommended; cache documented as a brittle fallback).
- [ ] HTML companion of this plan regenerated (mirrors this markdown; markdown is the source of truth).

---

## Self-review

**Spec coverage** — every spec unit maps to a phase: `figures_extractor` → Phase 1; fixture corpus (incl. buried-error crux + derived-but-consistent `good`) → Phase 2; judge prompt + Promptfoo config (holistic policy 4b, JSON contract, multi-sample) → Phase 3; CI gate + API-key story → Phase 4; toolchain → Phase 0. The 1:1 mapping and the out-of-scope list are carried as global constraints + the deferred section.

**Acceptance crux surfaced** — the buried-error experiment is explicit in Phase 2 (author), Phase 3 (verify locally + fallback to per-number extraction), and Phase 4 (prove the gate bites). It is the falsifiable test of the holistic no-extraction bet.

**Honesty checks** — the API-key requirement is stated as a global constraint and in Phase 4 (not "no key needed"); the extractor's non-circularity (reuse ≠ re-verify) is a global constraint and Phase 1 docstring; the offline-regression-not-per-run-guard framing appears in Phase 0 README and Phase 4 trigger scope.

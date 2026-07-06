# Track A — Prose-Number Entailment Eval (design)

**Date:** 2026-07-06
**Status:** Design — approved from brainstorming, pending spec review → writing-plans
**Tracking:** `docs/tasks.md` ENH-10 (prose-authored-number drift), ENH-5 Track A (evals master)
**Scope:** The first buildable slice of **Track A — Evals** for the `consultant_engine/` package: an LLM-as-judge that checks prose-embedded numbers for **entailment** against the deterministic figures the engine already computes. This is exactly ENH-10.

---

## 1. Summary

Build an **LLM-as-judge** that answers one question over the consultant engine's free-text prose: *is every number the model wrote into a narrative slot entailed by the deterministic figures the engine handed it?* The judge reuses the engine's already-verified `ConsultantState` figures as trusted ground truth, is driven by **Promptfoo**, and is gated in **CI** over a **frozen, hand-authored fixture corpus** that proves the judge itself before the judge is trusted to gate anything.

It is an **offline regression layer**, run when the generation prompt or model changes — *not* a per-run production guard. The runtime `validate → repair` loop remains the per-run guard for structured (data-slot-bound) values; this eval measures the one surface that loop structurally cannot see.

This is the first of the Track-A judges deliberately, because prose-number entailment has the cleanest possible ground truth (the deterministic figures) and needs **no human-labeling bottleneck** — unlike the qualitative-prose judge (tone/relevance), which is deferred.

## 2. The gap this closes

The consultant's determinism boundary keeps every *structured* number Python-owned, and that surface is already tested three ways:

| Tier | Where | What it guards |
|---|---|---|
| Per-node unit tests | `tests/consultant_engine/*` | each node's compute logic in isolation |
| Runtime reconciliation | `check_render_fidelity(html, state)` — `consultant_engine/rules/validation.py` (~L739) | every rendered **`data-slot`** value matches the engine's own state |
| Published-proposal recompute | `tests/test_proposal_validation.py` | recomputes CFS / performance / exposure / portfolio-summary **from the FundMaster workbook** and asserts the displayed values match |

The one surface **none** of those can see is **numbers the LLM writes into free-text prose that have no `data-slot` anchor** — e.g. *"nearly 78% of the portfolio beats its benchmark"* or *"your three equity sleeves average 4.1% alpha"*. Because these figures have no anchor to reconcile against:

- the reconciliation guard can't see them (no `data-slot`);
- the locked-template / recompute evals can't see them (not a known cell);
- they can silently **drift or contradict** the deterministic figures elsewhere in the same document.

This judge closes that gap.

## 3. The judged surface (the genuine-synthesis prose slots)

In `consultant_engine/nodes/generate_proposal.py`, proposal assembly is two-phase:

1. Python `fill_slots()` replaces every `data-slot` fact/table marker with concrete HTML (numbers, tables, charts).
2. The LLM is then asked **only** for the leftover `<!--slot:KEY-->` prose markers and (per the code, ~L476) *"returns only a delimited map of slot-key → prose; Python substitutes."*

The **genuine-synthesis prose slots** — the judged surface — are exactly:

| Slot family | Count (typical) | Content |
|---|---|---|
| `why.<fund>` | 4 (one per portfolio fund) | why-this-fund synthesis |
| `watch.<fund>` | 4 (one per portfolio fund) | what-to-watch synthesis |
| `macro.impact.*` | ~1 | macro-context impact narrative |

≈ **9 slot instances per proposal**. Everything else — `cover.*`, `exposure.*`, `fee_table`, `portfolio_summary`, `profile.*`, `sources.*`, `macro.events_rows`, `strategy.rsp_table` — is **Python-filled** and already covered by the three tiers above.

## 4. Locked decisions

1. **First judge = prose-NUMBER entailment (ENH-10)**, not the qualitative judge. Cleanest ground truth; no human-labeling bottleneck.
2. **Harness = Promptfoo.** Config-driven `llm-rubric` assertions, multi-sample runs, CI-gateable pass/fail. Adds a Node / `npx` dependency alongside the Python repo. Chosen for portfolio value (legible eval tooling is a named JD gap) and because ENH-10 names it.
3. **Data sourcing = fixtures-first, live-later.** Build a **frozen** fixture corpus that validates the **judge itself** before trusting it to gate anything. Live multi-sample proposal regeneration is a later phase.
4. **Rubric policy (a) — allow derived-but-consistent numbers.** Prose **may** introduce numbers not literally in a slot (e.g. an average of three funds' alphas) as long as they are **consistent** with the figures. The judge checks *consistency, not novelty* — forbidding new numbers would gut synthesis prose. See §4a for the precise definition of "consistent".
5. **Rubric policy (b) — holistic per slot-instance.** One judge call per slot instance (e.g. `why.PAPFF`), given **that slot's prose + that slot's relevant figures**, returning `{entailed: bool, offending_sentence: string|null}`. **No** brittle number-extraction / parsing pre-step — the LLM does both "find the numbers" *and* "map + check against figures", which is the part a regex cannot do. The rubric prompt **must** instruct the judge to *"check EACH numeric claim independently before answering"* to mitigate the holistic blind spot (§7).

### 4a. What "consistent" means

The judge's question about any number in the prose is **not** "is this number literally in the figure set?" (that would reject legitimate synthesis such as averages) but **"can I trace this number back to the figures, and does it clash with any of them?"** A number is **consistent** if it falls into one of three cases:

1. **Restatement** — the number *is* one of the figures. PAPFF's 3yr alpha is `2.1%`; prose says "outperformed by 2.1%." Trivially consistent.
2. **Correct derivation** — the number is not in the figure set but is a valid arithmetic/logical result of it:
   - *average* — "its three equity funds average ~1.9% alpha" when the figures are `2.1, 1.8, 1.8` → mean `1.9` ✓
   - *rounding* — figure `2.13%`, prose "about 2.1%" ✓
   - *rank / superlative* — "the top performer of the three" when it genuinely holds the highest alpha ✓
   - *direction* — "outperformed its benchmark" when alpha > 0 ✓
3. **Non-contradiction band** — an approximate/soft number the judge cannot derive exactly but that conflicts with nothing. "A modest ~2% edge" against an actual `2.1%` ✓.

A number is **inconsistent** (the complement) when it either:
- **contradicts** a figure — "a 9% edge" when alpha is `2.1%`; or
- **cannot be traced to any figure** — fabricated with no derivation path (prose cites a Sharpe ratio or an "8% annual return" when state holds no such number). **Unverifiable-as-stated-fact is treated as inconsistent**, because it cannot be confirmed and reads as a hard claim.

The subtle boundary — and the reason the seeded-bad fixtures exist — is the **wrongly-derived trap**: prose claims a derivation the figures don't support ("average 3%" when the true mean is `1.9%`). This is case-2-shaped but **inconsistent**, because the *claimed* relationship to the figures is false. The judge must catch it, not wave it through as "a new number."

## 5. The 1:1 mapping

The core discipline of the design — everything lines up one-to-one:

```
one fixture record  ↔  one Promptfoo test case  ↔  one judge call  ↔  one SLOT INSTANCE
```

**Not** per-proposal, **not** per-fund-type. `why.PAPFF` is one test row carrying PAPFF's figures; `why.PCIF` is a *different* row carrying PCIF's figures. A fixture is a single `(slot prose, that slot's figures, expected verdict)` triple.

## 6. Architecture — the four units

### 6.1 `figures_extractor` — pure `state → figures`

- **Purpose:** expose *only* the judge-relevant deterministic numbers as a flat dict, ready to inject into the judge prompt as ground truth.
- **Interface:** `extract_figures(state: ConsultantState) -> dict` (pure function, no I/O).
- **Fields exposed:** per-fund CFS + rank, weighted alpha, allocation %, exposure %, and portfolio-level weighted aggregates (see §9 for the exact schema).
- **Home:** engine-side, `consultant_engine/evals/` (or `evals/track_a/` — resolve in the plan). Unit-tested in Python.
- **Dependency:** reads a `ConsultantState`; depends on nothing outside the engine. Its output is what gets injected into the judge prompt.

### 6.2 Fixture corpus — the frozen judged inputs

- **Purpose:** freeze a hand-authored set of `(prose, figures, expected verdict)` triples that **proves the judge** across good/bad cases before it gates.
- **Layout:** `evals/track_a/fixtures/*.json`, each record:

```json
{
  "slot_key": "why.PAPFF",
  "figures": { "...": "the extract_figures output relevant to this slot" },
  "prose": "the LLM-authored narrative text for this slot",
  "expect": "entailed",
  "offending_sentence": null,
  "category": "good"
}
```

- **Categories (all three required):**
  - `good` — real, correct prose/figure pairs (incl. **derived-but-consistent** cases per policy 4a, so the judge isn't over-strict).
  - `seeded-bad-single` — a slot with exactly one planted wrong number.
  - `seeded-bad-buried` — a slot with several correct numbers **plus exactly one** planted wrong one (the §7 crux).
- **Coverage:** spans `why.*` / `watch.*` / `macro.impact`, and multiple funds.
- **Dependency:** each `figures` block is produced by / consistent with `figures_extractor`; hand-authored prose.

### 6.3 Judge prompt + Promptfoo config

- **Purpose:** turn each fixture into a test case and assert the judge's verdict equals the fixture's `expect`.
- **Files:** `promptfooconfig.yaml` + the rubric prompt.
- **Judge output contract:** strict JSON `{ "entailed": bool, "offending_sentence": string|null }`.
- **Assertion:** an `llm-rubric` (or a `javascript` / `python` assertion that parses the judge's JSON) asserts `entailed` matches `expect`, and — for `seeded-bad-*` — that an offending sentence is surfaced.
- **Judge model:** a concrete Anthropic **Claude** model (recommend a current Sonnet-class model; pin the exact id in the config). Stated, not left implicit.
- **Non-determinism:** configure **multi-sample repeats** so judge flakiness surfaces as a measured pass rate rather than a single coin-flip.
- **Dependency:** consumes the fixtures + rubric; needs a model API key at run time (§8).

### 6.4 CI gate

- **Purpose:** a job that runs the promptfoo eval over the fixtures and is green **only** when every judge verdict matches its fixture's `expect` (within a stated multi-sample threshold).
- **Threshold:** e.g. the judge must **catch 100% of `seeded-bad-*`** and **pass 100% of `good`** across N samples. A missed buried-error fails the suite red.
- **Dependency:** GitHub Actions + the API-key story in §8.

### Data flow

```
ConsultantState ──figures_extractor──> figures dict ──┐
                                                       ├─> fixture record (frozen JSON)
hand-authored prose ───────────────────────────────────┘        │
                                                                 ▼
                                     promptfooconfig.yaml + rubric prompt
                                                                 │  (one test case per fixture)
                                                                 ▼
                                            Claude judge call → {entailed, offending_sentence}
                                                                 │
                                                                 ▼
                                        assert verdict == fixture.expect  → CI green / red
```

## 7. The judge's known blind spot + the buried-error experiment

**The blind spot.** A single slot's prose often contains several numbers. A holistic judge (policy 4b) could rubber-stamp `entailed: true` when **one** number is wrong but "buried among several" correct ones — the whole point of *not* doing per-number extraction is that the LLM must find *and* check each number itself, and it can get lazy.

**The safety check.** The fixture corpus therefore **requires** the `seeded-bad-buried` category: a slot with multiple correct numbers plus exactly one planted wrong one. This is the **acceptance crux** for the whole holistic bet:

- If the judge **catches** the buried errors → the holistic, no-extraction shortcut is validated; ship it.
- If the judge **misses** them → the suite goes **red** and the holistic bet is **falsified**. Fallback: tighten the rubric (the *"check EACH numeric claim independently"* instruction is the first lever), and if that fails, move to a per-number extraction step.

This experiment is deliberate and must be made explicit in the plan: it **proves or kills the holistic shortcut before it gates.**

## 8. CI / API-key story (stated honestly)

"Fixtures-first" freezes the eval's **inputs** (no proposal regeneration; a tiny, fast, cheap run) and isolates **judge** behaviour from **generator** behaviour. **But the judge is itself an LLM call, so running the eval needs a model API key.** This is not a "no API key needed" design — say so plainly.

| Option | How | Trade-off |
|---|---|---|
| **CI runs the judge live (recommended)** | An `ANTHROPIC_API_KEY` repo secret; the small frozen fixture set keeps cost/latency trivial; multi-sample with a pass threshold absorbs judge non-determinism. | Needs a secret; each CI run spends a few cents of tokens. |
| Committed response cache | Commit a promptfoo response cache so CI replays recorded judge outputs deterministically without a key. | Brittle — the cache must be regenerated whenever the prompt or model changes, and a stale cache silently stops testing the real judge. |

**Recommendation: the live option.** The fixture set is small enough that live judging is cheap and honest; the cache option trades a real secret for a maintenance hazard.

Either way, the eval is an **offline regression layer run on prompt/model change, NOT a per-run production guard**. The runtime `validate → repair` loop remains the per-run guard for structured values.

## 9. `figures_extractor` schema (the ground-truth surface)

The flat dict the extractor emits (exact field names resolved in the plan). It exposes **only** what a prose judge could legitimately be checked against:

| Group | Fields | Source in state |
|---|---|---|
| Per-fund | `cfs`, `rank`, `weighted_alpha`, `allocation_pct`, per-fund `exposure_pct` | `cfs_scores`, `portfolio`, exposure compute |
| Portfolio-level | weighted-average alpha, weighted CFS, asset-class / geo exposure aggregates, count/share of funds beating benchmark | derived from the portfolio + per-fund figures |

The extractor is **not** re-deriving these from the workbook — that is `test_proposal_validation.py`'s job (§10). It re-reads the already-verified state figures and reshapes them.

## 10. Explicitly out of scope

State clearly in the docs — this slice does **not** own:

- **Correctness of the state figures themselves.** Already covered by the three deterministic tiers (§2). The judge **reuses** the already-verified `ConsultantState` figures as trusted ground truth. **This is not circular:** state is independently verified against the *source workbook* by `test_proposal_validation.py`; the judge only asks whether the *prose* is consistent with those verified figures.
- **The fact-slot guardrail** (that the LLM can't overwrite Python-filled slots) — already enforced structurally: the LLM emits keyed fragments, not the document; the `[UNFILLED:KEY]` sentinel catches missing slots; and `check_render_fidelity` reconciles every data-slot. Not this slice's job.
- **Live multi-sample proposal regeneration** — deferred to a phase 2.
- **The qualitative-prose judge** (tone / relevance / no-hallucination — Track A "wave a") — deferred.
- **RAG / retrieval evals** (Track A "wave b") — **blocked on Track B**, which has no corpus yet.
- **Human-label calibration set** — deferred (a strength of this slice is that it needs none).

## 11. Deliverable & success criteria

**Success** = a *trustworthy* prose-number entailment judge, **gated in CI**, over a fixture corpus that **proves** the judge (via seeded `good` / `seeded-bad-single` / `seeded-bad-buried` fixtures). Concretely:

- `figures_extractor` implemented + Python-unit-tested.
- A frozen fixture corpus spanning all three categories, `why.*` / `watch.*` / `macro.impact`, and several funds — including derived-but-consistent `good` cases.
- A Promptfoo config + rubric with a pinned Claude judge model, multi-sample repeats, and a parsed `{entailed, offending_sentence}` verdict asserted against each fixture's `expect`.
- A CI job that is green only when every verdict matches within the stated threshold — the buried-error catch being the acceptance crux.

This deliverable also **feeds the eventual "published eval case study"** named in `docs/tasks.md` (Track A).

## 12. Open items to settle during writing-plans

- Exact home for the extractor + fixtures (`consultant_engine/evals/` vs `evals/track_a/`) and how Promptfoo (Node) sits beside the Python repo.
- The precise `figures_extractor` field names and rounding/tolerance the judge is told to accept.
- Concrete judge-model id + sample count `N` + the pass threshold numbers.
- Whether the verdict assertion is `llm-rubric` or a `javascript`/`python` assertion parsing the judge JSON (the latter gives crisper control over the `offending_sentence` check).
- Cache-vs-live final call for CI (recommendation stands: live).

# Track 0 — Headless Consultant Engine (design)

**Date:** 2026-06-19
**Status:** Design — approved forks, pending spec review → writing-plans
**Tracking:** `docs/tasks.md` ENH-5 (Phase-1 master), ENH-4 (macro store, deferred), ENH-6 (macro-researcher agent, deferred)
**Scope:** Track 0 of the AI Development Skill Plan's Phase 1 — rebuild the `fund-consultant` generate→validate→repair loop as a LangGraph graph.

---

## 1. Summary

Re-implement the `fund-consultant` procedure as a runnable, headless **LangGraph `StateGraph`** in a new Python package `consultant_engine/`. It takes a client risk profile + the latest FundMaster workbook + a macro-context input, and emits a version-stamped HTML proposal that passes `tests/test_proposal_validation.py`.

This **replaces the `fund-consultant` skill entirely.** The skill bundle is **retired** once the engine exists; invocation is via CLI / Python import (no natural-language trigger). The procedure is **not** kept as a parallel prose spec — there is no document to drift. `SKILL.md` decomposes into its two natural homes, each a single source of truth with nothing duplicated:
- **Steps 1–4** (load, Step-1b eligibility, Step-2 filters, Step-3 CFS, Step-4 allocation) → **Python code** — code is the precise, testable source of truth for the algorithms.
- **Steps 5–7** (macro narrative guidance, jargon layering, fee presentation, the HTML skeleton/template) → the engine's **LLM prompt(s) + HTML template assets** — the generation guidance *becomes* the prompt; the skeleton already lives in `references/` and moves into the engine.

Track 0 also folds in the deterministic core that ENH-1/ENH-2 described — those stop being a separate "optional accelerant" and become the spine of this engine.

## 2. Locked decisions (the forks resolved during brainstorming)

1. **Role:** full headless re-implementation that replaces interactive skill execution (not a thin wrapper, not a reduced demonstrator). Full-parity end goal across every branch.
2. **Determinism boundary:** Python owns **all numbers** (load, eligibility, filter, CFS, allocation) as deterministic ground truth; the **LLM writes prose AND assembles the HTML** by filling a **locked, slotted skeleton** (semantic placeholder slots / `data-*` numeric slots), *not* free-form markup — it transcribes computed numbers into fixed slots. The validate→repair loop therefore guards: number-transcription (HTML slots vs state), template/section conformance, disclosure rules, version stamp.
3. **Macro acquisition:** **outside the graph** — macro enters as a **contract-bound structured input** (option A). A fixture (tests) or a small producer script fills it now; the ENH-6 macro-researcher agent fills the same contract later, with the graph unchanged.
4. **Build order:** **horizontal by layer** (all compute → LLM → loop), with a **Layer 0 graph-skeleton + stubs** standing up first so each layer slots into a runnable shell (mitigates horizontal's deferred-integration risk).
5. **Checkpointer + interrupt:** **in scope** — a SQLite checkpointer + an `interrupt()` on the **main path, after `build_portfolio`**, implements a "Proposed Allocation — for Consultant Review" human-in-the-loop gate (generalised from the old Step-4e shortlist gate). Review is **on by default**; a `--no-review` / auto-approve path lets evals, CI, and batch runs proceed without the pause. **Streaming is deferred** (Phase 2 / UI).
6. **e-Series branch retired (simplicity):** Step 4e, the `mode` conditional (e-Series vs Starter), `build_shortlist`, and the Pe-only universe filter are **removed entirely**. The graph is one linear path — standard portfolio build for all clients — with the consultant-review interrupt above and the experience-tier (new vs experienced) branch at `generate_proposal` as the only remaining conditionals (plus the validate→repair loop).
7. **Review-gate interaction = exit-and-resume:** on `interrupt()` the engine writes an **editable review artifact** (`data/review/<thread_id>.json`) plus a **read-only HTML allocation preview**, then exits `0`. A `--resume <thread_id>` invocation continues from the SQLite checkpoint. Human edits are **re-validated** against the deterministic invariants before generation: the consultant owns **intent** (which funds, what %), the engine owns **facts** (CFS, rank, eligibility — re-derived, never trusted from the file). Full contract in §7.
8. **Validation = one rule module, two consumers (not redundant):** the rule logic lives in one shared module. The runtime `validate` node imports it for LLM-driven **self-correction** of the live output; the offline pytest suite imports the *same* module as a deterministic **CI regression gate** (+ checker-correctness proof via known-good/known-bad fixtures, + the Track-A eval seam). Different time, input, and guarantee — see §8.

## 3. Determinism boundary (detail)

| Concern | Owner | Notes |
|---|---|---|
| Load FundMaster, Step 1b retail-eligibility exclusion | Python | openpyxl read of the latest workbook |
| Step 2 filters (Shariah, risk-level ceiling) | Python | operates on the eligible universe |
| Step 3 CFS (4 dims, profile-adaptive weights, ER-stretch modifier, tiebreaker) | Python | the deterministic scoring core (= ENH-1/ENH-2) |
| Step 4 allocation (templates, diversification, ATH momentum, 4b structural, 4c exposure-gap + dry powder, 4d satellite) | Python | one linear build for all clients |
| Human edits at the review gate | Python (re-validate on resume) | invariants replayed against edited allocation; facts re-derived |
| Macro context | Python (normalize/validate the input contract) | prose rendered in the LLM node |
| Prose (rationale, macro narrative, jargon-layered explanations) | LLM | |
| HTML assembly into the locked slotted skeleton (numbers transcribed into slots) | LLM | this is the surface the loop guards |

Because numbers are correct-by-construction in state, the loop's job is to catch the LLM mis-transcribing them into HTML, breaking section order/template, or violating a disclosure rule — not to make numbers correct.

## 4. Graph topology

One linear path — no `mode` branch, no e-Series universe restriction. Every client runs the same build.

**Compute nodes (Python):**
`load_profile` → `load_funds` (+ Step 1b) → `filter_universe` → `score_cfs` → `build_portfolio`

**Human-in-the-loop (main path):** after `build_portfolio`, the graph `interrupt()`s for consultant review of the proposed allocation — *every* proposal pauses here (unless `--no-review`). The interaction is **exit-and-resume**: the engine writes the review artifact (§7) + a read-only HTML preview and exits; state persists in the SQLite checkpointer (keyed by `thread_id`); a `--resume <thread_id>` invocation continues. On resume, any human-edited allocation is **re-validated against the deterministic invariants** before `macro_context`; a violating edit re-pauses (review ON) or fails loudly (`--no-review`).

**Macro:** `macro_context` — validates/normalizes the contract-bound macro input.

**Generation (LLM):** `generate_proposal` — structured state + locked slotted skeleton → full HTML.

**Loop:** `validate` → (violations? `repair` → `validate`) → `emit`.

**Conditional edges (only two remain):**
- at `generate_proposal`: **new vs experienced** investor (`experience_tier`, set at `load_profile`) → jargon layering / output style.
- after `validate`: → `repair` if violations and `repair_iterations < MAX`; else → `emit`. At cap with unresolved violations: **fail loudly** (non-zero exit + violation list); never silently emit a broken proposal.

```
load_profile → load_funds → filter_universe → score_cfs → build_portfolio
   → [interrupt: consultant review] ──(resume: re-validate edits)──> macro_context
   → generate_proposal → validate ⇄ repair → emit
                              │
          (fail loudly at MAX iters) ─┘
```

## 5. State schema (LangGraph state)

A typed state (TypedDict/Pydantic) with these channels:

- `inputs`: `client_profile` (risk_level, shariah, experience, upfront_capital, E_target), `macro_context` (the contract), `fundmaster_path`
- `routing`: `experience_tier` (`new` | `experienced`)
- `computed`: `eligible_funds`, `filtered_funds`, `cfs_scores` (per fund: 4 dims + composite + weights), `portfolio` (allocations), `structural`/`satellite`/`exposure_gap` picks, `fees` (PHS)
- `review`: `proposed_allocation` (the artifact written at `interrupt()`), `resume_payload` (consultant decision + edited allocation), re-validation reuses `validation.violations[]`
- `generation`: `proposal_html`
- `validation`: `violations[]`, `repair_iterations`
- `output`: `output_path`

## 6. Macro contract (the ENH-6 seam)

Typed schema — a list of dated events: `{date, theme, claim, source_url}` (theme tags align with the Step-5 query set / ENH-4 theme taxonomy). Producers, all interchangeable behind this schema:
- **now:** a fixture (tests) or a small producer script.
- **later (ENH-6):** a macro-researcher agent — its own LangGraph subgraph (search → dedupe → date → cite → cluster) — optionally backed by the ENH-4 persistent store for longitudinal deltas.

The `macro_context` node only normalizes/validates the contract; macro prose is rendered in `generate_proposal`. The graph is byte-for-byte unchanged across producer swaps.

## 7. Review-artifact contract (the HITL gate)

At `interrupt()` the engine writes `data/review/<thread_id>.json` (editable) plus a read-only HTML allocation preview. The consultant edits the JSON (or not) and runs `--resume <thread_id>`. Example — a Moderate, experienced investor, RM 50k:

```json
{
  "thread_id": "moderate-20260619-a3f9",
  "schema_version": "1.0",

  "context": {
    "client_profile": {
      "risk_level": "Moderate", "risk_band": 3, "shariah": false,
      "experience": "experienced", "upfront_capital_rm": 50000, "target_equity_pct": 60
    },
    "fundmaster": "output/fundmasters/PublicMutual_FundMaster_Jun2026_v2.3.xlsx",
    "engine_version": "0.1.0", "generated_at": "2026-06-19T10:42:00+08:00"
  },

  "constraints": {
    "_comment": "Re-validation enforces these on resume. Stay within them or it re-pauses (review ON) / fails loudly (--no-review).",
    "allocations_sum_to_pct": 100,
    "fund_count": { "min": 4, "max": 6 },
    "per_fund_cap_pct": 40,
    "risk_level_ceiling": 3,
    "required_structural": { "gold": 1, "money_market": 1 },
    "universe": "scored eligible funds only (retail-eligible, risk ≤ ceiling, Shariah filter applied)"
  },

  "allocation": [
    { "abbrev": "PeEMAS",     "role": "structural:gold",         "allocation_pct": 10, "cfs": 0.71, "rank": 7,  "risk_level": 3, "eligible": true },
    { "abbrev": "PeCDF-A",    "role": "structural:money_market", "allocation_pct": 10, "cfs": 0.55, "rank": 12, "risk_level": 1, "eligible": true },
    { "abbrev": "PIX",        "role": "core",                    "allocation_pct": 40, "cfs": 0.88, "rank": 1,  "risk_level": 3, "eligible": true },
    { "abbrev": "PeDividend", "role": "core",                    "allocation_pct": 40, "cfs": 0.83, "rank": 3,  "risk_level": 3, "eligible": true }
  ],

  "review": { "decision": "approve", "note": "" }
}
```

**Three blocks, three roles:**

| Block | Editable? | Purpose |
|---|---|---|
| `context` | read-only | provenance — who/what this build is for |
| `constraints` | read-only | the rules re-validation enforces, surfaced so edits are *informed* |
| `allocation` | **editable** | the decision — change `allocation_pct`, add/remove funds |
| `review.decision` | **editable** | `approve` / `revise` (resume re-validates either way) |

- **No change is required** — the default file is already a valid, approvable allocation; save and `--resume` to accept it. Edits are optional overrides.
- **Intent vs facts:** the consultant edits only `abbrev` and `allocation_pct`. The computed fields (`cfs`, `rank`, `risk_level`, `eligible`) are **display-only** — on resume the engine re-derives them from state/workbook and ignores anything typed there. You cannot fake a CFS, and you can only pick from the scored eligible universe.
- **Add/swap a fund:** add `{ "abbrev": "PISTF", "allocation_pct": 15 }` and rebalance to 100. On resume the engine backfills its facts and checks it's in the eligible universe; an ineligible or over-ceiling pick produces a re-validation violation.

## 8. Validate→repair loop

- `validate` recomputes from the structured ground truth in state and cross-checks the rendered HTML — the seven checks in `tests/test_proposal_validation.py`, run programmatically: section skeleton/order, CFS composite == weighted recompute (now: HTML slot values vs state numbers), recommended funds exist in source workbook, alpha-warning iff disqualified, retail-eligibility, version stamp + AI disclosure. Emits a `violations[]` list.
- `repair` receives `violations[]` + the current HTML and fixes **only** those, re-emitting HTML.
- `MAX` repair iterations = **3** (revisit during planning). At cap with unresolved violations → fail loudly.

**One rule module, two consumers** (not redundant — they share logic but run at different times, on different inputs, for different guarantees):

| | `validate` **node** (runtime) | pytest **suite** (CI) |
|---|---|---|
| When | during a live generation run | every push, offline |
| Input | the one proposal being generated | committed fixtures + golden sample |
| LLM? | yes (drives `repair`) | no — deterministic |
| Job | self-correct *this* output | catch *code* regressions |

The runtime loop structurally **cannot** do three things the suite owns: (1) **validate the validator** — known-good/known-bad fixtures prove the shared module is correct (a self-grading runtime with a buggy checker passes its own broken check); (2) **gate CI** — runtime validation runs at generation time on the user's machine and can't stop a bad commit landing, while CI pytest runs LLM-free on every push (per CLAUDE.md, keep green); (3) **seed Track A** — which re-expresses these checks as calibrated evals on the offline, fixture-driven form. So `test_proposal_validation.py` is **refactored, not deleted**: it imports the shared rule module instead of duplicating logic, reads `version` from the package (not `SKILL.md`), and points at fixtures + the golden anchor.

## 9. Tech stack

Python 3 · LangGraph `StateGraph` + SQLite checkpointer · Anthropic SDK for LLM nodes (Sonnet default for `generate_proposal`/`repair`, configurable) · openpyxl (FundMaster read) · the shared rule module reused as the validate node · CLI entry `python -m consultant_engine --profile … --fundmaster … --macro … -o …` with `--no-review` (skip the gate) and `--resume <thread_id>` (continue from checkpoint). Review artifacts land under `data/review/`. Streaming deferred.

## 10. Build order (horizontal, skeleton-first)

- **L0** — graph skeleton + state schema + all nodes stubbed; graph compiles and runs end-to-end with stubs (+ checkpointer wired, interrupt as a no-op stub).
- **L1** — deterministic compute nodes, full-parity across all branches, unit-TDD'd (the ENH-1/ENH-2 core). Graph still uses the stub LLM node.
- **L2** — real `generate_proposal` LLM node (prose + slotted HTML assembly).
- **L3** — real `validate`→`repair` loop + the consultant-review `interrupt()` gate on the main path (exit-and-resume, edit re-validation, `--no-review`).

Each layer green before the next.

## 11. Repo layout

- New top-level importable package `consultant_engine/` (graph, nodes, state, CLI, checkpointer setup, **LLM prompts + HTML slotted-template assets**, the **shared validation rule module**).
- **Retire the `fund-consultant-skill/` bundle** once the engine is live: Steps 1–4 → code; Steps 5–7 → engine prompt/template assets; the `references/` design-system + HTML skeleton move into the engine. The natural-language trigger is dropped — invocation is CLI / import.
- **Move the version source** off `SKILL.md` frontmatter onto the engine/package version; update `tests/test_proposal_validation.py::skill_version()` + the filename/footer stamping to read it from the package.
- `tests/test_proposal_validation.py` imports the shared rule module (single source of truth for the rules) and points at fixtures + the golden anchor.
- Macro contract schema + fixture/script producer live with the engine (the ENH-6 seam). Review artifacts under `data/review/`.

## 12. Deliverables (Track 0)

1. Runnable LangGraph engine (`consultant_engine/`) that emits a validator-passing proposal, with the main-path consultant-review HITL gate (exit-and-resume + edit re-validation) and a `--no-review` path.
2. "Primitives ↔ framework" mapping note (conditional dispatch, retry-until-valid loop, shared-state blackboard, planner-executor, agent handoff/subgraph, human-in-the-loop, tool use → their LangGraph expressions, incl. the MCP-tool → node mapping).
3. The macro-context contract + a fixture/script producer (the ENH-6 seam).
4. The `fund-consultant` skill bundle retired — rules → code, prose-generation → prompt/template assets, version source → package; CLI / import is the sole entry point.

## 13. Scoped out of Track 0

- Streaming / token-level UI (Phase 2 hosted demo).
- The macro-researcher agent itself (ENH-6) and the persistent macro store (ENH-4) — Track 0 ships only the contract + a fixture (and, optionally, a thin script); the **live web-search producer is deferred to ENH-6**.
- Track A eval harness and Track B regulatory RAG — separate tracks; Track A later measures this engine, Track B plugs a retrieval node into generation.
- Deploy / hosting / observability — Phase 2.

## 14. Open items to settle during writing-plans

- Exact `MAX` repair iterations (default 3) and the fail-loud surface (exit code + machine-readable violation log).
- Precise macro-contract schema fields + theme taxonomy (resolve jointly with ENH-4/ENH-6). **Track 0 ships the contract + a fixture only; the live producer is ENH-6's.**
- **Parity golden anchor:** nominate an existing `output/examples/` proposal as the structural reference the engine must reproduce at L2/L3, so "full parity" is falsifiable.
- **Fan-out/fan-in for per-fund prose — assessed: viable, but single-node is the working default.** All selection interdependence (top-holdings overlap dedup, diversification, satellite carving from the lowest-alpha core fund, ranks, role assignment) is resolved in the deterministic layer *before* prose, so per-fund cards are self-contained — they narrate fixed scalars (rank, role, allocation) and never read sibling cards. Clean shape: **map** per-fund card prose → **reduce** = whole-portfolio sections (Executive Summary, Macro Alignment, Investment Strategy) + the document-global jargon define-once pass + HTML assembly. Refinements that shrink the map set: the two structural positions (gold PeEMAS; money market PeCDF-A, or PIMMF-A for Shariah) are always-included with formulaic rationale → **template their cards deterministically**, out of the LLM map set. So the map set is only the alpha-selected cards (+ optional satellite / exposure-gap) — roughly **2 in a 4-fund Starter, up to ~5 in a full Aggressive portfolio**. At N≈2 fan-out isn't worth the orchestration; it's only marginally attractive at the high end, and then for isolation/repair + the `Send`-API showcase, not throughput. Caveat: naive independent workers break the jargon "define-a-term-once-per-document" rule — handle the glossary deterministically (define-once injection/strip) or in the reduce stage. Decide map-vs-single at planning.
- Model selection per node + token/cost budget for a full run.
- Cutover plan for retiring the skill bundle without breaking CI: update the CLAUDE.md skill table + trigger docs, `scripts/sync-private.sh` references, and the version-source move — sequence so `pytest` stays green throughout.

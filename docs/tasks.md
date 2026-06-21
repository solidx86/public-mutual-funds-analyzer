# Tasks

Tracked enhancement / follow-up work for the public-mutual-funds-analyzer.
Status legend: `TODO` · `IN PROGRESS` · `DONE` · `WONTFIX`

---

## ENH-1 — Harden the LLM-reasoned consultant layer against hallucination / drift

**Status:** PARTIALLY DONE (Track 0, 2026-06-20) — the deterministic CFS / allocation / exposure engine shipped in `consultant_engine`; deterministic PHS **fee** extraction is the open remainder.

> **Update 2026-06-21 (determinism-hardening / proposal-polish pass):** moved the remaining LLM-authored *facts* into Python — §3 profile + cover/exec facts, the §9 sources list, the per-fund alpha-warning disclosure text, and the §7 RSP table — and removed the display-only portfolio-VF surface (never computed; not a construction input). The LLM now authors only genuine-synthesis prose (9 slots), with the determinism boundary locked by `test_llm_prose_surface_is_locked_to_genuine_synthesis`. Open remainder unchanged: deterministic PHS **fee** extraction.

**Raised:** 2026-06-14
**Area:** `consultant_engine/` (was `fund-consultant-skill/`, now retired)

> **Delivered by Track 0:** CFS scoring + normalization + allocation roll-ups + asset/geo pie
> percentages are now Python (`consultant_engine/cfs.py`, `portfolio.py`, `exposure.py`); the LLM
> consumes computed numbers into a locked slotted skeleton and the validate→repair loop guards
> transcription (CFS, performance, exposure, portfolio-summary). **Still open:** the PHS sales /
> management / trustee **fee** numbers remain LLM/em-dash (the highest-consequence transcription
> risk) — that's the remaining half of this ENH, pairing naturally with ENH-2's structured store.

### Problem
The fund-consultant skill is **entirely LLM-executed** — it ships no `scripts/`, only
`SKILL.md` + `references/` (templates + CSS). At proposal-generation time Claude:
- opens the latest `PublicMutual_FundMaster_*.xlsx`, reads Master-sheet cells, and does
  **all math by reasoning** — CFS composite score, normalization, alpha/AE/momentum
  weighting, allocation roll-ups, geo/asset-class pie percentages;
- opens each `<Abbr>_PHS.pdf` and **transcribes** the three fee numbers (sales charge,
  management fee, trustee fee) verbatim.

Both are reasoning + fact-finding, so proposal output is **non-deterministic** and carries
real risk of arithmetic error, transcription error, and drift between runs — unlike the
screener pipeline, which is byte-stable (same `mfr_results.json` in → identical workbook out,
verified 2026-06-14: v1.4 vs v1.5 differ only in the filename version stamp and one footer date).

`tests/test_proposal_validation.py` already exists as an *eval/validator* (CFS recomputation,
template conformance, disclosure rules, retail eligibility) — i.e. it catches errors *after*
a proposal is generated. The gap is reducing the chance of error *during* generation, and/or
making the numeric steps deterministic.

### Candidate directions (to scope, not yet decided)
- **Deterministic CFS engine:** move CFS scoring + normalization + allocation roll-ups +
  pie-percentage math into a small Python helper (reads the workbook, emits the computed
  numbers), so Claude consumes computed values instead of doing arithmetic. Mirrors the
  screener's "numbers are deterministic" principle.
- **PHS fee extraction helper:** deterministic parse of the "FEES & CHARGES" section into a
  structured fee record per `<Abbr>` (today it's verbatim LLM transcription). Reduces the
  highest-consequence transcription risk (client-facing fees).
- **Strengthen the validator:** tighten `test_proposal_validation.py` tolerances and add
  fee cross-checks against PHS so drift is caught harder post-generation.
- **Self-check pass:** add a generation-time recompute-and-compare step before the proposal
  is finalized.

### Acceptance (draft)
- Numeric proposal values (CFS inputs/outputs, allocations, fees) are reproducible run-to-run
  for the same workbook + client profile, or are independently re-verified before output.
- No regression to the locked-template conformance / disclosure rules.

### Notes
- Do NOT reintroduce determinism by pinning expected values in `KNOWN_*` sets — those must
  stay empty (see CLAUDE.md / `tests/test_proposal_validation.py`).
- Decide scope via the brainstorming → writing-plans flow before implementing.

---

## ENH-2 — Canonical single-source-of-truth data store; build workbook from it

**Status:** TODO
**Raised:** 2026-06-14
**Area:** `fund-screener-skill/scripts/`, data storage layer
**Related:** ENH-1 (a deterministic store also removes the consultant's PHS fee transcription risk)

### Idea
Make a canonical per-fund data store the **single source of truth**, and build the FundMaster
workbook (and ideally feed the consultant) from it — instead of the current arrangement where
workbook columns are stitched together at build time from **three** different origins:

| Origin | Today's columns |
|---|---|
| `mfr_results.json` (per-MFR extraction) | most fund data: name, performance, allocation, geo/sector, holdings, VF/VC, benchmark, weighted_alpha |
| `funds_risk_level.xlsx` (external lookup) | Risk Level (col 6) |
| `ath_results.json` (scraped) | ATH band (cols 69–73) |
| computed at build | Status (10), Rationale (13), per-period Alpha (17/20/23/26/29), AE (30–34) |
| **not in workbook at all** | Sales/management/trustee fees — live only in PHS PDFs, read ad hoc by the consultant |

### Key design insight — static vs. volatile data
Per-fund data splits into two lifetimes, and the store should model that explicitly:

- **Static / slow-changing reference data** (set once, rarely changes): risk level, fund type,
  sales charge + management + trustee fees, launch date, Shariah flag, benchmark name,
  asset_class / geography classification labels (the ENH? relabel fields).
- **Volatile / per-MFR data** (refreshed every monthly report): performance returns, AUM /
  fund size, asset allocation, geo breakdown, sector breakdown, top-5 holdings, NAV/ATH.

A new MFR ingest would then **update only the volatile fields**, leaving static reference data
untouched — rather than today's full overwrite of `mfr_results.json` (which, notably, also
wipes the Step 1.5 relabel each run).

### Open questions to resolve in design
- Storage format: keep JSON, or move to SQLite / a normalized schema (static table + monthly
  snapshots keyed by fund × month)?
- Where do fees live and how are they sourced (manual entry vs. one-time PHS parse)?
- Do we keep monthly history (time series) or only latest? History enables trend analysis but
  enlarges the store.
- Migration: seed the static table from current data without re-scraping.
- How the consultant consumes it (still via the workbook, or directly from the store).

### Benefits
- One authoritative store; workbook becomes a pure render of it (testable, reproducible).
- Static data entered/verified once → less re-extraction risk each month.
- Fees become first-class structured data → directly addresses ENH-1's transcription risk.
- Relabel/classification fields would have a durable home that monthly ingest won't clobber.

### Notes
- Scope via brainstorming → writing-plans before implementing; likely larger than ENH-1.
- Respect existing locked decisions (don't edit `extract_mfr.py` semantics casually;
  qualification rule stays weighted-alpha > 0; PRS funds stay excluded).

---

## ENH-3 — Durable consultant-profile file for the fund-consultant to render from

**Status:** TODO
**Raised:** 2026-06-14
**Area:** `fund-consultant-skill/`

### Problem
The consultant's own credentials (name, FIMM number `F01091705`, contact details — everything
in the cover top-bar `cover-contact` block, document footer, and disclaimer block) are currently
**loaded purely from memory**. `SKILL.md:1007` even codifies this: *"Consultant credentials …
Sourced from memory file `user_consultant_details.md`."*

But that file does not exist as a tracked artifact:
- the project memory dir is empty — `user_consultant_details.md` isn't there;
- it's nowhere in the repo (`grep` finds the name only inside `SKILL.md`).

So the profile survives only as long as it's in conversational/working memory. On a fresh clone
or a cleared session the consultant has **no authoritative source** for these invariant fields and
would either omit them, prompt for them, or hallucinate them — silently breaking the locked
template (cover-footer must contain exactly the 4 spans incl. `FIMM F01091705`; cover top-bar must
carry the full `cover-contact` block — see Step 7.5 items 4–5).

### Idea
Give the fund-consultant a durable, version-controlled profile file to pull from instead of memory:
- a structured Markdown (or YAML-front-matter) file holding the invariant consultant fields —
  legal/display name, FIMM reg no., agency, phone/email, and any footer/disclaimer boilerplate;
- live it inside the skill bundle so it ships with a clone, e.g.
  `fund-consultant-skill/references/consultant_profile.md`;
- repoint `SKILL.md` (Step 7.3 token substitution + the Step 7.5 self-check) at that file as the
  single source of truth, replacing the "memory file" wording;
- treat its values as `[BRACKETED]`-style tokens substituted at render time, same mechanism as
  `[SKILL_VERSION]`.

### Open questions to resolve in design
- File location & format: `references/consultant_profile.md` vs. a `.yaml`; structured fields vs.
  pre-rendered HTML snippets for cover-contact / footer / disclaimer.
- Privacy: are any of these fields sensitive enough to keep out of git? (FIMM no. is on every
  client-facing proposal already, so likely fine to track — confirm.)
- Migration: capture the current in-memory values into the file as the seed.
- Should the profile also carry the `cover-brand` "Solid + Public Mutual" branding, or keep that
  template-fixed?

### Acceptance (draft)
- A fresh clone (no memory) can render a template-conformant proposal: cover-contact, the 4
  cover-footer spans (incl. `FIMM F01091705`), and the footer/disclaimer credentials all populate
  from the tracked profile file with no prompting and no hallucinated values.
- `SKILL.md` no longer references a memory file for consultant credentials.
- No regression to Step 7.5 self-check items 4–5 or the locked-template conformance test.

### Notes
- Scope via brainstorming → writing-plans before implementing (small, but touches the locked
  template path).

---

## ENH-4 — Macro-context grounding via a persistent RAG / memory store (Track B — DEFERRED)

**Status:** TODO — parked; pick up in a dedicated fresh session
**Raised:** 2026-06-19
**Area:** `fund-consultant-skill/` (Step 5 macro context), retrieval/eval layer

### Context
Surfaced while evaluating this repo as the capstone for the AI Development Skill Plan's
*Track B — RAG / retrieval (close the embeddings gap)*. Macro-grounding was explored as one
candidate RAG surface, then **deliberately deferred** — there isn't enough to uncover without a
focused session, and the higher-value Track-B target is **proposal citation-grounding** over the
regulatory/disclosure (PHS/prospectus/SC/LHDN) corpus only (the *active* Track-B direction;
fund-commentary grounding and macro are both separate, later workstreams).

### How macro context is gathered TODAY (baseline to build on)
`SKILL.md` Step 5 (lines 719–744): at proposal-generation time the skill runs **12 live web
searches** (Malaysia: BNM OPR, GDP/inflation, ringgit, KLCI, data-center/AI; Global: Fed, global
equity, China/Asia, trade war, Middle East, AI megatrend, recession risk), each parameterized
`[current year]`. Macro narrative prose is "written fresh"; macro table rows are "populated from
web-searched dated events; cite source URLs" in §9 (lines 1004–1009).
**So today: live web-search at generation time, dated + URL-cited, NO persistent store — each
proposal re-searches cold.**

### Proposed model IF pursued
- Keep **web-search as the acquisition path** (unchanged).
- Add a **theme-keyed, append-only, dated log** of each proposal's macro findings (memory).
- At generation: retrieve the theme's prior views, diff the fresh search against the latest stored
  view, surface the **delta** ("OPR held at 2.75% since May — unchanged" vs "Fed pivoted since last
  proposal"). Enables a longitudinal "weeks-ago X → now Y" narrative.

### Key design insights (don't lose these)
- **Staleness ≠ age. Staleness = contradiction by a newer search.** A 3-week-old "AI supercycle
  intact" snapshot is *corroborated*, not stale, if today's search still says so. Flag only when a
  newer search on that theme *materially diverges*. A blanket age / "as-of" guard is trigger-happy —
  it mis-fires on slow structural theses.
- **Themes have heterogeneous half-lives:** OPR/inflation/ringgit move on data-release cadence
  (weeks); structural theses (AI supercycle, data-center buildout) move on quarters. Change-detection
  must be theme-aware, not a single timer.
- **Embeddings earn their place only in theme-clustering** (collapse "AI capex supercycle broadens" ≈
  "semiconductor megatrend intact" into one theme) and **fund-exposure ↔ theme matching.** The
  dated-event storage/retrieval itself is structured. So macro is a *hybrid* (structured time-series +
  an embedding layer), not pure vector RAG.
- **The macro eval-set decays** (last week's correct answer is wrong this week) → it cannot be a
  stable CI regression gate; evaluate point-in-time or with templated cases. This is a key reason the
  regulatory corpus — not macro — is the CI-gateable Track-B eval.
- **First-order defect is conformance, not staleness:** the example proposal
  (`FundProposal_Aggressive_Jun2026_v1.27.html`) stated macro claims (inflation 1.6%, Middle East
  conflict, central-bank gold, AI capex) **uncited**, despite Step 5 mandating cite-URLs. The first
  fix is "every macro sentence traces to a retrieved dated source" (faithfulness) — a grounding/eval
  problem — before any persistent store.

### Open questions for the fresh session
- Store format: structured table (theme × date × source) + an embedding index for clustering, or a
  full vector store?
- Theme taxonomy: fixed list (the 12 Step-5 queries) vs. emergent clustering.
- Change-detection: how to define "material divergence" per theme (LLM-judged vs. a stance/similarity
  threshold).
- Backfill: seed a short history so a delta is demonstrable on day one (weeks, not a year — macro
  moves fast).
- Eval: point-in-time / templated cases; explicitly NOT a CI gate.
- Scope boundary vs. the floated **"fund Q&A chatbot over all funds + MFR content"** idea — does macro
  fold into that, or stay separate?

### Notes
- The **acquisition agent** that fills the macro contract and reads/writes this store is tracked
  separately as **ENH-6** (producer); this entry (ENH-4) is its persistent-memory model.
- Macro is the **biggest must-cite defect by consequence** in the current proposal (e.g. the gold
  sleeve rationale rests on an uncited geopolitical claim). Deferring it means the citation-grounding
  work (regulatory / tax / fees) will **not** close the macro gaps — the proposal stays partially
  ungrounded until this is done. Acceptable as a deliberate scoping call; flagged so it is not lost.
- Scope via brainstorming → writing-plans before implementing.

---

## ENH-5 — Phase 1 of the AI Development Skill Plan: harden this repo as the public RAG/eval capstone (MASTER TRACKING)

**Status:** IN PROGRESS — Track 0 **SHIPPED** (the headless `consultant_engine`, PR #2; 2026-06-20, 209 tests green); Track A (evals) is the next action
**Raised:** 2026-06-19
**Area:** whole repo (consultant + screener + new eval / retrieval layers)
**Source plan:** `~/Documents/Claude/Projects/Job/ai-development-skill-plan.md` (external, not in repo).
Phase 1 = "LangGraph quick win + evals + RAG/retrieval depth", ~140 hrs.
**Related:** ENH-1 & ENH-2 (determinism — the real owner of numeric correctness), ENH-4 (macro-RAG, deferred).

### Why this repo is the capstone
Clean deterministic-pipeline → LLM-generation seam (ideal for evals + retrieval); regulated
financial-advisory domain = credibility story; easiest to make runnable without client PII. Phase 1
here closes the top recurring JD gaps: vector RAG (#1, ~8/11 JDs), named framework **LangGraph**
(~7/11, hard-required at Dassault), and legible eval tooling.

### The structured-vs-RAG boundary (the central scoping decision)
RAG (Track B) applies ONLY to unstructured prose where a claim needs an external source passage.
Everything numeric/tabular is structured lookup, owned by the deterministic pipeline + ENH-1/ENH-2 —
**never RAG.**

| Content | Owner |
|---|---|
| Fund selection / CFS scoring / **performance numbers** (all tabular data) | Structured lookup + deterministic pipeline (ENH-1/ENH-2) — never RAG |
| Regulatory / tax / fee / eligibility **claims needing a source passage** (PHS, prospectus, SC, LHDN) | **Track B RAG** — the SOLE Track-B corpus |
| Macro context | Deferred → ENH-4 |
| Fund commentary | Dropped (sat in the "correctly NOT cited" tier; fuzzy ground truth) |

### Track 0 — LangGraph quick win (✅ DELIVERED 2026-06-20)
- **Shipped** as the headless `consultant_engine/` package (PR #2). Spec:
  `docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md`; code-review +
  remediation: `docs/superpowers/notes/track0-code-review-findings.md`.
- Slice: rebuild the consultant's **generate → validate → repair loop** as a LangGraph graph.
  *Refined during brainstorming away from the original sketch:* the e-Series-Shortlist-vs-Starter
  `mode` branch was **retired** (one universal 4-fund build), and new-vs-experienced became
  **presentation-only** — so the only conditionals are the experience branch at `generate_proposal`
  and the validate⇄repair loop. The HITL consultant-review `interrupt()` gate (exit-and-resume) was
  added on the main path.
- The validate node shares one rule module (`consultant_engine/rules/validation.py`) with
  `tests/test_proposal_validation.py` — no dependency on Track A.
- Deliverables shipped: runnable LangGraph artifact + the "primitives ↔ framework" mapping note
  (`docs/superpowers/notes/primitives-to-langgraph.md`). Determinism boundary fully closed
  (Python owns every number; the LLM only writes prose).

### Track A — Evals (the measuring instrument; precedes / overlaps Track B)
- Stand up Promptfoo/Braintrust + Ragas (Phase-0 toolchain residual).
- Wave (a): re-express `test_proposal_validation.py` as legible *generation* evals + add an
  **LLM-as-judge** for the prose surface, **calibrated against human labels** (report agreement rate).
- Wave (b): *retrieval* evals — RAG triad (Faithfulness, Answer/Context Relevance) over Track B.
  Gate the whole suite in CI.
- Deliverable: a published eval case study.

### Track B — Regulatory citation-grounding RAG (iterates against Track A's evals)
- Sole corpus: regulatory/disclosure (PHS, prospectus, SC, LHDN). Function: ground the proposal's
  must-cite fee/tax/cooling-off/eligibility claims in retrieved, cited passages.
- Full pipeline (corpus built from scratch — there is NO existing BM25 to "upgrade"):
  build corpus → chunk + Anthropic-style contextual retrieval → **pgvector** dense + BM25 **hybrid**
  (build both halves) → **rerank** (cross-encoder / Cohere/Voyage) → wire into generation → measure
  with Track-A retrieval evals → CI gate → port to **Qdrant** to compare tradeoffs.
- Under-exercised here: embeddings **quantization** recall-tradeoff (corpus too small to motivate) →
  deferred to Phase 3 model-layer / a later fund-Q&A expansion.

### The three-layer separation (do NOT conflate)
- **ENH-1/ENH-2 (determinism):** correctness *at the source* — deterministic CFS engine + structured
  fee extraction so numbers can't be wrong. The real owner of numeric correctness.
- **Track A (evals):** the *checks* — recompute + cross-check; catches what it has ground truth for.
- **Track 0 (LangGraph loop):** the *control flow* — runs the check inline + repairs. A
  detector/safety-net, NOT the correctness guarantee.
The validate→repair loop only catches numbers the validator can independently recompute/cross-check;
it does not make numbers correct — that is ENH-1/2's job.

### Recommended sequence
0. Lock decisions (this entry, ENH-5). ← done when this is written.
1. Track 0 — LangGraph (brainstorm → writing-plans → TDD).
2. Track A — eval harness, wave (a) then (b).
3. Track B — regulatory RAG, iterating against Track A.
4. Eval case study.
- ENH-1/ENH-2 = optional accelerant; a deterministic-CFS slice before/with Track A gives the loop +
  evals cleaner ground truth. Not on the critical path.

### Runnability / infra decisions
- Real corpus stays in the private symlink mount (`public-mutual-funds-analyzer-private`); the vector
  index is a **gitignored, regenerable build artifact** (the `master_funds.csv` precedent). The public
  repo ships code + eval methodology + published metrics, not the data.
- Runnability is satisfied by a **gated hosted demo** (Phase 2 — behind auth), not clone-and-run. The
  **"fund Q&A chatbot" over all funds + MFR content** is that hosted surface and a *later* expansion
  (where macro + scale + quantization could eventually live).
- Synthetic corpus only needed if a fully-open (ungated) public demo is ever wanted.

### Scoped OUT of Phase 1 (tracked, not forgotten)
- Macro-RAG (ENH-4); fund-commentary grounding; embeddings quantization-at-scale.
- Deploy / observability / multi-provider / K8s / Azure → **Phase 2**.

### Phase-1 "done" = 4 artifacts
1. Runnable LangGraph artifact (consultant loop) + primitives↔framework note.
2. Capstone hybrid-RAG-grounded (regulatory corpus; pgvector→Qdrant; hybrid + rerank + contextual
   chunking).
3. Measured retrieval+generation eval suite (RAG triad + calibrated judge), gated in CI.
4. Published eval case study.

### Notes
- Each track: brainstorm → writing-plans → TDD before implementing (repo convention).
- Deploy/hosting is Phase 2 — Phase 1 ends at a local, CI-gated, hybrid-RAG-grounded capstone +
  the case study.

---

## ENH-6 — Macro-researcher agent: the upstream producer of the macro-context contract

**Status:** TODO — deferred; later than Track 0 (Track 0 ships the contract + a script/fixture producer first)
**Raised:** 2026-06-19
**Area:** new `macro-researcher/` agent (its own LangGraph subgraph), feeding `fund-consultant` Step 5
**Related:** ENH-5 Track 0 (defines & consumes the macro-context contract), ENH-4 (the persistent
macro store this agent eventually retrieves from / writes to).

### Context
Falls out of the Track-0 design decision (ENH-5) to make **macro a contract-bound INPUT to the
consultant graph** rather than a live web-search tool node *inside* it. The graph consumes only a
typed macro-context contract (dated events + source URLs + theme tags) and never knows how that
contract was produced. That dependency-inversion seam is what makes acquisition swappable:

- **Track 0 (now):** the contract is filled by a small web-search script (prod) or a fixture (tests).
- **ENH-6 (later):** the *same* contract is filled by a dedicated **macro-researcher agent** —
  search → dedupe → date → cite → cluster-by-theme — with **zero change to the consultant graph**.

### Why a separate ENH (not folded into ENH-4)
- **ENH-4** is the *persistent macro store / retrieval model* (theme-keyed append-only dated log,
  staleness = contradiction-not-age, heterogeneous half-lives, embeddings only for theme-clustering).
- **ENH-6** is the *agent that does the acquisition* and writes/reads that store. ENH-6 is the
  producer; ENH-4 is its memory. ENH-6 can ship a first version backed only by live search (no
  persistent store) and gain ENH-4's longitudinal "weeks-ago X → now Y" delta later.

### Why it's worth its own workstream (capstone value)
- A separable researcher agent feeding the consultant through a typed contract demonstrates
  **agent handoff / subgraph composition** — a stronger multi-agent / LangGraph narrative than one
  monolith doing its own web search. Good portfolio surface.

### Open questions for its own brainstorming session
- Is it a LangGraph subgraph invoked as a node, or an out-of-band job whose output is fed in? (The
  contract seam supports both — pick per runnability/eval needs.)
- Contract schema: exact shape of the dated-event records + theme taxonomy (shared with ENH-4's
  theme taxonomy question — resolve together).
- Where it sits vs. the floated "fund Q&A chatbot" (shared upstream research substrate?).

### Notes
- Do NOT start before Track 0 has shipped the contract + script/fixture producer — ENH-6 is an
  upgrade of the producer behind a stable interface, not a prerequisite.
- Scope via brainstorming → writing-plans before implementing.

---

## ENH-7 — Small-upfront-capital fund selection (standard high-performer vs e-Series low-entry)

**Related:** ENH-5 Track 0 (decision 11 — capital adequacy is flagged, not solved), ENH-8 (the
deployment-plan sibling). Falls out of the Track-0 decision to retire the e-Series shortlist mode.

### Problem
Track 0 builds one universal 4-fund portfolio and is **capital-blind**: standard funds need
**RM 1,000** initial per fund, e-Series need only **RM 100** (confirmed from the Master
Prospectuses). A client with small upfront capital can't clear the RM 1,000 minimum on every
sleeve of a standard 4-fund build, so a higher-performing standard fund may simply be
**unreachable** for them — while a lower-entry e-Series fund is. Track 0 only *flags* this; it
does not reason about the trade-off.

### Idea
A selection layer that, for small-capital clients, reasons explicitly between **a higher-performing
standard fund the client can't yet fully fund** vs **a lower-entry e-Series alternative** — surfacing
the performance gap, the entry-minimum gap, and a recommendation. The e-Series universe (Pe-prefix)
and the RM 100 entry point are the levers retired from the old Step-4e shortlist mode, repurposed as
a *reasoned* choice rather than a hard mode switch.

### Notes
- Needs the per-fund minimum-investment data as first-class structured input (pairs naturally with
  ENH-2's canonical store). Scope via brainstorming → writing-plans before implementing.

---

## ENH-8 — Contribution / deployment plan to clear per-fund minimums

**Related:** ENH-5 Track 0 (decision 11), ENH-7 (the selection sibling — different problem: *which*
fund vs *when/how-much*).

### Problem
Even with the right funds chosen, a small-capital client may not be able to fund all four sleeves to
their RM 1,000 standard-fund minimum **at once**. The portfolio is correct in *target weights* but
not yet *fundable in one lump*. Track 0 produces target allocations only — it has no notion of
staging contributions over time.

### Idea
A deployment/phasing planner that turns a target 4-fund allocation + an upfront-capital figure (and
optional monthly capacity, e.g. RM 100/mo additional minimums) into a **funding schedule**: which
sleeves to seed first to clear RM 1,000, which to layer in over subsequent months, and how the
portfolio converges to target weights. Distinct from ENH-7 (selection) — this is execution
scheduling.

### Notes
- Consumes the same per-fund minimum data as ENH-7. The HITL review gate is the natural surface to
  present a proposed schedule for consultant adjustment. Scope via brainstorming → writing-plans
  before implementing.

---

## ENH-9 — Per-fund-card top-5 holdings + country-exposure chart

**Status:** TODO — not now (parked; idea captured)
**Raised:** 2026-06-21
**Area:** `consultant_engine/` (Section 4 fund cards — `templates.py` structural card render),
data source `mfr_results.json`
**Related:** ENH-2 (top-5 holdings + geo breakdown are already listed as volatile per-MFR fields in
the canonical store), ENH-1/Track 0 (determinism — this stays Python-rendered, never LLM prose).

### Idea
Each fund card in Section 4 currently shows meta / CFS / performance / asset-exposure but not the
fund's own **top-5 holdings** or a **per-fund country (geographic) exposure** breakdown. Add both to
the card:
- **Top-5 holdings** — name + weight %, rendered as a small ranked list or mini bar.
- **Country exposure** — a compact per-fund geographic chart (mirroring the portfolio-level geo pie
  in Section 6, but scoped to the single fund).

This deepens the per-fund story (what the fund actually holds, where) without touching the
portfolio-level look-through in Section 6.

### Why deterministic (Python-owned)
Both are facts already extracted into `mfr_results.json` (ENH-2 lists `top-5 holdings` and
`geo breakdown` as volatile per-MFR fields). They must render as engine facts via the structural
card template — **never** routed through the LLM as prose (same determinism boundary as the existing
card numbers and the Section 6 pies).

### Open questions to resolve in design
- Chart treatment: reuse the Section 6 conic-gradient pie component per fund, or a horizontal bar
  list (cards are narrower than the full-width exposure section)?
- Holdings display: top-5 only, or top-5 + "Other %"? Show weights or rank only?
- Card vertical budget: cards are already dense — does this go inline, behind a sub-heading, or in a
  two-column split with the existing asset exposure?
- Data availability: confirm every screened fund carries top-5 + geo in `mfr_results.json` (handle
  funds missing the field gracefully).

### Notes
- Not doing this now — captured so it isn't lost.
- Scope via brainstorming → writing-plans before implementing; stays inside the determinism
  boundary (facts from the workbook/JSON, Python-rendered).

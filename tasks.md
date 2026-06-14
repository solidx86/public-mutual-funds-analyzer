# Tasks

Tracked enhancement / follow-up work for the public-mutual-funds-analyzer.
Status legend: `TODO` · `IN PROGRESS` · `DONE` · `WONTFIX`

---

## ENH-1 — Harden the LLM-reasoned consultant layer against hallucination / drift

**Status:** TODO
**Raised:** 2026-06-14
**Area:** `fund-consultant-skill/`

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

# Proposal Polish + LLM-Responsibility Audit

**Date:** 2026-06-21 · **Branch:** `track0-headless-consultant-engine-spec` · **Status:** APPROVED plan, not yet executed
**Why this doc:** captured for fresh execution (the originating session ran very long). Source of truth = this file.

---

## Part 1 — LLM-responsibility audit (what the LLM authors, by section)

Legend: **PY** = Python-owned (deterministic). **LLM** = free LLM prose. **PARTIAL** = Python scaffolding/structure with LLM prose inside. **⚠FACT** = currently LLM but is a *fact Python already knows* → determinism gap worth closing.

> Note: `fund_cards`, `fee_table.fund_rows`, `portfolio_summary.fund_rows`, `macro.events_rows`, the exposure pies/legend, and (as of 2026-06-21) the 4 cover facts use `<!--slot:-->` syntax but are **Python-substituted before prose fill** — they are PY, not LLM.

| Section | Field / slot | Owner | Notes |
|---|---|---|---|
| **Cover** | `cover.profile` | LLM ⚠FACT | risk level — Python knows it |
| | `cover.subtitle` | LLM | tagline — genuine prose, OK |
| | `cover.shariah` | LLM ⚠FACT | Shariah pref — Python knows it |
| | `cover.fundmaster_month_year` / `month_year` / `proposal_date` / `prepared_date` | PY | fixed 2026-06-21 (`3157df0`) |
| | `cover.target_annual_return_pct` / `funds_selected_n` / `funds_screened_m` | PY | data-slots |
| **Foundation** (Unit Trust / Returns / Cooling-Off) | — | PY (static) | new-investor block; no slots |
| **1 · Executive Summary** | `exec_summary.profile` | LLM ⚠FACT | "Moderate" — derivable |
| | `exec_summary.composition` | LLM ⚠FACT | "2 bond, 1 gold, 1 MM" — derivable from portfolio |
| | `exec_summary.thesis` | LLM | genuine prose, OK |
| | `portfolio.volatility_class` | LLM ⚠FACT | "Low-Medium" — derivable from VF |
| | CFS / 3Y Alpha / VF numbers + bold labels | PY | data-slots + static `<strong>` |
| **2 · Global & Local Macro Context** | `macro.month_year` | LLM ⚠FACT | report month — Python should own (like cover) |
| | macro table Event + Date columns | PY | engine-rendered from the macro contract |
| | `macro.impact.N` (Implication per row) | LLM | per-row prose — **needs bolding** |
| | `macro.themes` (Medium-Long Horizon Themes) | LLM | prose — **needs bolding** |
| **3 · Client Risk Profile** | `profile.name_description` | LLM ⚠FACT | profile name+desc |
| | `profile.target_note` | LLM ⚠FACT | **bug:** `load_profile` computes a realism warning that is *discarded*; "empty" is a PY verdict, not an LLM canvas → PY both branches |
| | `profile.shariah` | LLM ⚠FACT | Python knows |
| | `profile.experience_level` | LLM ⚠FACT | Python knows |
| | `profile.rl_ceiling` | LLM ⚠FACT | **Python owns the RL-ceiling rule** |
| | `profile.target_vf_range` | LLM ⚠FACT | Python owns the VF-range rule |
| | `profile.target_annual_return_pct` | PY | data-slot |
| **4 · Fund Recommendations** | fund card structure (meta, CFS, perf, exposure numbers) | PY | all numbers Python-owned |
| | `why.<FUND>` (Why We Chose It) | LLM | prose — **needs bolding** |
| | `watch.<FUND>` (What to Watch) | LLM | prose — **needs bolding** |
| | `alpha_warning.<FUND>` | LLM ⚠FACT | div is PY-gated; **prose is near-boilerplate Python knows** (status / weighted-alpha / role / alloc) → static PY string |
| **5 · Portfolio Summary** | summary rows + weighted CFS/Alpha/VF | PY | engine-rendered |
| | `portfolio.volatility_class` | LLM ⚠FACT | (same as §1) |
| **6 · Portfolio Exposure** | asset + geo pies, legends, asset % | PY | deterministic look-through |
| **7 · Investment Strategy** | `strategy.rsp` | LLM ⚠FACT(partial) | contains the allocation split (Python facts) → **RSP table** |
| | `strategy.distribution` | LLM | prose → **bullets** |
| | `strategy.rebalancing` | LLM | prose → **bullets** |
| | `strategy.dip_capture` | LLM | prose → **bullets** |
| **8 · Fee Disclosure** | fee table structure | PY | values are `—` (deferred, ENH-1) |
| **9 · Disclaimer / Sources** | AI-Gen / Regulatory / Cooling-Off / Conflict | PY (static) | locked disclosure text |
| | `sources.fundmaster` / `sources.web_urls` / `sources.phs_list` | LLM ⚠FACT | **fix in this pass** (all are facts) |

**Headline gaps the audit reveals (beyond the agreed polish):**
- **§3 Client Risk Profile is almost entirely LLM-authored facts** — the biggest remaining determinism gap. Profile name, Shariah, experience, RL ceiling, VF range are all things Python computes (the load_profile rules).
- **Cover `profile`/`shariah`, §1 `exec_summary.profile`/`composition`/`volatility_class`, §2 `macro.month_year`** are LLM-authored facts too.

---

## Part 2 — Approved polish plan (this pass)

1. **Sources → Python-owned** (`generate_proposal`, substitute before prose fill like the cover):
   - `sources.fundmaster` = the source workbook basename (e.g. `PublicMutual_FundMaster_Jun2026_v1.00.xlsx`).
   - `sources.web_urls` = the live macro events' `source_url`s (dedup, as `<li>` items).
   - `sources.phs_list` = `<Abbr>_PHS.pdf` for each portfolio fund (`<li>` items).
2. **Consistent emphasis (Option A)** — extend the prose prompt so the LLM wraps key figures, percentages, and fund names in `<strong>` in: `macro.impact.N`, `macro.themes`, `why.<FUND>`, `watch.<FUND>`. (Exec Summary already gets its bold from Python scaffolding.)
3. **Investment Strategy readability:**
   - **`strategy.rsp` → Python-rendered RSP table** (Fund · Allocation % · per RM 1,000), from portfolio allocations (deterministic). Keep a one-line LLM intro slot if desired.
   - **`strategy.distribution` / `rebalancing` / `dip_capture` → `<ul><li>` bullet lists** (prompt the LLM to return bullets, not a paragraph).

Land in one "proposal polish" commit; then regenerate a fresh proposal to review.

## Part 3 — Determinism hardening (follow-ups; NOT this pass unless approved)

> **2026-06-21 review-pass addendum.** A second content review re-classified three slots and found one bug. Two self-corrections logged from that review: (i) `name_description` is a PY candidate because it is generic per-profile boilerplate with no client-specific input — *not* (as first claimed) because the prompt mandates exact wording; that mandate is the jargon table's, the `name_description` instruction only gives an `e.g.`. (ii) `target_note` is PY in **both** branches — first understated as "leave the empty case to the LLM."

### Re-classified to Python (this review pass)
- **`alpha_warning.<FUND>` → PY static string.** The div is already PY-gated (renders only for a Disqualified structural fund); the prose is near-boilerplate Python fully knows (status, weighted alpha, role, allocation). Promote to a templated static disclosure. Removes the last per-card LLM disclosure and closes the FAKE_LLM convergence hole (today FAKE_LLM emits `[alpha_warning narrative]`, the real LLM writes the sentence).
- **`profile.target_note` → PY, both branches (bug fix).** `load_profile` already computes a realism warning when `target > ceiling` — but it is **silently discarded**; the slot never carries it. "Empty" (target ≤ ceiling) is a *Python verdict*, not a blank canvas for the LLM. Make the slot wholly Python: the computed warning when it fires, a static standard qualifier otherwise. Remove the LLM from this slot entirely. (The LLM's goals-grounded "N-year horizon" is a *separate* concern — surface it in a genuine prose slot or via a structured `horizon_years` field; do not smuggle it into a deterministic qualifier.)
- **`profile.name_description` (description half) → PY static lookup.** The `Moderate` label is already a fact; the one-sentence description is generic per-profile boilerplate (no client-specific input) → a 4-row lookup keyed by risk level. The LLM only adds run-to-run variance here, not value.

### §3 Client Risk Profile + the other LLM-authored facts (the headline gap)
- Remaining `profile.*` → PY data-slots from `load_profile`: `shariah`, `experience_level`, `rl_ceiling`, `target_vf_range` (plus the `name_description` label, above). Largest single win.
- Cover `profile` / `shariah`; §1 `exec_summary.profile` / `composition` / `volatility_class` (also rendered in §5); §2 `macro.month_year` → Python.

### Prompt hygiene (real risk, not cosmetic)
- Trim `assets/prompts/generate_proposal.md` to **only** the slots still LLM-owned. It still instructs the model on ~7 slots Python now owns or that are deferred — `cover.fundmaster_month_year`, `cover.proposal_date` / `prepared_date`, `macro.events_rows`, `portfolio_summary.fund_rows`, `fee_table.fund_rows`, `fees.PIX.phs_date`. A stale prompt invites the LLM to re-emit markup for already-filled slots, re-introducing the exact transcription risk Track 0 removed.
- `cover.subtitle` stays LLM framing but instruct it to **omit numbers** (fund count / target range are facts).

### Deferred
- Fees (§8) — ENH-1 PHS extraction.

## Test/verify expectations
- Each Python-owned slot lands an adversarial/consistency test (per repo convention).
- After changes, a live e2e run must converge AND pass `tests/test_proposal_validation.py` (29/29).
- Keep the bare-`pytest` suite green.

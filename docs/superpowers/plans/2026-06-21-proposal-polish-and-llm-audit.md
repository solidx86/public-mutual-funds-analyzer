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

## Part 2 — Combined implementation scope (this pass)

> **Scope decision (2026-06-21):** the Part-3 determinism hardening is **folded into this pass** — one combined commit (or a short ordered series), not a deferred follow-up. Only **fees (§8, ENH-1)** remain out of scope. After this pass the LLM authors *only* genuine synthesis prose (see "Remaining LLM-owned" below).
>
> **Review-pass addendum & self-corrections (kept for the trail):** a second content review re-classified three slots and found one bug. (i) `name_description` is a PY candidate because it is generic per-profile boilerplate with no client-specific input — *not* (as first claimed) because the prompt mandates exact wording; that mandate is the jargon table's. (ii) `target_note` is PY in **both** branches — first understated as "leave the empty case to the LLM."

### Group 1 — Profile / cover / exec facts → Python data-substitution
Extend the existing "substitute before prose fill" block in `generate_proposal` (the same mechanism that already fills the 4 cover facts). Each slot gets a **named authoritative source** — no new rules except where Group 2 says so:

| Slot (also where duplicated) | Python source |
|---|---|
| `cover.profile`, `exec_summary.profile` | `client_profile["risk_level"]` |
| `cover.shariah`, `profile.shariah` | `client_profile["shariah"]` — **3-way** map: `True`→"Shariah-compliant", `False`→"Conventional", `None`→"No preference (both)". ⚠ Today `null` is mislabeled "Conventional" — fix as part of this. |
| `profile.experience_level` | `client_profile["experience"]` → "New investor" / "Experienced investor" |
| `profile.rl_ceiling` | **reuse** `filter_universe.RISK_CEILING[risk_level]` (Cons=2, Mod=3, MA=4, Agg=5) — do **not** duplicate the map |
| `exec_summary.composition` | count built-portfolio holdings by fund type → "2 bond, 1 gold, 1 MM" (small format helper) |
| `profile.name_description` | `risk_level` label + a **new** static 4-row description lookup (one sentence per profile) |
| `profile.target_note` | PY both branches: `load_profile`'s computed warning when `target > ceiling`, else a static standard qualifier. **Remove the LLM from this slot.** |
| `macro.month_year` | derive from the macro-context snapshot date |

### Group 2 — Two NEW locked mappings (⚠ DECISION REQUIRED before coding)
`portfolio.volatility_class` (VF→class label; rendered in §1 **and** §5) and `profile.target_vf_range` (per-profile VF band, e.g. Moderate "6–12 (Low-Medium)") have **no rule today — the LLM invents them.** Folding to Python means **defining authoritative, client-facing band boundaries + a per-profile VF-range table** (locked numbers, like the qualification rule). This needs consultant sign-off, not silent invention.
- **Recommended:** define one VF-band scheme + per-profile ranges in a small rule module, with a test pinning each profile's range. Boundaries to be confirmed at implementation (placeholder e.g. Low <6, Low-Medium 6–12, Medium-High 12–18, High ≥18).
- **If the boundaries aren't signed off in time:** these two stay the *only* profile/portfolio facts the LLM fills — ship the rest of the pass, leave these as a tracked stub. Do not block the whole pass on them.

### Group 3 — `alpha_warning.<FUND>` → PY static templated string
Render in the card template (`templates.py`), not as a prose slot. Remove it from the collected prose keys; update the FAKE_LLM fill + the determinism-guard test (the structural-card test already asserts the div is PY-emitted — extend it to assert the *text* is Python's).

### Group 4 — Sources → Python-owned
Substitute before prose fill, like the cover:
- `sources.fundmaster` = source workbook basename (e.g. `PublicMutual_FundMaster_Jun2026_v1.00.xlsx`).
- `sources.web_urls` = the live macro events' `source_url`s (dedup, as `<li>` items).
- `sources.phs_list` = `<Abbr>_PHS.pdf` for each portfolio fund (`<li>` items).

### Group 5 — Investment Strategy readability
- **`strategy.rsp` → Python-rendered RSP table** (Fund · Allocation % · per RM 1,000), from portfolio allocations (deterministic). Optional one-line LLM intro slot.
- **`strategy.distribution` / `rebalancing` / `dip_capture` → `<ul><li>` bullet lists** (prompt returns bullets, not a paragraph).

### Group 6 — Prompt + emphasis (LAST — after the slot set is final)
- **Trim** `assets/prompts/generate_proposal.md` to **only** the slots still LLM-owned. It still instructs the model on slots Python now owns or that are deferred (`cover.fundmaster_month_year`, `cover.proposal_date`/`prepared_date`, `macro.events_rows`, `portfolio_summary.fund_rows`, `fee_table.fund_rows`, `fees.PIX.phs_date`, plus everything moved to PY above). A stale prompt invites the LLM to re-emit markup for already-filled slots, re-introducing the transcription risk Track 0 removed.
- **Bolding:** instruct the LLM to wrap key figures, %, and fund names in `<strong>` in `macro.impact.N`, `macro.themes`, `why.<FUND>`, `watch.<FUND>`.
- **`cover.subtitle`:** keep LLM framing but **omit numbers** (fund count / target range are facts).
- **Bullets:** instruct `strategy.distribution`/`rebalancing`/`dip_capture` to return `<li>` items.

### Remaining LLM-owned after this pass (the genuine-synthesis surface)
`cover.subtitle` (no numbers) · `exec_summary.thesis` · `macro.impact.N` · `macro.themes` · `why.<FUND>` · `watch.<FUND>` · `strategy.distribution` / `rebalancing` / `dip_capture`. *(Plus `volatility_class` + `target_vf_range` only if Group 2's boundaries are deferred.)*

### Deferred (still out of scope)
- Fees (§8) — ENH-1 PHS extraction.

### Suggested order
Group 1 → 3 → 4 → 5 (independent, mechanical) → Group 2 (gated on the VF decision) → Group 6 (prompt last). Land as one pass or a short series; regenerate a fresh proposal to review; keep `tests/test_proposal_validation.py` at 29/29.

## Test/verify expectations
- Each Python-owned slot lands an adversarial/consistency test (per repo convention).
- After changes, a live e2e run must converge AND pass `tests/test_proposal_validation.py` (29/29).
- Keep the bare-`pytest` suite green.

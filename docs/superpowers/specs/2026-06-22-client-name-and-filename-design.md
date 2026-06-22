# Client name + robust proposal filenaming — design

**Date:** 2026-06-22
**Status:** Approved (ready for implementation plan)
**Component:** `consultant_engine/`

## Problem

The client's name is absent end-to-end:

- It is **not a field** in the `ClientProfile` data structure (`consultant_engine/state.py`) nor in any `data/profiles/*.json` sample.
- It is **never rendered** in the proposal — the cover page (`assets/proposal_skeleton.html`) shows Risk Profile, dates, and data source, but no recipient.
- `emit.py` half-handles it for the *filename* only, and does so with two stale conventions: it uses **last-name-only** and orders the name segment last, after a date segment that is the **FundMaster workbook vintage** (`MonYYYY`) rather than the generation date.

The documented naming convention (`CLAUDE.md`) is correspondingly stale, and the three tracked example proposals still carry the old name shape.

## Goals

1. Make `client_name` a first-class **optional** profile field (default `""` = generic).
2. Render the client's name on the proposal cover when present; omit cleanly when generic.
3. Adopt a robust, documented filename convention:
   - Named: `FundProposal_<ClientName>_<RiskProfile>_<YYYY-MM-DD>_v<version>.html`
   - Generic: `FundProposal_generic_<RiskProfile>_<YYYY-MM-DD>_v<version>.html`
4. Validate post-generation that the name rendered correctly (or is correctly absent).
5. Update stale documentation and the tracked example filenames.

## Non-goals

- No `--client-name` CLI flag. The profile JSON is the single owner of client facts; a name reaches the engine only through the profile.
- No change to how the FundMaster vintage is displayed *inside* the proposal (the "Data Source" cover cell stays `FundMaster <Mon YYYY>`). The vintage simply stops being the filename's date segment.
- No PII handling beyond HTML-escaping. Real (client-named) runs are already gitignored; only generic examples are public.

## Design decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Filename date segment | Generation date as `YYYY-MM-DD` | Daily uniqueness, clean sort; the FundMaster vintage is still shown inside the proposal so no information is lost. |
| Name in filename | Full name, spaces **and** punctuation removed, case preserved | Keeps full identity; underscore stays an unambiguous field separator. |
| Render location | A single "Prepared for" line on the cover, under the subtitle | One prominent placement; omitted entirely when generic. |
| Name channel | Profile JSON only | Single owner; no CLI surface to keep in sync. |

## Architecture

The change touches one field and threads it through the existing pipeline stages. Each unit keeps its current single responsibility.

### 1. Data model — `client_name` as an optional profile field

- **`consultant_engine/state.py`** — add `client_name: str` to the `ClientProfile` `TypedDict`. (`TypedDict` is a type hint, not runtime-enforced, so existing callers/tests that omit it keep working.)
- **`consultant_engine/nodes/load_profile.py`** — normalize and default the field, alongside the existing `experience`/`target_annual_return_pct` defaults. This is the **input-validation boundary** (concern A below):
  - trim leading/trailing whitespace;
  - collapse internal whitespace runs to a single space;
  - strip control characters / newlines (would corrupt the filename or the HTML);
  - cap length (100 chars) to keep filenames sane;
  - `setdefault(..., "")`; an all-whitespace value normalizes to `""` (generic).

  After this node every downstream node sees a guaranteed, render- and filename-safe `client_name`.
- **`data/profiles/*.json`** — add `"client_name": ""` to all four samples so the field is discoverable; the samples stay generic.

### 2. Render — "Prepared for" line on the cover (Python-owned)

- **`assets/proposal_skeleton.html`** — insert one marker on its own line under the cover subtitle:
  `<!--slot:cover.prepared_for_block-->`
- **`consultant_engine/nodes/generate_proposal.py`** — in the cover-facts block (substituted *before* prose fill, like the other deterministic facts), build:
  - has name → `<div class="cover-prepared-for">Prepared for <strong>{html.escape(name)}</strong></div>`
  - generic → `""` (the whole block collapses — no empty div)

  "Has name" = `bool(client_name.strip())`. The name is **HTML-escaped** — it is the one free-text user value reaching the DOM. The block is fully Python-owned: the LLM never authors it and so can never drift it.
- **`assets/design_system.css`** — a small `.cover-prepared-for` rule matching the cover's type scale.

### 3. Filename — `emit.py` rewritten

```
FundProposal_<NameOrGeneric>_<Risk>_<YYYY-MM-DD>_v<version>.html
```

- `<NameOrGeneric>` = `re.sub(r'[^A-Za-z0-9]', '', client_name)` (full name, spaces + punctuation stripped, case preserved); falls back to `generic` when the result is empty (empty/whitespace/all-punctuation input).
- `<Risk>` = `risk_level` with spaces removed (e.g. `ModeratelyAggressive`).
- `<YYYY-MM-DD>` = `datetime.now()` (generation date) — replaces the old FundMaster-vintage segment.
- `<version>` = unchanged (parsed from the `fund-consultant v…` HTML stamp, falling back to `__version__`).

The stale docstring is rewritten Google-style to describe the new shape.

Examples:
- `FundProposal_TanWeiMing_Aggressive_2026-06-22_v0.1.0.html`
- `FundProposal_generic_Moderate_2026-06-22_v0.1.0.html`

### 4. Validation — post-generation conformance (concern B)

Two validations, two places, split by concern:

- **(A) Input validation** lives at `load_profile` (§1) — fail/normalize fast at the boundary, before expensive LLM work, and feed a clean value to both the renderer and the filename builder.
- **(B) Output conformance** lives in the post-generation validate layer, as requested:
  - **`consultant_engine/rules/validation.py`** — new pure rule `check_prepared_for(html_text, client_name)`:
    - named → assert the `Prepared for <strong>{escaped}</strong>` line is present and carries the expected escaped name; else violation `prepared_for_missing`.
    - generic → assert no `cover-prepared-for` block leaked; else violation `prepared_for_unexpected`.
  - **`validate_html`** gains an optional `client_name: str = ""` parameter and includes `check_prepared_for` in its composite run. The default keeps the legacy eval's existing positional calls (`validate_html(html, version, idx)`) working unchanged.
  - **`consultant_engine/nodes/validate.py`** — pass `state["client_profile"].get("client_name", "")` into `validate_html`.

  **Caveat (by design):** the prepared-for block is Python-owned/deterministic, so a `check_prepared_for` violation cannot be meaningfully fixed by the LLM `repair` node — it would loop `MAX_REPAIR` times then `fail`. This mirrors the existing `check_unfilled_slots` rule (a surviving marker is a structural bug, not LLM prose). The rule's value is a **fail-loud regression guard**: it catches a future skeleton/marker edit or escaping bug that silently drops or mangles the name, guaranteeing the engine never emits a proposal where the recipient vanished.

### 5. Examples — rename to the new generic convention

The three tracked examples are generic (their source profiles have no name) and carry an internal `Prepared 12 Jun 2026` date. Rename them to:

- `FundProposal_generic_Aggressive_2026-06-12_v0.1.0.html`
- `FundProposal_generic_Moderate_2026-06-12_v0.1.0.html`
- `FundProposal_generic_ModeratelyAggressive_2026-06-12_v0.1.0.html`

Bodies are unchanged: being generic, they correctly show no prepared-for line (they demonstrate the generic path; the named path is covered by unit tests). The legacy eval discovers proposals by glob and resolves each workbook from the cover's "Data Source" cell, so renaming is safe; its only filename assertion (`endswith("_v0.1.0.html")`) still holds.

### 6. Documentation

- **`CLAUDE.md`** — update the *Outputs & versioning* line from the stale `FundProposal_<RiskProfile>_<MonYYYY>[_<ClientName>]_v<skill-version>.html` to the new named/generic convention with the generation-date segment.
- Code docstrings are rewritten Google-style for every touched function (`emit`, `load_profile`, `check_prepared_for`, the `generate_proposal` cover-facts helper).

## Testing

- **`tests/consultant_engine/test_emit.py`** — new order/date segment; a generic case (`FundProposal_generic_…`); a full-name-spaces-removed case (`Tan Wei Ming` → `TanWeiMing`); a punctuation/whitespace-only name → `generic` fallback.
- **`tests/consultant_engine/test_generate_proposal.py`** — the `Prepared for <strong>…</strong>` line renders (escaped) when named; absent when generic.
- **`tests/consultant_engine/test_load_profile` coverage** — `client_name` defaults to `""`; normalization (trim, collapse whitespace, strip control chars, length cap, whitespace-only → `""`).
- **`tests/consultant_engine/test_validation_rules.py`** — `check_prepared_for` both directions (named present/missing/mismatched; generic clean/leaked).
- **`tests/test_proposal_validation.py`** (legacy eval) — confirm it stays green against the renamed examples; `KNOWN_*` pin sets stay empty.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| HTML injection via client name | `html.escape` at render; control chars stripped at `load_profile`. |
| Filename collisions (same client+profile, same day) | Acceptable — overwrite is the intended behavior for a regenerated same-day proposal; version segment differentiates across engine versions. |
| Deterministic-fact violation wastes repair cycles | Documented, accepted (mirrors `unfilled_slot`); the check is a fail-loud guard, not a repair trigger. |
| Legacy eval coupling to filenames | Verified: discovery is glob + cover-cell based, not filename-parsed. |

## HTML companion

Per repo convention, a self-contained `2026-06-22-client-name-and-filename-design.html` ships alongside this markdown and is regenerated whenever the markdown changes. Markdown is the source of truth.

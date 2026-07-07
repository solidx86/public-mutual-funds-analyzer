# Prose-number eval fixtures

Frozen, hand-authored `(slot_key, figures, prose, expect, offending_sentence?,
category)` records — the judged inputs for the prose-number entailment eval
(see `docs/superpowers/specs/2026-07-06-track-a-prose-number-eval-design.md`).
One JSON file per record; one record ↔ one Promptfoo test case ↔ one judge
call ↔ **one slot instance** (never per-proposal, never per-fund-type — the
1:1 mapping in the design's §5).

## Schema

```json
{
  "slot_key": "why.PAPFF",
  "figures": { "...": "consultant_engine.evals.figures_extractor.extract_figures() output" },
  "prose": "the LLM-authored narrative HTML for this slot",
  "expect": "entailed",
  "offending_sentence": null,
  "category": "good"
}
```

| Field | Type | Notes |
|---|---|---|
| `slot_key` | string | `why.<ABBR>`, `watch.<ABBR>`, or `macro.impact.<n>` — matches the real `<!--slot:KEY-->` markers `consultant_engine/nodes/generate_proposal.py` emits. |
| `figures` | object | The ground-truth numbers this slot's prose is checked against. **Frozen via extract-then-freeze**: a real `ConsultantState` is built, `extract_figures(state)` is run for real, and its output is copied verbatim here — never hand-invented. Every fixture in this corpus uses the **whole** `extract_figures` output (`funds` + `portfolio` + `by_derived_class`), not a per-slot slice — this mirrors production, where the real prose-authoring LLM call is also handed the full `portfolio` + `cfs_scores` state for every slot (see `_prose_instruction` in `generate_proposal.py`), and keeps every fixture's ground truth internally consistent and comparable. |
| `prose` | string | Hand-authored HTML narrative, in the same shape the real slot renders (`why.*`/`macro.impact.*` — inline HTML, no wrapping block tag; `watch.*` — 2-4 `<li>…</li>` items), matching the "for keys starting `watch.` output 2-4 `<li>` items" instruction the real generator gives the LLM. |
| `expect` | `"entailed"` \| `"contradicted"` | The verdict a correct judge must return for this record's reduced (whole-slot) verdict. |
| `offending_sentence` | string \| null | Required (non-null) and must appear **verbatim as a substring of `prose`** whenever `category` is a `seeded-bad-*` variant; `null` for `good`. Identifies the sentence carrying the planted wrong number. |
| `category` | `"good"` \| `"seeded-bad-single"` \| `"seeded-bad-buried"` | See below. |

## Categories

- **`good`** — real, correct prose/figure pairs. Some are verbatim restatements
  of a single figure; others are **adversarial-but-correct DERIVED** cases
  (spec §4a policy 4a) — an average, a sum of two exposure slices, a
  superlative, or a pre-computed `by_derived_class`/`portfolio` aggregate that
  is not literally any one slot figure but is arithmetically consistent with
  the figure set. These measure the judge's **precision** (false-positive
  rate): a judge that flags every unfamiliar number would sail through a
  good-set of only verbatim restatements yet be useless in production.
- **`seeded-bad-single`** — take a `good` pair, plant exactly **one** wrong
  number, set `expect: "contradicted"` and `offending_sentence` to the
  sentence carrying it.
- **`seeded-bad-buried`** — several **correct** numbers plus **exactly one**
  planted wrong one, with the wrong one placed in the *middle* of the
  sentence run (never first or last) so it cannot be caught by only reading
  the first or last claim. **This is the acceptance crux** (spec §7): several
  of these deliberately reuse the correct-shaped-but-wrong "blended alpha"
  derivation trap called out in spec §4a (a number that looks like a valid
  average/derivation but doesn't match the true weighted figure) — the
  subtlest failure mode a holistic judge can miss.

## Coverage (Phase 2, 19 fixtures)

| Family | good | seeded-bad-single | seeded-bad-buried |
|---|---|---|---|
| `why.*` | 3 | 2 | 2 |
| `watch.*` | 2 | 2 | 2 |
| `macro.impact.*` | 3 | 1 | 2 |

Six distinct funds appear as slot subjects across the corpus: `PIATAF`,
`PCSF`, `PeEMAS`, `PeCDF-A` (Scenario A — a growth-tilted 4-holding
portfolio) and `PBLNF`, `PSTIF` (Scenario B — a balanced/defensive-tilted
4-holding portfolio, which reuses the *same* `PeEMAS`/`PeCDF-A` structural
sleeve records as Scenario A, since those are literally the same real funds
regardless of which client portfolio holds them).

`tests/evals/test_fixtures_valid.py` is the offline half of this corpus's
self-check (schema + coverage, no API key); the live judge half is a later
phase (Phase 4).

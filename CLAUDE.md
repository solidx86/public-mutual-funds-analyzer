# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A two-stage system for a Public Mutual unit trust consultant (Malaysia):

1. **Screening pipeline** — ingests Public Mutual Monthly Fund Report (MFR) PDFs + scrapes ATH NAV from publicmutual.com.my, produces a formatted Excel "FundMaster" workbook.
2. **Consulting layer** — reads the latest FundMaster workbook + a client's risk profile, generates an HTML client proposal.

The screener stage is driven by a skill; the consultant stage is a headless Python package.

## Where the logic lives

| Skill | Trigger phrases | Path |
|---|---|---|
| `fund-screener` | "screen the new MFR", "run the fund screener", "new MFR is out" | `fund-screener-skill/SKILL.md` |

The screener skill bundle has a `references/` directory (templates, framework docs, design system CSS) and a `scripts/` directory with the pipeline.

### Consultant engine

The consulting layer is the `consultant_engine/` LangGraph package — a headless CLI, not a Claude Code skill. Invoke it from the repo root:

```bash
python -m consultant_engine --profile <p.json> [--fundmaster <wb.xlsx>] [-o <dir>] [--no-review] [--resume <thread_id>]
```

`--fundmaster` is **optional**: omit it to use the newest `PublicMutual_FundMaster_*.xlsx` under `output/fundmasters/` (else `output/examples/fundmasters/`). Ready-to-run sample profiles — one per risk level, all `experience: "new"` — live in `data/profiles/`. Run `python -m consultant_engine --help` for the full flag/profile-field reference.

**HITL review gate** — by default the engine pauses after drafting, writes `data/review/<thread_id>.json` + a preview `.html`, and exits. Run `--resume <thread_id>` to continue after consultant review. Pass `--no-review` to auto-approve (evals, CI, batch runs).

**Offline mode** — set `CONSULTANT_ENGINE_FAKE_LLM=1` to stub all LLM calls for fast local testing.

## Pipeline at a glance

Run all four steps **from the repo root** — every script derives its paths from its own location. Cache files read/written under `data/cache/`, reference data under `data/reference/`.

```bash
python3 fund-screener-skill/scripts/extract_mfr.py        # → data/cache/mfr_results.json
python3 fund-screener-skill/scripts/fetch_ath.py          # → data/cache/ath_results.json (warm, ~30s)
python3 fund-screener-skill/scripts/build_sheet_data.py   # → data/cache/master_funds.csv
python3 fund-screener-skill/scripts/build_xlsx.py         # → output/fundmasters/PublicMutual_FundMaster_<MonYYYY>_v<ver>.xlsx
```

`fetch_ath.py --cold` does a full NAV history pull (~2 min, first run only). `--refresh-codes` force-refreshes `fund_code_map.json` when a new fund is missing.

Full step-by-step semantics, sanity checks, and troubleshooting live in `fund-screener-skill/SKILL.md`.

## Tests & CI

```bash
pip install -r requirements.txt pytest && pytest
```

- `tests/test_pipeline.py` runs pipeline steps 3–4 offline from the tracked JSONs in a temp workspace — it never touches the repo's tracked outputs.
- `tests/test_proposal_validation.py` is the eval layer for generated proposals (locked-template conformance; CFS / performance / exposure / portfolio-summary recomputation; disclosure rules; retail eligibility) cross-checked against the FundMaster workbook each proposal names. The `KNOWN_*` pin sets at the top must stay empty — if a regenerated proposal trips one, fix the proposal, don't pin it.
- CI (`.github/workflows/ci.yml`) runs the same `pytest` on every push to main; keep it green.

## Outputs & versioning

- `output/fundmasters/PublicMutual_FundMaster_<MonYYYY>_v<skill-version>.xlsx` — screener output
- `output/fund_proposals/FundProposal_<RiskProfile>_<MonYYYY>[_<ClientName>]_v<skill-version>.html` — consultant output

For the **screener**, `<skill-version>` is parsed from the `version:` field in `fund-screener-skill/SKILL.md` frontmatter. Bump the skill's frontmatter version when changing the skill (semver: minor for backward-compatible, major for breaking).

For the **consultant**, the version comes from `consultant_engine.__version__` (currently `0.1.0`). The stamp label in filenames and footers is the literal `fund-consultant v<ver>` — kept as-is for proposal-validator continuity. Bump `consultant_engine/__init__.py` when changing the engine (same semver convention).

The live `output/fundmasters/` and `output/fund_proposals/` dirs are **gitignored** — real (possibly client-named) runs stay local and are never committed.

## Public / private data split

Copyrighted source PDFs (`unit-trust/`, `private-retirement-scheme/`) and real outputs (`output/fund_proposals/`, `output/fundmasters/`) are **not** in this public repo — they are gitignored symlinks mounting the private repo `public-mutual-funds-analyzer-private` (see README → *Public / private split*). Only `output/examples/` is public.

**After** `consultant_engine` writes a proposal, or `fund-screener` writes a FundMaster workbook, run `scripts/sync-private.sh` to commit + push the new/updated file to the private repo. The script resolves the private repo through the symlink mount (no hardcoded path) and no-ops on a public-only clone.

## Repo conventions worth knowing

- **Qualification rule is weighted alpha > 0%**, not a binary beat-rate. Legacy beat-rate columns (Beat %, period checkmarks) are kept for display only — do not reintroduce the old binary gate as the qualifier.
- **Cached intermediate files** in `data/cache/`: `mfr_results.json`, `ath_results.json`, `fund_code_map.json` are **tracked** (so a fresh clone has working data without re-scraping). `data/cache/master_funds.csv` is **gitignored** (cheap to regenerate from the three JSONs).
- **PRS PDFs** in `private-retirement-scheme/` are deliberately excluded by `extract_mfr.py` — the screener is UT-only.
- **MFR parsing edge cases** (abbreviations with spaces like `P SmallCap`, casing mismatches like `PSMALLCAP` vs `P SmallCap` in the API code map) are handled inside the pipeline. If a fund goes missing from ATH output, the escape hatch is `fetch_ath.py --refresh-codes`.
- `data/reference/funds_risk_level.xlsx` is the authoritative risk-level lookup (1–5 scale) keyed by fund abbreviation, joined in `build_sheet_data.py`.
- **Specs and plans always ship an HTML companion.** Every design spec (`docs/superpowers/specs/*.md`) and implementation plan must have a standalone, self-contained HTML copy alongside it (same basename, `.html`) for easy browser review — regenerate it whenever the markdown changes so the two never drift. Markdown remains the source of truth.

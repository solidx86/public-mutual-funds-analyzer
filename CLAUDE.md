# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A two-stage system for a Public Mutual unit trust consultant (Malaysia):

1. **Screening pipeline** — ingests Public Mutual Monthly Fund Report (MFR) PDFs + scrapes ATH NAV from publicmutual.com.my, produces a formatted Excel "FundMaster" workbook.
2. **Consulting layer** — reads the latest FundMaster workbook + a client's risk profile, generates an HTML client proposal.

Both stages are driven by skills. The skills' `SKILL.md` files are the source of truth for procedure — read them before doing pipeline or proposal work, and don't duplicate their content here.

## Where the logic lives

| Skill | Trigger phrases | Path |
|---|---|---|
| `fund-screener` | "screen the new MFR", "run the fund screener", "new MFR is out" | `fund-screener-skill/SKILL.md` |
| `fund-consultant` | "recommend funds for a moderate investor", "build a portfolio for…" | `fund-consultant-skill/SKILL.md` |

Each skill bundle has a `references/` directory (templates, framework docs, design system CSS) and, for the screener, a `scripts/` directory with the pipeline.

## Pipeline at a glance

Run all four steps **from the repo root** — every script derives its paths from its own location, and relative reads (`Unit Trust (UT)/`, `mfr_results.json`, etc.) resolve from cwd.

```bash
python3 fund-screener-skill/scripts/extract_mfr.py        # → mfr_results.json
python3 fund-screener-skill/scripts/fetch_ath.py          # → ath_results.json (warm, ~30s)
python3 fund-screener-skill/scripts/build_sheet_data.py   # → master_funds.csv
python3 fund-screener-skill/scripts/build_xlsx.py         # → output/fundmasters/PublicMutual_FundMaster_<MonYYYY>_v<ver>.xlsx
```

`fetch_ath.py --cold` does a full NAV history pull (~2 min, first run only). `--refresh-codes` force-refreshes `fund_code_map.json` when a new fund is missing.

Full step-by-step semantics, sanity checks, and troubleshooting live in `fund-screener-skill/SKILL.md`.

## Tests & CI

```bash
pip install -r requirements.txt pytest && pytest
```

- `tests/test_pipeline.py` runs pipeline steps 3–4 offline from the tracked JSONs in a temp workspace — it never touches the repo's tracked outputs.
- `tests/test_proposal_validation.py` is the eval layer for generated proposals (locked-template conformance, CFS recomputation, disclosure rules, retail eligibility) cross-checked against the FundMaster workbook each proposal names. The `KNOWN_*` pin sets at the top must stay empty — if a regenerated proposal trips one, fix the proposal, don't pin it.
- CI (`.github/workflows/ci.yml`) runs the same `pytest` on every push to main; keep it green.

## Outputs & versioning

- `output/fundmasters/PublicMutual_FundMaster_<MonYYYY>_v<skill-version>.xlsx` — screener output
- `output/fund_proposals/FundProposal_<RiskProfile>_<MonYYYY>[_<ClientName>]_v<skill-version>.html` — consultant output

The `<skill-version>` is parsed from the `version:` field in the corresponding `SKILL.md` frontmatter and stamped automatically into output filenames and footers. Bump the skill's frontmatter version when changing the skill (semver: minor for backward-compatible, major for breaking).

## Repo conventions worth knowing

- **Qualification rule is weighted alpha > 0%**, not a binary beat-rate. Legacy beat-rate columns (Beat %, period checkmarks) are kept for display only — do not reintroduce the old binary gate as the qualifier.
- **Cached intermediate files** at repo root: `mfr_results.json`, `ath_results.json`, `fund_code_map.json` are **tracked** (so a fresh clone has working data without re-scraping). `master_funds.csv` is **gitignored** (cheap to regenerate from the three JSONs).
- **PRS PDFs** in `Private Retirement Scheme (PRS)/` are deliberately excluded by `extract_mfr.py` — the screener is UT-only.
- **MFR parsing edge cases** (abbreviations with spaces like `P SmallCap`, casing mismatches like `PSMALLCAP` vs `P SmallCap` in the API code map) are handled inside the pipeline. If a fund goes missing from ATH output, the escape hatch is `fetch_ath.py --refresh-codes`.
- `funds_risk_level.xlsx` is the authoritative risk-level lookup (1–5 scale) keyed by fund abbreviation, joined in `build_sheet_data.py`.

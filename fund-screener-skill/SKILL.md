---
version: "1.5"
name: fund-screener
description: >
  Bulk-screen all Public Mutual unit trust funds from Monthly Fund Report (MFR) PDFs and produce a fund master list as a formatted Excel file (importable to Google Sheets). Applies weighted alpha scoring: qualifies funds whose weighted alpha (YTD 5%, 1Y 15%, 3Y 40%, 5Y 25%, 10Y 15%) is positive, ensuring alpha quality matters more than binary pass/fail counts. Use this skill whenever the user says things like: "screen the new MFR", "update the fund qualification list", "which funds qualify this month", "run the fund screener", "update with the [month] MFR", "new monthly report is out — re-run the analysis", or any request to produce or refresh a qualified funds shortlist from Public Mutual MFR data. Also trigger when the user wants to compare qualified funds across months, filter by asset class (equity, bond, Shariah), or update the Google Sheet / Excel output. If the user drops new MFR PDFs and says "these are out" or "new reports", use this skill.
---

# Public Mutual Fund Screener (v1.1)

You are running a monthly fund-qualification pipeline for a Public Mutual unit trust consultant.
The pipeline reads MFR PDFs, fetches All-Time High NAV from the Public Mutual website, scores
every fund against its benchmark, and outputs a formatted Excel workbook with a Master sheet
(all funds) and a Summary dashboard.

**All scripts live in `fund-screener-skill/scripts/` inside the Funds project folder.**
**All scripts auto-derive their paths from their own location — no manual path configuration needed.**

---

## How the screening works

**Qualification rule:** A fund qualifies if its **weighted alpha score is positive** (> 0%)
across available return periods. Minimum 2 periods required.

**Weighted Alpha Formula:**
```
Weighted Alpha = (YTD_Alpha × 5%) + (1Y_Alpha × 15%) + (3Y_Alpha × 40%) + (5Y_Alpha × 25%) + (10Y_Alpha × 15%)
```

When a period is unavailable (fund too young), its weight is redistributed proportionally
across available periods.

**Why these weights?**
- 3Y (40%): Current team's track record — most reliable signal of repeatable skill
- 5Y (25%): Smooths through market cycles — shows structural edge
- 1Y (15%): Recent execution and momentum
- 10Y (15%): Long-term structural advantage for mature funds
- YTD (5%): Very recent direction — lowest weight due to noise

**Why weighted alpha over binary beat rate?**
The previous system counted each period as an equal pass/fail vote (≥60% needed). This penalized
funds with strong 3Y/5Y alpha caught in short-term macro headwinds (a single bad YTD could flip
the result), while letting funds with marginally positive alpha in many periods but negative
overall alpha sneak through. Weighted scoring measures *how much* alpha was generated, not just
*how often*, with heavier emphasis on the periods that matter most.

**Legacy columns preserved:** The workbook still shows Beat %, Periods Assessed, and period
checkmarks (✔/✘) in the Rationale for quick visual reference. The Weighted Alpha (%) column
is the actual qualification driver.

---

## Pipeline overview

| Step | Script | Output |
|---|---|---|
| 1 | `extract_mfr.py` | `mfr_results.json` |
| 1.5 | (Claude Code, in-session — no script) | `mfr_results.json` (relabeled) |
| 2 | `fetch_ath.py` | `ath_results.json` + `fund_code_map.json` |
| 3 | `build_sheet_data.py` | `master_funds.csv` |
| 4 | `build_xlsx.py` | `.xlsx` workbook |

Run all steps from the Funds project folder. **Step 2 is required for ATH columns.** If
`ath_results.json` is absent, Steps 3–4 still run but the ATH MOMENTUM band will be empty.

---

## Step 1: Extract MFR PDFs → mfr_results.json

MFR files live under `Unit Trust (UT)/`. Named like:
```
[MFR FEB26] Public Series Funds.pdf
[MFR FEB26] PB Series Funds.pdf
[MFR FEB26] Public Series of Shariah-Based Funds.pdf
[MFR FEB26] Public e-Series Funds.pdf
```

The script auto-discovers the newest MFR per series from filenames (`[MFR MONYY]` prefix).
PRS files are automatically excluded.

**Before running:** Confirm the MFR PDFs are in `Unit Trust (UT)/`. If the user says "new
MFR is out" but hasn't placed the files, ask them to drop the PDFs in first.

```bash
python3 fund-screener-skill/scripts/extract_mfr.py
```

Expected: `mfr_results.json` with ~171 funds.

---

## Step 1.5: Relabel low-confidence classifications (Claude Code, in-session — no script)

`extract_mfr.py` classifies four fields with keyword matching, which silently defaults hard cases.
After Step 1, Claude (not a script) relabels ONLY the funds the keyword classifier punted on. No API
key, no console spend — this runs in the skill session under the Max plan.

**Relabel a field only when its value is low-confidence:**

| Field | Relabel when… |
|---|---|
| `asset_class` | `== "Other"` |
| `objective_class` | `== ""` |
| `phs_fund_type` | `== ""` |
| `geography` | `== "Malaysia"` AND `lipper_class` names a foreign region AND carries no domestic marker (predicate below) |

> **Geography predicate (important):** a fund is a foreign-default only when its lowercased `lipper_class`
> (a) is non-empty, (b) contains **none** of the domestic markers `malaysia` / `myr` / `domestic`, and
> (c) contains at least one foreign-region token (`asia`, `china`, `global`, `asean`, `pacific`, `india`,
> `indonesia`, `japan`, `australia`, `vietnam`, `singapore`, `europe`, `emerging`, `far east`,
> `united states`). `Bond MYR` and `Mixed Asset MYR Domestic` are **Malaysian** (the "MYR"/"Domestic"
> marker is the home signal) — never relabel them. `Consistent` (a Lipper performance tag, not a region)
> and `Commodity Precious Fund-of-Funds` (gold) name no region — leave them. Funds with an **empty**
> lipper but clearly-foreign `geo_breakdown`/`objective_text` (e.g. the Islamic ESG funds) may still be
> relabeled by judgment, but the test does not require it.

**For each flagged fund:** read its `name`, `lipper_class`, `objective_text` (already in `mfr_results.json`),
choose the corrected value from the bounded enum below, write it back, and add a sibling
`"<field>_source": "llm-relabel"`.

**Bounded enums (choose only these values):**
- `asset_class`: Equity - Malaysia · Equity - Foreign · Bond / Fixed Income · Bond / Sukuk · Mixed Asset · Balanced · Money Market
- `geography`: Malaysia · Greater China · ASEAN · Asia Pacific · Asia · Global · United States · India · Indonesia · Japan · Australia · Vietnam · Singapore
- `objective_class`: Capital Growth · Income · Capital Growth + Income
- `phs_fund_type`: Equity · Fixed Income · Mixed Asset / Balanced · Money Market · Fund of Funds  (one combined value — NOT split, unlike asset_class)

**Rules:**
- NEVER modify `performance`, `ytd`, `weighted_alpha`, `asset_allocation`, `top5_holdings`, `top5_sectors`,
  or any other field. Numbers and holdings are deterministic and authoritative.
- If no enum fits (e.g. a gold/commodity fund), leave the original value and do NOT set `_source`.
- If `objective_text` is empty and the objective can't be resolved, leave it and do NOT set `_source`.
- Never invent an out-of-enum value.

**Verify:** run `pytest tests/test_relabel.py -v` — it must pass.

---

## Step 2: Fetch ATH NAV → ath_results.json + fund_code_map.json

```bash
python3 fund-screener-skill/scripts/fetch_ath.py --cold    # first time: full NAV history, ~2 min
python3 fund-screener-skill/scripts/fetch_ath.py           # monthly: incremental warm run, ~30s
python3 fund-screener-skill/scripts/fetch_ath.py --refresh-codes   # force-refresh the code map
```

The script handles CSRF tokens, session management, and delta caching automatically.
`fund_code_map.json` is persistent — reuse it every month (warm runs are ~145x faster than cold).

Expected output:
```
ath_results.json  (171 funds)
fund_code_map.json  (190 entries)
```

---

## Step 3: Build master CSV → master_funds.csv

```bash
python3 fund-screener-skill/scripts/build_sheet_data.py
```

Expected:
```
Written 171 funds to .../master_funds.csv
  Qualified: 111 | Disqualified: 60
  Risk Level coverage: 171/171
```

---

## Step 4: Build Excel workbook

The output filename is set in `build_xlsx.py` (`OUT_PATH`). Update the month in the filename
at the start of each new month's run.

```bash
python3 fund-screener-skill/scripts/build_xlsx.py
```

Expected:
```
Output: PublicMutual_FundMaster_[Month][Year]_v[skill-version].xlsx
ATH data loaded: 171 funds
Saved: .../output/fundmasters/PublicMutual_FundMaster_[Month][Year]_v[skill-version].xlsx
Sheets: ['Master', 'Summary']
Columns: 73
Data rows: 171 (qualified: ~110, disqualified: ~61)
```

---

## What the scripts extract per fund

| Data | Source | Method |
|---|---|---|
| Fund name, abbreviation | MFR page header | Regex with 3 patterns (standard, e-Series, Islamic e-Series) |
| Annualised returns (YTD, 1Y, 3Y, 5Y, 10Y) | MFR performance table | Row-by-row regex |
| Fund size, launch date, VF | MFR left column metadata | Regex |
| Distribution policy | MFR left column | Regex + noise stripping |
| Asset allocation | MFR left column (x < 310px) | Coordinate-based |
| Top 5 Holdings | MFR right column (x > midpoint) | Coordinate-based |
| Geo breakdown | MFR right column | KNOWN_COUNTRIES whitelist |
| Volatility Class | Derived from VF | SC banding: Very Low ≤4.245, Low ≤7.795, Moderate ≤10.235, High ≤13.595, Very High >13.595 |
| Fund Objective | PHS PDF (page 0) | Keyword classification (asset class, geography, objective, PHS fund type) — refined in Step 1.5 |
| Risk Level | funds_risk_level.xlsx | Lookup by abbreviation |
| Lipper Class, Benchmark | MFR left column | Regex |
| ATH NAV, ATH Date | publicmutual.com.my | Full NAV history → max(Nav) |
| Current NAV, Drawdown % | publicmutual.com.my | Bulk date endpoint + ATH delta |

### Known edge cases

- **Abbreviations with spaces**: `P ITTIKAL`, `PI BOND`, `P BOND`, `P SmallCap`, `PI INCOME`
  all appear this way in the MFR. PHS lookup strips spaces for filename matching.
- **API code map casing mismatch**: The API code map uses uppercase/joined keys (`PSMALLCAP`,
  `PeSUKUK`) while the MFR abbreviation may differ (`P SmallCap`, `PeSukuk`). The script
  handles normalization automatically; force a code map refresh with `--refresh-codes` if a
  fund is missing.
- **New funds without VF**: Launched within ~1 year — empty VF/VC is correct.
- **New funds ATH**: ATH = current NAV, drawdown = 0% — correct for brand-new funds.

---

## Excel output structure (73 columns)

### Sheet 1: Master

| Band | Cols | Contents | Color |
|---|---|---|---|
| FUND DETAILS | 1–9 | Name, Abbr, Shariah-compliant, Type, Objective, Risk Level, Distribution, Size, Launch | Dark Grey |
| SCREENING | 10–14 | Status, Beat %, Periods, Rationale, **Weighted Alpha (%)** | Red |
| ANNUALISED RETURNS | 15–29 | YTD/1Y/3Y/5Y/10Y × (Fund, Bench, Alpha) | Blue |
| ALPHA EFFICIENCY | 30–34 | Alpha/VF per period (formula column) | Dark Blue |
| ASSET ALLOCATION | 35–40 | Dom. Equity, For. Equity, FI/Sukuk, Money Mkt, Deposits, Other | Brown |
| GEO BREAKDOWN | 41–52 | 11 countries + Other | Green |
| SECTOR BREAKDOWN | 53–63 | 10 sectors + Other | Dark Teal |
| TOP 5 | 64 | Top 5 Holdings | Purple |
| META | 65–68 | VF, VC, Lipper Class, Benchmark | Grey |
| **ATH MOMENTUM** | **69–73** | **ATH NAV, ATH Date, Cur NAV, Drawdown (%), Days from ATH** | **Steel Blue** |

Conditional formatting:
- **Weighted Alpha**: green positive, red negative
- **Drawdown %**: ColorScaleRule — green (0%) → yellow (−10%) → red (−60%)
- Status: green/red fill for Qualified/Disqualified
- Risk Level: color scale 1→3→5 (green/yellow/red)
- Alpha columns: green positive, red negative

### Sheet 2: Summary

Formula-driven — references Master sheet so edits auto-propagate.
Median stats, Top-N tables, and fund type breakdowns all use FILTER/SORTBY/MEDIAN formulas.

---

## Sanity checks

| Check | Expected |
|---|---|
| mfr_results.json — total funds | ~171 (4 MFR series) |
| mfr_results.json — asset_class == "Other" | ~0 after Step 1.5 (gold/commodity funds excepted) |
| Qualified count | ~110 at weighted alpha > 0% threshold |
| Risk Level coverage | 171/171 |
| ath_results.json — total_processed | 171 |
| ath_results.json — errors | 0 |
| ath_results.json — drawdown range | All values ≤ 0 (positive = data error) |
| fund_code_map.json — count | ~190 |
| Excel — columns | 73 |
| Excel — ATH coverage | 171/171 |

---

## Troubleshooting

### fetch_ath.py — fund missing from code map (scheme_code null/undefined)
- Cause: Casing mismatch between MFR abbr and API key
  - MFR writes `P SmallCap` → API map key is `PSMALLCAP`
  - MFR writes `PeSukuk` → API map key is `PeSUKUK`
- Fix: Run `python3 fund-screener-skill/scripts/fetch_ath.py --refresh-codes` to force a fresh
  code map pull

### fetch_ath.py — connection error / timeout
- Cause: Network issue or publicmutual.com.my is temporarily down
- Fix: Retry after a few minutes. The script is safe to re-run — warm runs pick up from cache.

### build_xlsx.py — wrong month in output filename
- The filename is set in `OUT_PATH` near the top of `build_xlsx.py`. Update it each month.

### extract_mfr.py — fund count lower than expected
- Cause: New MFR series added, or PDF not yet placed in `Unit Trust (UT)/`
- Fix: Confirm all 4 series PDFs are present for the target month

---

## Generated cache files (Funds folder)

| File | Contents | Persistence |
|---|---|---|
| `fund_code_map.json` | `{fetched, count:190, codes:{abbr→FundCode}}` | Persistent — reuse every month |
| `ath_results.json` | `{generated, total_processed:171, successful, errors, funds[], error_list[]}` | Updated every run |
| `mfr_results.json` | Raw MFR extraction output | Updated every run |
| `master_funds.csv` | Merged flat data for all funds | Updated every run |

---

## Scripts in this bundle

| Script | Purpose |
|---|---|
| `fund-screener-skill/scripts/extract_mfr.py` | Step 1 — parse MFR PDFs, produce mfr_results.json |
| `fund-screener-skill/scripts/fetch_ath.py` | Step 2 — Python ATH fetcher with cold/warm modes |
| `fund-screener-skill/scripts/build_sheet_data.py` | Step 3 — merge MFR + ATH into master_funds.csv |
| `fund-screener-skill/scripts/build_xlsx.py` | Step 4 — build formatted Excel workbook (73 cols) |

---

## API endpoints reference

No login required — only a CSRF token extracted from the page HTML.

```
CSRF: document.querySelector('input[name="__RequestVerificationToken"]').value

GET  /FundExplorerList/GetFundExplorerData?date={YYYY-MM-DD}
     → all UT funds with FundCode, abbreviation → builds fund_code_map.json

POST /FundOverview/GetFundPerformanceChartData
     Body: { SchemeCode, StartDate, EndDate, IndexCode }
     → [{Date, Nav}] time series for one fund → ATH computation

GET  /FundPriceUT/GetAllUTFundPriceByDate?date={YYYY-MM-DD}
     → bulk current NAV for all ~190 UT funds (one API call)
```

---

## Google Sheets import

Open Google Drive → drag the .xlsx file in → right-click → "Open with Google Sheets".
All formatting, filters, and conditional formatting carry over automatically.

---

## Changelog

| Version | Date | Type | Summary |
|---------|------|------|---------|
| 1.5 | 2026-06-14 | Feature | Step 1.5: in-session LLM relabel of low-confidence classifications (asset_class/geography/objective_class/phs_fund_type), guarded by tests/test_relabel.py |
| 1.4 | 2026-05-06 | Bugfix | Fix asset-allocation parser misattributing Domestic/Foreign equity split for Shariah funds whose MFR layout places the `- Domestic` / `- Foreign` sub-qualifier on a separate line below the percentage row (e.g. PeIGRF, PBIEF, PBISCF, PeMZSF) |
| 1.3 | 2026-04-17 | Refactor | Organize output files into output/fundmasters/ directory and update build_xlsx.py to target this new location |
| 1.2 | 2026-04-15 | Feature | Auto-derive output filename, sheet titles, and footer from MFR month/year (parsed from mfr_results.json) and skill version (parsed from SKILL.md frontmatter) — no manual hardcoding required each month; generated date also dynamic |
| 1.1 | 2026-04-06 | Major | Replace binary 60% beat rate with weighted alpha scoring (YTD 5%, 1Y 15%, 3Y 40%, 5Y 25%, 10Y 15%); qualify if weighted alpha > 0; add Weighted Alpha (%) column (col 14); v7→v8 layout (72→73 cols) |
| 1.0 | 2026-04-06 | — | Initial versioned release |

---
name: fund-screener
description: >
  Bulk-screen all Public Mutual unit trust funds from Monthly Fund Report (MFR) PDFs and
  produce a fund master list as a formatted Excel file (importable to Google Sheets).
  Applies the 5-Point Code Review framework: filters for funds that beat their benchmark
  in at least 60% of available return periods (YTD, 1Y, 3Y, 5Y, 10Y). Also computes
  All-Time High (ATH) NAV and drawdown from ATH for every fund using an incremental cache.
  Use this skill whenever the user says things like: "screen the new MFR", "update the fund
  qualification list", "which funds qualify this month", "run the fund screener", "update with
  the March/April/[month] MFR", "new monthly report is out — re-run the analysis", or any
  request to produce or refresh a qualified funds shortlist from Public Mutual MFR data.
  Also trigger when the user wants to compare qualified funds across months, filter by
  asset class (equity, bond, Shariah), check ATH drawdown, or update the Google Sheet / Excel output.
  Even if the user just drops new MFR PDFs into the folder and says "these are out" or
  "new reports", use this skill to re-run the screening.
---

# Public Mutual Fund Screener (v6)

You are running a monthly fund-qualification pipeline for a Public Mutual unit trust consultant.
The pipeline reads MFR PDFs, fetches All-Time High NAV from the Public Mutual website, scores
every fund against its benchmark, and outputs a formatted Excel workbook with a Master sheet
(all funds) and a Summary dashboard.

## How the screening works

**Qualification rule:** A fund qualifies if it beats its benchmark in at least 60% of available
return periods. The periods assessed are: YTD, 1Y, 3Y, 5Y, 10Y. Minimum 2 periods of data
required.

**Why these periods?**
- YTD captures very recent momentum and direction
- 1Y shows current-year performance
- 3Y reveals the current team's track record
- 5Y smooths through market cycles
- 10Y shows long-term structural edge

A 60% threshold (e.g., 3/5 periods) is strict enough to filter noise but realistic enough to
catch strong consistent performers. Including YTD gives the screening a forward-looking tilt
that pure annualised periods miss.

## Pipeline overview

The screener runs in 4 steps:

1. **extract_mfr.py** — reads all MFR PDFs, extracts fund data, scores, saves `mfr_results.json`
2. **fetch_ath.py** — fetches ATH NAV from Public Mutual website, saves `ath_results.json`
3. **build_sheet_data.py** — merges MFR + ATH data into structured CSV with Status + Risk Level
4. **build_xlsx.py** — builds the formatted Excel workbook from CSV

Each script is bundled in `scripts/`. They are designed to be run sequentially.

**Step 2 is optional but recommended.** If `ath_results.json` is absent, the pipeline runs
without ATH columns. If present, the ATH columns are automatically included in the Excel output.

## Step 1: Locate the MFR Files

MFR files live in the user's workspace folder under `Unit Trust (UT)/`. They are named like:
```
[MFR FEB26] Public Series Funds.pdf
[MFR FEB26] PB Series Funds.pdf
[MFR FEB26] Public Series of Shariah-Based Funds.pdf
[MFR FEB26] Public e-Series Funds.pdf
```

The extraction script auto-discovers the latest MFR files by parsing the `[MFR MONYY]` date
from filenames and keeping only the newest per series. So if both FEB26 and MAR26 exist for
the same series, it picks MAR26. PRS files are automatically excluded.

**Before running:** Confirm the MFR PDFs are in the `Unit Trust (UT)/` folder. If the user
says "new MFR is out" but hasn't placed the files yet, ask them to drop the PDFs into the folder.

## Step 2: Configure paths and run

The scripts need these path configurations:

1. **BASE_DIR** (extract_mfr.py) — path to the `Unit Trust (UT)/` folder
2. **PHS_DIR** (extract_mfr.py) — path to the `Product Highlight Sheet (PHS)/` subfolder
3. **RISK_LEVEL_FILE** — **auto-detected**. Looks for `funds_risk_level.xlsx` in the Funds
   folder (parent of BASE_DIR). Must exist at all times — it is the definitive 1-5 risk scale.
4. **fetch_ath.py** — **fully auto-configured**. Uses `os.path.dirname(dirname(__file__))`
   to resolve the parent Funds folder regardless of where `scripts/` is placed.
   No path edits needed.

Open `scripts/extract_mfr.py` and update `BASE_DIR` and `PHS_DIR`. Open `scripts/build_sheet_data.py`
and update only `WORK_DIR`. Then run all 4 scripts in order:

```bash
# Step 1: Extract all fund data from MFR PDFs
python3 scripts/extract_mfr.py

# Step 2: Fetch All-Time High NAV (two modes — see ATH section below)
python3 scripts/fetch_ath.py           # warm run (incremental, ~30s)
python3 scripts/fetch_ath.py --cold    # cold run (full history, ~2 min) — first time only

# Step 3: Build master CSV (all funds with Status, Risk Level, ATH data)
python3 scripts/build_sheet_data.py

# Step 4: Build the Excel workbook
python3 scripts/build_xlsx.py
```

## Step 3: ATH Fetching — Two-Mode Operation

`fetch_ath.py` uses the Public Mutual website's internal API (no login required):

```
POST /FundOverview/GetFundPerformanceChartData
Body: { SchemeCode, StartDate, EndDate, IndexCode }
```

### Cold run (first time, or --cold flag)
Fetches full NAV history from fund inception for every fund. PIATAF (launched Dec 2011)
returns ~3,200 data points. Typical runtime: ~2 minutes for 171 funds.

### Warm run (every month after, default)
Three optimisations make this ~5× faster:

1. **Fund code map cached** — `fund_code_map.json` stores the `abbr → FundCode` mapping
   fetched from `GetFundExplorerData`. Reused on every warm run. Auto-refreshes only when
   a fund from `mfr_results.json` is missing from the cached map (handles new fund launches).
   Force-refresh: `python3 scripts/fetch_ath.py --refresh-codes`

2. **Bulk current NAV — 1 call for all funds** — `GetAllUTFundPriceByDate` returns today's
   NAV for all ~190 funds in a single request. No per-fund current-NAV call needed.

3. **Delta-only history per fund** — fetches only from `last_checked + 1 day` to today.
   PIATAF: 3,200 points (cold) → ~22 points (monthly warm). ~145× less data per fund.

### ATH cache files produced
| File | Contents | Frequency |
|---|---|---|
| `fund_code_map.json` | `{ abbr: FundCode }` for all UT funds | Once, auto-refresh on new fund |
| `ath_results.json` | ATH NAV, ATH Date, Current NAV, Drawdown %, Days from ATH | Updated every run |

### Warm run command cheatsheet
```bash
python3 scripts/fetch_ath.py                    # standard monthly warm run
python3 scripts/fetch_ath.py --cold             # rebuild ATH from scratch (keep code map)
python3 scripts/fetch_ath.py --refresh-codes    # refresh fund code map, then warm run
python3 scripts/fetch_ath.py --cold --refresh-codes   # full reset of everything
```

## Step 4: What the scripts extract per fund

The extraction is coordinate-based (using pdfplumber word-level coordinates) to handle the
multi-column layout of MFR pages. Here's what gets extracted:

| Data | Source | Method |
|---|---|---|
| Fund name, abbreviation | Page header | Regex with 3 patterns (standard, e-Series, Islamic e-Series) |
| Annualised returns (YTD, 1Y, 3Y, 5Y, 10Y) | Performance table | Row-by-row regex parsing |
| Fund size, launch date, VF | Left column metadata | Regex |
| Distribution policy | Left column | Regex + noise stripping |
| Asset allocation | Left column (x < 310px) | Coordinate-based extraction |
| Top 5 Holdings | Right column (x > midpoint) | Coordinate-based extraction |
| Geographical breakdown | Right column | KNOWN_COUNTRIES whitelist filter |
| Volatility Class | Derived from VF | SC banding: Very Low ≤4.245, Low ≤7.795, Moderate ≤10.235, High ≤13.595, Very High >13.595 |
| Fund Objective | PHS PDF (page 0) | Keyword classification → Capital Growth / Income / Capital Growth + Income |
| Risk Level | funds_risk_level.xlsx | Lookup by abbreviation (Public Mutual defined, 1-5 scale) |
| Lipper Class, Benchmark | Left column (MFR) | Regex |
| ATH NAV, ATH Date | publicmutual.com.my API | Full NAV history → max(Nav) |
| Current NAV, Drawdown % | publicmutual.com.my API | Bulk date endpoint + ATH delta |

### Known extraction patterns

- **EPF suffix in headers**: Fund headers may end with `EPFQualified Fund`, `EPFQualifiedFund`, or just `EPF`. The regex handles all variants.
- **e-Series headers**: Use mixed case like `PUBLIC e-AVANTGARDE FOCUS FUND (PeAGFF)`. Detected by separate regex pattern.
- **Abbreviations with spaces**: Some funds have spaces in their abbreviation (e.g., `P ITTIKAL`, `PI BOND`). PHS lookup strips spaces for filename matching.
- **New funds without VF**: Funds launched within ~1 year may not have a Volatility Factor assigned yet. These will have empty VF/VC — that's correct, not a bug.
- **New funds ATH**: Very new funds will have ATH = current NAV and 0% drawdown — correct behaviour.

## Step 5: Excel output structure

The workbook has 2 sheets with 72 columns on the Master tab (67 in v5 + 5 ATH columns):

### Sheet 1: Master (all funds — qualified + disqualified)
All funds are shown together with a Status column (Qualified/Disqualified). Qualified funds
appear first, sorted by fund type, beat rate, and 3Y alpha. Disqualified funds appear after,
rendered in greyed-out text.

Grouped into 8 column bands:

| Band | Columns | Color |
|---|---|---|
| FUND DETAILS | Fund Name, Abbr, Series, Fund Type, Geography, Status, Objective, Risk Level, Distribution, Size, Launch | Dark Grey |
| SCREENING | Beat %, Periods | Red |
| RETURNS | YTD/1Y/3Y/5Y/10Y × (Fund, Bench, Alpha) = 15 cols | Blue |
| ASSET ALLOCATION | Dom. Equity, For. Equity, FI/Sukuk, Money Mkt, Deposits, Other | Brown |
| GEO BREAKDOWN | USA, Taiwan, Korea, Japan, France, Germany, China, Singapore, Netherlands, Indonesia, Australia, Other | Green |
| TOP 5 | Holdings | Purple |
| ATH / MOMENTUM | ATH NAV, ATH Date, Current NAV, Drawdown from ATH (%), Days from ATH | Orange |
| META | VF, VC, Lipper Class, Benchmark | Grey |

Conditional formatting (new in v6):
- **Drawdown from ATH**: color scale from green (0%) through yellow (-15%) to red (-30%+)
- **Days from ATH**: highlight in amber when > 180 days (fund has been off its peak for 6+ months)
- All v5 formatting retained (Status, Risk Level, Alpha columns, Beat %, Allocation, Geo)

**Percentage handling:** All percentage columns store raw numbers (e.g., 12.34 means 12.34%)
with plain number format ("0.00"). Column headers include "(%) " suffix.

### Sheet 2: Summary
- Screening stats (total screened, qualified, pass rate, Shariah/Conventional split)
- Breakdown by fund type
- Top 15 Equity funds by 3Y Alpha (qualified only)
- Mixed Asset funds by 3Y Alpha (qualified only)
- Bond/Fixed Income qualified funds
- **New in v6**: ATH Momentum section — funds near ATH (drawdown ≥ -5%) and
  funds with deepest drawdown (potential recovery candidates)

**Formula-driven:** The Summary sheet uses live Excel formulas referencing the Master sheet.
Median statistics, Top-N tables, and ATH breakdowns all auto-update if Master data is edited.

### Data standardization applied:
- **Distribution Policy**: Standardized to: Annual, Monthly, Semi-Annual, Incidental, None
- **Asset Allocation**: 14 raw MFR categories → 6 columns (Shariah variants merged into parent)
- **Geo Breakdown**: Named columns for 11 major markets + "Geo Other" bucket
- **Risk Level**: From Public Mutual official fund risk classification (1=Low to 5=High)
- **ATH Drawdown**: Negative value = below ATH; 0% = at ATH; positive not possible by definition

## Step 6: Sanity checks

Before presenting results, verify:

| Check | Expected |
|---|---|
| Total funds in Master | ~160-170 (across 4 MFR series) |
| Qualified count | Typically 100-120 at 60% threshold |
| All 4 MFR series processed | Check log output for each file |
| PHS Obj coverage | Should be 160+/166 (a few very new funds may miss) |
| Risk Level coverage | Should be ~160+/170 (most funds mapped) |
| Holdings coverage | ~159/166 |
| ATH coverage | Should match total funds (all have NAV history) |
| ATH drawdown range | Typically -30% to 0%; any positive value is a data error |
| fund_code_map.json | Should contain ~190 entries; auto-refreshes if a fund is missing |

If a fund the user expects to see is missing, common causes:
1. EPF suffix not matching — check the header regex
2. Fund header on an unexpected line — check raw page text with pdfplumber
3. File not discovered — check if filename follows `[MFR MONYY]` pattern
4. Fund abbreviation not in fund_code_map.json — run `python3 scripts/fetch_ath.py --refresh-codes`

## Step 7: Present the output

Name the file `PublicMutual_FundMaster_[Month][Year].xlsx` and provide a computer:// link.

Summary format:
```
Screened [N] funds from [Month] MFR.
[X] qualified (≥60% benchmark outperformance incl. YTD) | [Y] disqualified

Top equity picks by 3Y alpha:
- [Fund 1] (Abbr): +X.X% alpha | ATH drawdown: -X.X%
- [Fund 2] (Abbr): +X.X% alpha | ATH drawdown: -X.X%
- [Fund 3] (Abbr): +X.X% alpha | ATH drawdown: -X.X%

Fund type breakdown: [N] Equity MY | [N] Equity Foreign | [N] Mixed Asset | [N] Bond | ...
Shariah: [N] | Conventional: [N]

ATH Momentum snapshot:
- Funds at/near ATH (≤ -5% drawdown): [N]
- Funds in moderate drawdown (-5% to -20%): [N]
- Funds in deep drawdown (> -20%): [N]
- Median drawdown across all funds: -X.X%
```

## Monthly update workflow

When a new MFR arrives (~2-3 weeks after month end):

1. User places new MFR PDFs in the `Unit Trust (UT)/` folder
2. Run `python3 scripts/extract_mfr.py` → produces `mfr_results.json`
3. Run `python3 scripts/fetch_ath.py` (warm run — uses cached code map, fetches only new NAV data)
4. Run `python3 scripts/build_sheet_data.py`
5. Run `python3 scripts/build_xlsx.py`
6. Save the new xlsx as `PublicMutual_FundMaster_[Month][Year].xlsx`

Old files are never overwritten — keep monthly history for comparison.
The script auto-selects the newest MFR per series, so old PDFs can coexist in the folder.

**First-time setup only:**
```bash
pip install requests pdfplumber openpyxl --break-system-packages
python3 scripts/fetch_ath.py --cold    # build ATH cache from scratch (~2 min)
```

## Google Sheets import

Tell the user: "To get this into Google Sheets: open Google Drive → drag the .xlsx file in →
right-click → 'Open with Google Sheets'. All formatting, filters, and conditional formatting
carry over automatically."

## Reference: 5-Point Code Review Framework

See `references/framework.md` for the full framework with engineering analogies.
The screener primarily uses Checkpoint 3 (Returns vs Benchmark) as its filter, enriched with
data from Checkpoints 1-2 (fund identity, details), Checkpoint 4 (portfolio composition),
and now ATH momentum data as an additional dimension for Checkpoint 3 analysis.

## Scripts in this bundle

| Script | Location | Purpose |
|---|---|---|
| `extract_mfr.py` | `scripts/` | Step 1 — parse MFR PDFs, produce mfr_results.json |
| `fetch_ath.py` | `scripts/` | Step 2 — fetch ATH NAV from Public Mutual API, produce ath_results.json |
| `build_sheet_data.py` | `scripts/` | Step 3 — merge MFR + ATH into master_funds.csv |
| `build_xlsx.py` | `scripts/` | Step 4 — build formatted Excel workbook |
| `fund_code_map.json` | root (generated) | Cached abbr→FundCode mapping |
| `ath_results.json` | root (generated) | Cached ATH NAV + drawdown per fund |
| `mfr_results.json` | root (generated) | Raw MFR extraction output |

## Changelog

| Version | Changes |
|---|---|
| v6 | Added fetch_ath.py (Step 2): ATH NAV + drawdown from Public Mutual API. Two-mode caching (cold/warm). Fund code map cache. ATH MOMENTUM column band in Excel. Summary ATH section. |
| v5 | Formula-driven Summary sheet. Percentage handling standardised to raw numbers. |
| v4 | Coordinate-based asset allocation extraction. Geo breakdown. |
| v3 | PHS objective classification. Risk Level from funds_risk_level.xlsx. |
| v2 | e-Series header detection. Top 5 Holdings extraction. |
| v1 | Initial MFR extraction, benchmark scoring, Excel output. |

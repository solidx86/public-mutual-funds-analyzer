---
name: fund-screener
description: >
  Bulk-screen all Public Mutual unit trust funds from Monthly Fund Report (MFR) PDFs and
  produce a fund master list as a formatted Excel file (importable to Google Sheets).
  Applies the 5-Point Code Review framework: filters for funds that beat their benchmark
  in at least 60% of available return periods (YTD, 1Y, 3Y, 5Y, 10Y).
  Use this skill whenever the user says things like: "screen the new MFR", "update the fund
  qualification list", "which funds qualify this month", "run the fund screener", "update with
  the March/April/[month] MFR", "new monthly report is out — re-run the analysis", or any
  request to produce or refresh a qualified funds shortlist from Public Mutual MFR data.
  Also trigger when the user wants to compare qualified funds across months, filter by
  asset class (equity, bond, Shariah), or update the Google Sheet / Excel output.
  Even if the user just drops new MFR PDFs into the folder and says "these are out" or
  "new reports", use this skill to re-run the screening.
---

# Public Mutual Fund Screener (v5)

You are running a monthly fund-qualification pipeline for a Public Mutual unit trust consultant.
The pipeline reads MFR PDFs, scores every fund against its benchmark, and outputs a formatted
Excel workbook with a Master sheet (all funds) and a Summary dashboard.

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

The screener runs in 3 steps:

1. **extract_mfr.py** — reads all MFR PDFs, extracts fund data, scores, saves `mfr_results.json`
2. **build_sheet_data.py** — transforms JSON into structured CSV (all funds with Status + Risk Level)
3. **build_xlsx.py** — builds the formatted Excel workbook from CSV

Each script is bundled in `scripts/`. They are designed to be run sequentially.

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

1. **BASE_DIR** — path to the `Unit Trust (UT)/` folder (where MFR PDFs live)
2. **PHS_DIR** — path to the `Product Highlight Sheet (PHS)/` subfolder (for fund objective classification)
3. **RISK_LEVEL_FILE** — **auto-detected**. No manual setting needed. The script looks for
   `funds_risk_level.xlsx` in the Funds folder (parent of BASE_DIR). This file must exist in
   the Funds folder at all times — it is the definitive Public Mutual 1-5 risk scale reference.
   Only set RISK_LEVEL_FILE explicitly if the file lives in a non-standard location.

Open `scripts/extract_mfr.py` and update `BASE_DIR` and `PHS_DIR`. Open `scripts/build_sheet_data.py`
and update only `WORK_DIR` (RISK_LEVEL_FILE auto-derives from the JSON output). Then run:

```bash
# Step 1: Extract all fund data from MFR PDFs
python3 [skill-path]/scripts/extract_mfr.py

# Step 2: Build master CSV (all funds with Status + Risk Level)
python3 [skill-path]/scripts/build_sheet_data.py

# Step 3: Build the Excel workbook
python3 [skill-path]/scripts/build_xlsx.py
```

Alternatively, you can copy the scripts to the working directory and run from there. The
scripts use hardcoded paths internally — update them to match the current session's paths.

## Step 3: What the scripts extract per fund

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
| Top 5 Sectors | Right column | Heading trigger: "Top 5 Sectors" OR standalone "Sectors" |
| Geographical breakdown | Right column | KNOWN_COUNTRIES whitelist filter |
| Volatility Class | Derived from VF | SC banding: Very Low ≤4.245, Low ≤7.795, Moderate ≤10.235, High ≤13.595, Very High >13.595 |
| Fund Objective | PHS PDF (page 0) | Keyword classification → Capital Growth / Income / Capital Growth + Income |
| Risk Level | funds_risk_level.xlsx | Lookup by abbreviation (Public Mutual defined, 1-5 scale) |
| Lipper Class, Benchmark | Left column (MFR) | Regex |

### Known extraction patterns

- **EPF suffix in headers**: Fund headers may end with `EPFQualified Fund`, `EPFQualifiedFund`, or just `EPF`. The regex handles all variants.
- **e-Series headers**: Use mixed case like `PUBLIC e-AVANTGARDE FOCUS FUND (PeAGFF)`. Detected by separate regex pattern.
- **Abbreviations with spaces**: Some funds have spaces in their abbreviation (e.g., `P ITTIKAL`, `PI BOND`). PHS lookup strips spaces for filename matching.
- **New funds without VF**: Funds launched within ~1 year may not have a Volatility Factor assigned yet. These will have empty VF/VC — that's correct, not a bug.

## Step 4: Excel output structure

The workbook has 2 sheets with 67 columns on the Master tab:

### Sheet 1: Master (all funds — qualified + disqualified)
All funds are shown together with a Status column (Qualified/Disqualified). Qualified funds
appear first, sorted by fund type, beat rate, and 3Y alpha. Disqualified funds appear after,
rendered in greyed-out text.

Grouped into 7 column bands:

| Band | Columns | Color |
|---|---|---|
| FUND DETAILS | Fund Name, Abbr, Series, Fund Type, Geography, Status, Objective, Risk Level, Distribution, Size, Launch | Dark Grey |
| SCREENING | Beat (%), Periods | Red |
| RETURNS | YTD/1Y/3Y/5Y/10Y × (Fund, Bench, Alpha) = 15 cols (all raw % values) | Blue |
| ALPHA EFFICIENCY | AE YTD, AE 1Y, AE 3Y, AE 5Y, AE 10Y | Cyan |
| ASSET ALLOCATION | Dom. Equity, For. Equity, FI/Sukuk, Money Mkt, Deposits, Other (all raw % values) | Brown |
| GEO BREAKDOWN | USA, Taiwan, Korea, Japan, France, Germany, China, Singapore, Netherlands, Indonesia, Australia, Other (all raw % values) | Green |
| TOP 5 | Holdings (Top 5 Sectors column removed) | Purple |
| META | VF, VC, Lipper Class, Benchmark | Columns 64-67 |

**v5 Changes:**
- **Top 5 Sectors column removed** — only Holdings text remains in the TOP 5 band (1 column instead of 2)
- **All percentage columns (RETURNS, ASSET ALLOCATION, GEO BREAKDOWN) now store raw values** — e.g., 12.5 instead of 12.50% with percentage formatting
- **New ALPHA EFFICIENCY band** — 5 columns (AE YTD/1Y/3Y/5Y/10Y) computed from formula Alpha/Volatility Factor
- **Summary sheet is now formula-driven** — uses MEDIAN(FILTER()), SORTBY(FILTER(INDEX())) for dynamic Top 5 tables per fund type instead of hardcoded values

Conditional formatting:
- Status: green for Qualified, red tint for Disqualified
- Risk Level: color scale 1 (green) → 3 (yellow) → 5 (red)
- Alpha columns: green fill for positive, red fill for negative
- Beat %: color scale from red (0%) through yellow (60%) to green (100%)
- Allocation columns: light yellow highlight when non-empty
- Geo columns: light green highlight when non-empty

### Sheet 2: Summary
- Screening stats (total screened, qualified, pass rate, Shariah/Conventional split)
- Breakdown by fund type
- Top 15 Equity funds by 3Y Alpha (qualified only)
- Mixed Asset funds by 3Y Alpha (qualified only)
- Bond/Fixed Income qualified funds

### Data standardization applied:
- **Distribution Policy**: Standardized to exactly one of: Annual, Monthly, Semi-Annual, Incidental, None
- **Asset Allocation**: 14 raw MFR categories consolidated into 6 columns (Shariah variants merged into parent, e.g. "Shariah-compliant equity - Domestic" → Domestic Equity)
- **Geo Breakdown**: Named columns for 11 major markets + "Geo Other" bucket
- **Risk Level**: From Public Mutual official fund risk classification (1=Low to 5=High)

## Step 5: Sanity checks

Before presenting results, verify:

| Check | Expected |
|---|---|
| Total funds in Master | ~160-170 (across 4 MFR series) |
| Qualified count | Typically 100-120 at 60% threshold |
| All 4 MFR series processed | Check log output for each file |
| PHS Obj coverage | Should be 160+/166 (a few very new funds may miss) |
| Risk Level coverage | Should be ~160+/170 (most funds mapped) |
| Sectors coverage | ~137/166 (bond/sukuk/money market genuinely don't have sectors) |
| Holdings coverage | ~159/166 |

If a fund the user expects to see is missing, common causes:
1. EPF suffix not matching — check the header regex
2. Fund header on an unexpected line — check raw page text with pdfplumber
3. File not discovered — check if filename follows `[MFR MONYY]` pattern

## Step 6: Present the output

Name the file `PublicMutual_FundMaster_[Month][Year].xlsx` and provide a computer:// link.

Summary format:
```
Screened [N] funds from [Month] MFR.
[X] qualified (≥60% benchmark outperformance incl. YTD) | [Y] disqualified

Top equity picks by 3Y alpha:
- [Fund 1] (Abbr): +X.X% alpha
- [Fund 2] (Abbr): +X.X% alpha
- [Fund 3] (Abbr): +X.X% alpha

Fund type breakdown: [N] Equity MY | [N] Equity Foreign | [N] Mixed Asset | [N] Bond | ...
Shariah: [N] | Conventional: [N]
```

## Monthly update workflow

When a new MFR arrives (~2-3 weeks after month end):

1. User places new MFR PDFs in the `Unit Trust (UT)/` folder
2. Update the `BASE_DIR` path in `extract_mfr.py` if needed
3. Run the 3 scripts in order
4. Save the new xlsx with the updated month in the filename
5. Old files are never overwritten — keep monthly history for comparison

The script auto-selects the newest MFR per series, so old month files can coexist in the folder.

## Google Sheets import

Tell the user: "To get this into Google Sheets: open Google Drive → drag the .xlsx file in →
right-click → 'Open with Google Sheets'. All formatting, filters, and conditional formatting
carry over automatically."

## Reference: 5-Point Code Review Framework

See `references/framework.md` for the full framework with engineering analogies.
The screener primarily uses Checkpoint 3 (Returns vs Benchmark) as its filter, enriched with
data from Checkpoints 1-2 (fund identity, details) and Checkpoint 4 (portfolio composition).

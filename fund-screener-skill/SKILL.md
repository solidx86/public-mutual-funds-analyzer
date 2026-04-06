---
name: fund-screener
description: >
  Bulk-screen all Public Mutual unit trust funds from Monthly Fund Report (MFR) PDFs and produce a fund master list as a formatted Excel file (importable to Google Sheets). Applies the 5-Point Code Review framework: filters for funds that beat their benchmark in at least 60% of available return periods (YTD, 1Y, 3Y, 5Y, 10Y). Use this skill whenever the user says things like: "screen the new MFR", "update the fund qualification list", "which funds qualify this month", "run the fund screener", "update with the [month] MFR", "new monthly report is out — re-run the analysis", or any request to produce or refresh a qualified funds shortlist from Public Mutual MFR data. Also trigger when the user wants to compare qualified funds across months, filter by asset class (equity, bond, Shariah), or update the Google Sheet / Excel output. If the user drops new MFR PDFs and says "these are out" or "new reports", use this skill.
---

# Public Mutual Fund Screener (v7)

You are running a monthly fund-qualification pipeline for a Public Mutual unit trust consultant.
The pipeline reads MFR PDFs, fetches All-Time High NAV from the Public Mutual website, scores
every fund against its benchmark, and outputs a formatted Excel workbook with a Master sheet
(all funds) and a Summary dashboard.

## ⚠️ Critical Environment Note: No Direct Internet in Sandbox

The Cowork/sandbox environment has **no direct internet access**. This means `fetch_ath.py`
(Step 2) **cannot be run directly from Python** — it will time out trying to reach
publicmutual.com.my. Instead, all Step 2 data must come from Claude in Chrome (browser
automation). Steps 1, 3, and 4 run normally in the sandbox.

If the user is running this locally (outside Cowork, on their own machine with internet),
`fetch_ath.py` works as written — use the direct Python path described in the ATH section.

---

## How the screening works

**Qualification rule:** A fund qualifies if it beats its benchmark in at least 60% of available
return periods. The periods assessed are: YTD, 1Y, 3Y, 5Y, 10Y. Minimum 2 periods required.

**Why these periods?**
- YTD captures very recent momentum and direction
- 1Y shows current-year performance
- 3Y reveals the current team's track record
- 5Y smooths through market cycles
- 10Y shows long-term structural edge

A 60% threshold (e.g., 3/5 periods) is strict enough to filter noise but realistic enough to
catch strong consistent performers. Including YTD gives the screening a forward-looking tilt
that pure annualised periods miss.

---

## Pipeline overview

| Step | Script | Runs where | Output |
|---|---|---|---|
| 1 | `extract_mfr.py` | Sandbox (Python) | `mfr_results.json` |
| 2 | `fetch_ath.py` or browser extraction | **Browser (Claude in Chrome)** | `ath_results.json` + `fund_code_map.json` |
| 3 | `build_sheet_data.py` | Sandbox (Python) | `master_funds.csv` |
| 4 | `build_xlsx.py` | Sandbox (Python) | `.xlsx` workbook |

**Step 2 is required for ATH columns.** If `ath_results.json` is absent, Steps 3–4 still
run but the ATH MOMENTUM band in the workbook will be empty.

---

## Step 1: Extract MFR PDFs → mfr_results.json

MFR files live in the workspace under `Unit Trust (UT)/`. Named like:
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

**Path configuration** — open `scripts/extract_mfr.py` and set:
- `BASE_DIR` → path to the `Unit Trust (UT)/` folder
- `PHS_DIR` → path to `Product Highlight Sheet (PHS)/`

```bash
python3 scripts/extract_mfr.py
```

Expected: `mfr_results.json` with ~171 funds.

---

## Step 2: Fetch ATH NAV → ath_results.json + fund_code_map.json

### Option A — Direct Python (local machine with internet)

```bash
python3 scripts/fetch_ath.py --cold    # first time: full NAV history, ~2 min
python3 scripts/fetch_ath.py           # monthly: incremental warm run, ~30s
python3 scripts/fetch_ath.py --refresh-codes   # force-refresh the code map
```

The script handles CSRF tokens, session management, and delta caching automatically.

### Option B — Browser-Assisted Extraction (Cowork / sandbox — the standard path)

Because the sandbox has no internet, Claude in Chrome does the API calls instead.
This is a 5-phase process:

#### Phase 1 — Check browser memory first (saves time)

Before doing any extraction, check whether the Fund Explorer tab already has data from
a prior run in this Cowork session. Data survives in browser memory as long as the tab
stays open:

```javascript
// Run on the Fund Explorer tab (publicmutual.com.my/fund-explorer-list)
typeof window.__csv_rows !== 'undefined'
  ? `rows=${window.__csv_rows.length}, codeMap=${Object.keys(window.__codeMap||{}).length}`
  : 'LOST - re-run Phase 2'
```

- `rows=171, codeMap=190` → skip to Phase 3 (data still live)
- `LOST` → continue to Phase 2

#### Phase 2 — Run the in-browser extraction script

Navigate to `https://www.publicmutual.com.my/fund-explorer-list` and run the full
extraction JavaScript (see `scripts/browser_extract.js`). The script:
1. Reads the CSRF token from the page: `document.querySelector('input[name="__RequestVerificationToken"]').value`
2. Calls `GET /FundExplorerList/GetFundExplorerData` → builds `window.__codeMap` (190 abbr→FundCode entries)
3. Calls `GET /FundPriceUT/GetAllUTFundPriceByDate` → bulk current NAVs (one call for all funds)
4. Calls `POST /FundOverview/GetFundPerformanceChartData` per fund → full NAV series → ATH
5. Stores results as `window.__csv_rows` (compact pipe-delimited strings, one per fund)

Runtime: ~2 minutes cold (first time) or ~30 seconds warm (code map already cached).

#### Phase 3 — Batch extract ATH rows from browser

The JS tool truncates output at ~1200 characters. Each CSV row is ~73 chars, so 12 rows
per batch (~876 chars) fits safely under the limit. Run these calls in sequence:

```javascript
window.__csv_rows.slice(0, 12).join('\n')
window.__csv_rows.slice(12, 24).join('\n')
window.__csv_rows.slice(24, 36).join('\n')
// ... continue in steps of 12 until all 171 rows extracted
window.__csv_rows.slice(168, 171).join('\n')   // final partial batch
```

Each row is 10 pipe-delimited fields:
```
abbr|scheme_code|ath_nav|ath_date|current_nav|current_date|drawdown_pct|days_from_ath|data_from|total_pts
```

Example:
```
PIATAF|39|0.9506|2026-02-26|0.884|2026-04-02|-7.01|39|2011-12-09|3212
PeAITF|170|0.507|2025-10-29|0.4106|2026-04-02|-19.01|159|2020-09-07|1304
```

**Why this format, not JSON?** The JS tool's character limit makes extracting 42KB of JSON
impossible in a single call. Compact pipe-CSV (no quotes, no braces, no whitespace) fits 12
records in ~876 chars. Base64, DOM injection, and blob URL approaches were all tried and
blocked by the browser security sandbox.

#### Phase 4 — Extract fund code map

Run 3 batches to pull all 190 entries (each batch ~80-90 entries, fits under limit):

```javascript
Object.entries(window.__codeMap).slice(0, 60).map(([k,v]) => `${k}=${v}`).join('|')
Object.entries(window.__codeMap).slice(60, 130).map(([k,v]) => `${k}=${v}`).join('|')
Object.entries(window.__codeMap).slice(130, 190).map(([k,v]) => `${k}=${v}`).join('|')
```

#### Phase 5 — Assemble JSON files via Python

Write `scripts/assemble_json.py` with all batch strings embedded as Python constants
(see template in `scripts/assemble_json.py`), then run:

```bash
python3 scripts/assemble_json.py
```

Expected output:
```
Code map entries: 190
Parsed: 171 funds, 0 errors
✓ Written: .../ath_results.json  (171 funds)
✓ Written: .../fund_code_map.json  (190 entries)
```

---

## Step 3: Build master CSV → master_funds.csv

Open `scripts/build_sheet_data.py`, set `WORK_DIR` to the Funds folder, then run:

```bash
python3 scripts/build_sheet_data.py
```

Expected:
```
Written 171 funds to .../master_funds.csv
  Qualified: 111 | Disqualified: 60
  Risk Level coverage: 171/171
```

---

## Step 4: Build Excel workbook

Open `scripts/build_xlsx.py` and update two hardcoded paths:
- `WORK_DIR` → Funds folder (same as Step 3)
- `OUT_PATH` → full path for the output xlsx (include month in filename)

**The `/sessions/` prefix changes every Cowork session.** Always update both paths at the
start of each new conversation — the most common cause of FileNotFoundError.

```bash
python3 scripts/build_xlsx.py
```

Expected:
```
ATH data loaded: 171 funds
Saved: .../PublicMutual_FundMaster_[Month][Year]_v7.xlsx
Sheets: ['Master', 'Summary']
Columns: 72
Data rows: 171 (qualified: 111, disqualified: 60)
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
| Fund Objective | PHS PDF (page 0) | Keyword classification |
| Risk Level | funds_risk_level.xlsx | Lookup by abbreviation |
| Lipper Class, Benchmark | MFR left column | Regex |
| ATH NAV, ATH Date | publicmutual.com.my | Full NAV history → max(Nav) |
| Current NAV, Drawdown % | publicmutual.com.my | Bulk date endpoint + ATH delta |

### Known edge cases

- **Abbreviations with spaces**: `P ITTIKAL`, `PI BOND`, `P BOND`, `P SmallCap`, `PI INCOME`
  all appear this way in the MFR. PHS lookup strips spaces for filename matching.
- **API code map casing mismatch**: The API code map uses uppercase/joined keys (`PSMALLCAP`,
  `PeSUKUK`) while the MFR abbreviation may differ (`P SmallCap`, `PeSukuk`). Look up
  directly by API key: `window.__codeMap['PSMALLCAP']`, not `window.__codeMap['P SmallCap']`.
- **New funds without VF**: Launched within ~1 year — empty VF/VC is correct.
- **New funds ATH**: ATH = current NAV, drawdown = 0% — correct for brand-new funds.

---

## Excel output structure (72 columns)

### Sheet 1: Master

| Band | Cols | Contents | Color |
|---|---|---|---|
| FUND DETAILS | 1–10 | Name, Abbr, Series, Type, Geography, Objective, Risk Level, Distribution, Size, Launch | Dark Grey |
| SCREENING | 11–13 | Status, Beat %, Periods | Red |
| ANNUALISED RETURNS | 14–28 | YTD/1Y/3Y/5Y/10Y × (Fund, Bench, Alpha) | Blue |
| ALPHA EFFICIENCY | 29–33 | Alpha/VF per period (formula column) | Dark Blue |
| ASSET ALLOCATION | 34–39 | Dom. Equity, For. Equity, FI/Sukuk, Money Mkt, Deposits, Other | Brown |
| GEO BREAKDOWN | 40–51 | 11 countries + Other | Green |
| SECTOR BREAKDOWN | 52–62 | 10 sectors + Other | Dark Teal |
| TOP 5 | 63 | Top 5 Holdings | Purple |
| META | 64–67 | VF, VC, Lipper Class, Benchmark | Grey |
| **ATH MOMENTUM** | **68–72** | **ATH NAV, ATH Date, Cur NAV, Drawdown (%), Days from ATH** | **Steel Blue** |

Conditional formatting:
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
| Qualified count | 100–120 at 60% threshold |
| Risk Level coverage | 171/171 |
| ath_results.json — total_processed | 171 |
| ath_results.json — errors | 0 |
| ath_results.json — drawdown range | All values ≤ 0 (positive = data error) |
| fund_code_map.json — count | ~190 |
| Excel — columns | 72 |
| Excel — ATH coverage | 171/171 |

---

## Troubleshooting

### JS output truncated (fewer rows than expected)
- Cause: The JS tool truncates at ~1200 chars regardless of how many rows you request
- Fix: Use exactly 12 rows per batch. At ~73 chars/row → 12 rows = ~876 chars (safely under)
- Never try `slice(0, 50)` — it will silently truncate mid-row

### Browser data lost between sessions
- Symptom: `typeof window.__csv_rows === 'undefined'`
- Cause: Tab closed, page refreshed, or Cowork restarted
- Fix: Re-run Phase 2 (full in-browser extraction) from scratch. Takes ~2 min cold

### Fund missing from code map (scheme_code null/undefined)
- Cause: Casing mismatch between MFR abbr and API key
  - MFR writes `P SmallCap` → API map key is `PSMALLCAP`
  - MFR writes `PeSukuk` → API map key is `PeSUKUK`
- Fix: Query directly by API key in browser: `window.__codeMap['PSMALLCAP']`
  Then patch the assembled CSV row before running assemble_json.py

### build_xlsx.py FileNotFoundError
- Cause: WORK_DIR / OUT_PATH contains an old `/sessions/nifty-vibrant-cannon/...` path
  from a previous Cowork session
- Fix: Update both paths in build_xlsx.py to the current session's `/sessions/` prefix
  Every new Cowork conversation gets a fresh session ID

### Approaches that did NOT work for browser extraction
| Method | Why it failed |
|---|---|
| Full JSON string extract | 42KB → immediately truncated by JS tool |
| Base64 encoding | Blocked by browser security restrictions in Claude in Chrome |
| DOM injection + get_page_text | Injected content not reliably visible to get_page_text |
| Blob URL navigation | Blob URLs are tab-scoped, not accessible cross-tab |

---

## Scripts in this bundle

| Script | Purpose |
|---|---|
| `scripts/extract_mfr.py` | Step 1 — parse MFR PDFs, produce mfr_results.json |
| `scripts/fetch_ath.py` | Step 2 (direct/local) — Python ATH fetcher with cold/warm modes |
| `scripts/assemble_json.py` | Step 2 (browser path) — assemble batch-extracted browser data into JSON |
| `scripts/build_sheet_data.py` | Step 3 — merge MFR + ATH into master_funds.csv |
| `scripts/build_xlsx.py` | Step 4 — build formatted Excel workbook (72 cols) |

**Generated cache files (Funds folder):**

| File | Contents | Persistence |
|---|---|---|
| `fund_code_map.json` | `{fetched, count:190, codes:{abbr→FundCode}}` | Persistent — reuse every month |
| `ath_results.json` | `{generated, total_processed:171, successful, errors, funds[], error_list[]}` | Updated every run |
| `mfr_results.json` | Raw MFR extraction output | Updated every run |
| `master_funds.csv` | Merged flat data for all funds | Updated every run |

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

"Open Google Drive → drag the .xlsx file in → right-click → 'Open with Google Sheets'.
All formatting, filters, and conditional formatting carry over automatically."

---

## Changelog

| Version | Key changes |
|---|---|
| v7 | Documented Cowork/sandbox has no internet — Step 2 requires browser. Two-path Step 2: direct Python (`fetch_ath.py`) vs browser-assisted (batch extraction + `assemble_json.py`). Documented 12-row pipe-CSV batch protocol and ~1200-char JS tool truncation limit. Added Phase 1 browser memory check (saves re-extraction if tab still open). Troubleshooting section: JS truncation, session loss, casing mismatches, stale session paths, failed extraction approaches. Added `assemble_json.py` to bundle. Updated monthly workflow with session path reminder. |
| v6 | Added `fetch_ath.py` (Step 2): ATH NAV + drawdown from publicmutual.com.my API. Cold/warm caching modes. `fund_code_map.json` persistent cache (190 entries). ATH MOMENTUM band in Excel (cols 68–72). Drawdown color scale. 72 columns total. |
| v5 | Formula-driven Summary sheet. Raw % storage (not Excel % format). |
| v4 | Coordinate-based asset allocation. Sector breakdown. Geo breakdown named columns. |
| v3 | PHS objective classification. Risk Level from funds_risk_level.xlsx. |
| v2 | e-Series header detection. Top 5 Holdings extraction. |
| v1 | Initial MFR extraction, benchmark scoring, Excel output. |

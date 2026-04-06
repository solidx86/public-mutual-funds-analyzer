# Fund-Screener v5 Skill Update - Deployment Instructions

## Overview
The fund-screener skill has been updated to v5 with significant improvements:
- 67 total columns (up from 52)
- New Alpha Efficiency band with risk-adjusted performance metrics
- Percentage columns now store raw values for better analysis
- Formula-driven Summary sheet with dynamic updates

## Files Ready for Deployment

### 1. Updated Build Script
**File**: `/sessions/nifty-confident-ramanujan/mnt/Funds/build_xlsx_skill_temp.py`

**Target Location**: `/sessions/nifty-confident-ramanujan/mnt/.claude/skills/fund-screener/scripts/build_xlsx.py`

**Status**: 
- Syntax verified ✓
- WORK_DIR and OUT_PATH reset to empty strings ✓
- Validation block added ✓
- Ready to copy ✓

### 2. Updated Documentation
**File**: `/sessions/nifty-confident-ramanujan/mnt/Funds/SKILL_v5.md`

**Target Location**: `/sessions/nifty-confident-ramanujan/mnt/.claude/skills/fund-screener/SKILL.md`

**Status**:
- Version updated from v4 to v5 ✓
- Column documentation updated ✓
- v5 changes section added ✓
- Ready to copy ✓

## Deployment Steps

### Step 1: Make the Script Writable
The skill scripts directory is mounted as read-only. You need to:

1. Navigate to: `/sessions/nifty-confident-ramanujan/mnt/.claude/skills/fund-screener/scripts/`
2. Change permissions: `chmod u+w build_xlsx.py`

### Step 2: Copy the New Script
```bash
cp /sessions/nifty-confident-ramanujan/mnt/Funds/build_xlsx_skill_temp.py \
   /sessions/nifty-confident-ramanujan/mnt/.claude/skills/fund-screener/scripts/build_xlsx.py
```

### Step 3: Update Documentation
```bash
cp /sessions/nifty-confident-ramanujan/mnt/Funds/SKILL_v5.md \
   /sessions/nifty-confident-ramanujan/mnt/.claude/skills/fund-screener/SKILL.md
```

### Step 4: Verify Deployment
```bash
python3 /sessions/nifty-confident-ramanujan/mnt/.claude/skills/fund-screener/scripts/build_xlsx.py
```
Should print: `ERROR: Please set WORK_DIR and OUT_PATH at the top of this script.`

## What Changed in v5

### Column Structure
```
FUND DETAILS (10)     → Name, Abbr, Series, Type, Geography, Objective, Risk, Distribution, Size, Launch
SCREENING (3)         → Status, Beat (%), Periods
RETURNS (15)          → YTD/1Y/3Y/5Y/10Y × (Fund %, Bench %, Alpha %) — RAW VALUES
ALPHA EFFICIENCY (5)  → NEW: AE YTD/1Y/3Y/5Y/10Y (Alpha / VF)
ASSET ALLOCATION (6)  → Equity, For. Equity, FI/Sukuk, Money Mkt, Deposits, Other — RAW VALUES
GEO BREAKDOWN (12)    → USA, Taiwan, Korea, Japan, France, Germany, China, Singapore, Netherlands, Indonesia, Australia, Other — RAW VALUES
TOP 5 (1)             → Holdings (REMOVED: Sectors column)
META (4)              → VF, VC, Lipper Class, Benchmark

Total: 67 columns
```

### Number Formatting
- Old: Percentage columns displayed as "12.50%" (with % symbol)
- New: Percentage columns display as "12.50" (raw number, no % symbol)
- Reason: Raw values are easier to work with in formulas and analysis

### Summary Sheet
- Old: Median statistics and Top 5 tables hardcoded by Python
- New: Formula-driven with dynamic updates
  - Uses `MEDIAN(FILTER())` for statistics
  - Uses `SORTBY(FILTER(INDEX()))` for Top 5 lists
  - Automatically updates when Master sheet changes

## Testing the Deployment

After copying files, test the script:

```bash
# Set up test environment
WORK_DIR="/path/to/data"
OUT_PATH="/path/to/output.xlsx"

# Edit build_xlsx.py and set these paths at the top

# Run the script
python3 /sessions/nifty-confident-ramanujan/mnt/.claude/skills/fund-screener/scripts/build_xlsx.py
```

Expected output:
1. Excel file created at OUT_PATH
2. Two sheets: Master and Summary
3. Master sheet: 67 columns with all fund data
4. Summary sheet: Dynamic formulas with live calculations

## Compatibility Notes

- v5 is backward compatible with v4 data structure
- Scripts that depend on v4 output may need minor adjustments for the new columns
- The raw percentage format (no %) is the main API change

## Support

See reference documents for details:
- `UPDATE_SUMMARY.txt` - Overview of changes
- `v5_CHANGES_DETAILED.txt` - Technical details
- `SKILL.md` section 4 - Excel output structure

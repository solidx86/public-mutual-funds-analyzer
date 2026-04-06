"""
assemble_json.py — Step 2 (browser path) for Public Mutual Fund Screener v7

PURPOSE:
  When running in Cowork/sandbox (no direct internet), ATH data is extracted from the
  Public Mutual website via Claude in Chrome's JS tool in batches of 12 rows.
  This script takes all those batch strings, parses them, and writes:
    - ath_results.json   (ATH NAV, drawdown, days from ATH for all 171 funds)
    - fund_code_map.json (abbr → FundCode mapping for all ~190 UT funds)

USAGE:
  1. Run the browser extraction (see SKILL.md Step 2, Phases 2–4)
  2. Paste all batch outputs into RAW_CSV below (171 rows total)
  3. Paste code map batches into RAW_CODES below (190 entries)
  4. Update TODAY and FUNDS_DIR
  5. python3 scripts/assemble_json.py

EXPECTED OUTPUT:
  Code map entries: 190
  Parsed: 171 funds, 0 errors
  ✓ Written: .../ath_results.json  (171 funds)
  ✓ Written: .../fund_code_map.json  (190 entries)
"""

import json
import os

# ── CONFIGURE THESE ─────────────────────────────────────────────────────────
TODAY = "YYYY-MM-DD"           # today's date, e.g. "2026-04-06"
FUNDS_DIR = ""                 # path to the Funds folder, e.g. "/path/to/Funds"

# ── RAW_CSV: paste all 171 batch rows here ───────────────────────────────────
# Format: abbr|scheme_code|ath_nav|ath_date|current_nav|current_date|drawdown_pct|days_from_ath|data_from|total_pts
# Each batch from browser: window.__csv_rows.slice(N, N+12).join('\n')
RAW_CSV = """
REPLACE_THIS_WITH_ALL_171_ROWS
""".strip()

# ── RAW_CODES: paste code map batches here (pipe-delimited key=value) ────────
# Each batch from browser: Object.entries(window.__codeMap).slice(0,60).map(([k,v])=>`${k}=${v}`).join('|')
RAW_CODES = (
    "REPLACE_BATCH_1_HERE|"
    "REPLACE_BATCH_2_HERE|"
    "REPLACE_BATCH_3_HERE"
)

# ── Validation ────────────────────────────────────────────────────────────────
if TODAY == "YYYY-MM-DD" or not TODAY:
    raise ValueError("Set TODAY to today's date before running")
if not FUNDS_DIR:
    raise ValueError("Set FUNDS_DIR to the Funds folder path before running")
if "REPLACE_THIS" in RAW_CSV or "REPLACE_BATCH" in RAW_CODES:
    raise ValueError("Paste the browser-extracted data into RAW_CSV and RAW_CODES first")

# ── Parse code map ─────────────────────────────────────────────────────────
code_map = {}
for pair in RAW_CODES.split("|"):
    pair = pair.strip()
    if "=" in pair:
        k, v = pair.split("=", 1)
        code_map[k.strip()] = v.strip()

print(f"Code map entries: {len(code_map)}")

# ── Parse ATH rows ──────────────────────────────────────────────────────────
funds = []
errors = []

for line_num, line in enumerate(RAW_CSV.strip().split("\n"), start=1):
    line = line.strip()
    if not line:
        continue
    parts = line.split("|")
    if len(parts) != 10:
        errors.append({
            "abbr": line[:30],
            "error": f"line {line_num}: expected 10 fields, got {len(parts)}"
        })
        continue
    abbr, sc, ath_nav, ath_date, cur_nav, cur_date, dd_pct, days, data_from, pts = parts
    try:
        rec = {
            "abbr":             abbr,
            "scheme_code":      sc,
            "ath_nav":          float(ath_nav),
            "ath_date":         ath_date,
            "current_nav":      float(cur_nav),
            "current_date":     cur_date,
            "drawdown_pct":     float(dd_pct),
            "days_from_ath":    int(days),
            "data_from":        data_from,
            "total_data_points": int(pts),
            "last_checked":     TODAY,
        }
        funds.append(rec)
    except Exception as e:
        errors.append({"abbr": abbr, "error": str(e)})

print(f"Parsed: {len(funds)} funds, {len(errors)} errors")
if errors:
    for err in errors:
        print(f"  ERROR: {err}")

# ── Write ath_results.json ───────────────────────────────────────────────────
ath_out = {
    "generated":        TODAY,
    "today":            TODAY,
    "total_processed":  len(funds),
    "successful":       len(funds) - len(errors),
    "errors":           len(errors),
    "funds":            funds,
    "error_list":       errors,
}

ath_path = os.path.join(FUNDS_DIR, "ath_results.json")
with open(ath_path, "w", encoding="utf-8") as f:
    json.dump(ath_out, f, indent=2)
print(f"✓ Written: {ath_path}  ({len(funds)} funds)")

# ── Write fund_code_map.json ─────────────────────────────────────────────────
cm_out = {
    "fetched": TODAY,
    "count":   len(code_map),
    "codes":   code_map,
}

cm_path = os.path.join(FUNDS_DIR, "fund_code_map.json")
with open(cm_path, "w", encoding="utf-8") as f:
    json.dump(cm_out, f, indent=2)
print(f"✓ Written: {cm_path}  ({len(code_map)} entries)")

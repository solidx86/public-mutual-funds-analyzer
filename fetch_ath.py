"""
fetch_ath.py — Step 4: Fetch All-Time High (ATH) NAV for every Public Mutual fund.

TWO-MODE OPERATION (efficiency by design)
==========================================
COLD RUN (first time, or --cold flag):
  - Fetches full NAV history from inception for every fund
  - Computes ATH from scratch
  - Saves results to ath_results.json

WARM RUN (subsequent monthly runs, default):
  - Step 1: One bulk call → current NAV for ALL funds simultaneously
  - Step 2: Per-fund delta call → only NAV since last_checked date
  - Compares delta max vs cached ATH → updates only if broken
  - Result: ~170 small calls instead of 170 full-history calls

WHY THIS MATTERS
================
  PIATAF launched Dec 2011 → ~3,200 data points on a cold run
  Monthly warm run → ~22 data points (one month of trading days)
  Speedup: ~145x fewer data points per fund on warm runs

FUND CODE MAP CACHING
=====================
  The abbr→FundCode mapping (GetFundExplorerData) is fetched ONCE and saved
  to fund_code_map.json. It is reused on every subsequent run.
  Auto-refresh triggers when a fund from mfr_results.json is missing from
  the cached map — silently handles new fund launches without manual intervention.
  Force a manual refresh with: python3 fetch_ath.py --refresh-codes

USAGE
=====
  python3 fetch_ath.py                    # warm run (incremental, reuses code map)
  python3 fetch_ath.py --cold             # cold run (full history, reuses code map)
  python3 fetch_ath.py --refresh-codes    # force-refresh fund code map, then warm run
  python3 fetch_ath.py --cold --refresh-codes  # rebuild everything from scratch

REQUIRES
========
  pip install requests --break-system-packages
  mfr_results.json  (from extract_mfr.py) — if absent, processes all ~190 UT funds

OUTPUT
======
  fund_code_map.json — cached abbr→FundCode mapping (fetch once, reuse forever)
  ath_results.json   — one record per fund, updated in-place each run
"""

import json
import time
import re
import os
import sys
from datetime import date, datetime, timedelta

# ── PATHS ────────────────────────────────────────────────────────────────────
FUNDS_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH      = os.path.join(FUNDS_DIR, "ath_results.json")
MFR_RESULTS      = os.path.join(FUNDS_DIR, "mfr_results.json")
CODE_MAP_PATH    = os.path.join(FUNDS_DIR, "fund_code_map.json")  # persisted cache

BASE_URL      = "https://www.publicmutual.com.my"
DELAY_SECONDS = 0.5          # polite pause between per-fund calls
COLD_START    = "01-Jan-2000" # safe far-back date for cold runs
TODAY         = date.today()
TODAY_STR     = TODAY.strftime("%d-%b-%Y")   # "06-Apr-2026"
TODAY_LOCAL   = TODAY.strftime("%d/%m/%Y")   # "06/04/2026"  (for bulk endpoint)


# ── SESSION + CSRF ────────────────────────────────────────────────────────────

def get_session_and_token():
    import requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    })
    page = session.get(f"{BASE_URL}/fund-explorer-list", timeout=30)
    page.raise_for_status()

    token = None
    for pat in [
        r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"',
        r'__RequestVerificationToken[^>]*value="([^"]+)"',
    ]:
        m = re.search(pat, page.text)
        if m:
            token = m.group(1)
            break

    if not token:
        raise RuntimeError("Could not extract CSRF token from fund-explorer-list")

    print(f"  CSRF token obtained ({len(token)} chars)")
    return session, token


# ── FUND CODE MAPPING ─────────────────────────────────────────────────────────

def _fetch_code_map_from_api(session, token):
    """Fetch live abbr→FundCode mapping from GetFundExplorerData."""
    resp = session.get(
        f"{BASE_URL}/FundExplorerList/GetFundExplorerData",
        params={"date": TODAY_LOCAL},
        headers={"Content-Type": "application/json", "RequestVerificationToken": token},
        timeout=30,
    )
    resp.raise_for_status()
    funds = resp.json().get("ResultData") or []
    return {
        (f.get("FundAbbr") or "").strip(): str(f.get("FundCode", ""))
        for f in funds
        if f.get("FundAbbr") and f.get("FundCode")
    }


def get_fund_code_map(session, token, force_refresh=False, required_abbrs=None):
    """
    Return { "PIATAF": "39", "PeAITF": "170", ... }.

    Cache strategy:
      1. Load fund_code_map.json if it exists and force_refresh is False.
      2. Auto-refresh if any required_abbr is missing from the cached map
         (handles new fund launches silently).
      3. Save fetched map back to fund_code_map.json for future runs.
    """
    cached_map = {}

    if not force_refresh and os.path.exists(CODE_MAP_PATH):
        with open(CODE_MAP_PATH) as f:
            meta = json.load(f)
        cached_map = meta.get("codes", {})
        missing = [a for a in (required_abbrs or []) if a not in cached_map]

        if not missing:
            print(f"  Fund code map: {len(cached_map)} funds (cached from {meta.get('fetched', '?')})")
            return cached_map
        else:
            print(f"  Fund code map: {len(missing)} new fund(s) not in cache → refreshing from API")
    else:
        reason = "forced refresh" if force_refresh else "no cache found"
        print(f"  Fund code map: fetching from API ({reason})...")

    # Fetch from API and persist
    live_map = _fetch_code_map_from_api(session, token)
    with open(CODE_MAP_PATH, "w") as f:
        json.dump({"fetched": TODAY.isoformat(), "count": len(live_map), "codes": live_map}, f, indent=2)

    print(f"  Fund code map: {len(live_map)} funds fetched → saved to fund_code_map.json")
    return live_map


# ── BULK CURRENT NAV (1 call for all funds) ───────────────────────────────────

def get_all_current_navs(session, token):
    """
    One call to GetAllUTFundPriceByDate returns today's NAV for every fund.
    Returns { "PIATAF": {"nav": 0.884, "date": "2026-04-02"}, ... }
    """
    resp = session.get(
        f"{BASE_URL}/FundPriceUT/GetAllUTFundPriceByDate",
        params={"date": TODAY.strftime("%Y-%m-%d")},
        headers={"Content-Type": "application/json", "RequestVerificationToken": token},
        timeout=30,
    )
    # This endpoint may require a fresh token on the Fund-Price-UT page
    if resp.status_code != 200 or resp.json().get("ResponseCode") != 1:
        return {}  # fallback: current NAV will be taken from delta call instead

    funds = resp.json().get("ResultData") or []
    return {
        (f.get("FundAbbr") or "").strip(): {
            "nav":  round(float(f.get("Nav") or 0), 4),
            "date": f.get("NavDate") or TODAY.strftime("%Y-%m-%d"),
        }
        for f in funds if f.get("FundAbbr")
    }


# ── NAV HISTORY (per-fund, date-ranged) ──────────────────────────────────────

def fetch_nav_range(session, token, scheme_code, start_date):
    """Fetch NAV data from start_date to today for one fund."""
    payload = {
        "SchemeCode": scheme_code,
        "StartDate":  start_date,
        "EndDate":    TODAY_STR,
        "IndexCode":  "",
    }
    resp = session.post(
        f"{BASE_URL}/FundOverview/GetFundPerformanceChartData",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "RequestVerificationToken": token,
            "Referer": f"{BASE_URL}/Fund-Overview?sc={scheme_code}",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("ResponseCode") != 1:
        return []
    return data.get("ResultData", {}).get("FundIndex", [])


# ── ATH COMPUTATION ───────────────────────────────────────────────────────────

def series_max(nav_series):
    """Return (max_nav, max_date) from a list of {Date, Nav} dicts."""
    best_nav, best_date = float("-inf"), None
    for pt in nav_series:
        nav = pt.get("Nav")
        if nav is None:
            continue
        nav = float(nav)
        if nav > best_nav:
            best_nav, best_date = nav, pt["Date"]
    return best_nav, best_date


def build_record(abbr, ath_nav, ath_date, current_nav, current_date, data_from, n_points):
    try:
        ath_dt = datetime.strptime(ath_date, "%Y-%m-%d").date()
        days_from_ath = (TODAY - ath_dt).days
    except Exception:
        days_from_ath = None

    drawdown_pct = (
        round((current_nav - ath_nav) / ath_nav * 100, 2) if ath_nav > 0 else None
    )
    return {
        "abbr":           abbr,
        "ath_nav":        round(ath_nav, 4),
        "ath_date":       ath_date,
        "current_nav":    round(current_nav, 4),
        "current_date":   current_date,
        "drawdown_pct":   drawdown_pct,
        "days_from_ath":  days_from_ath,
        "data_from":      data_from,
        "total_data_points": n_points,
        "last_checked":   TODAY.isoformat(),
    }


# ── CACHE I/O ─────────────────────────────────────────────────────────────────

def load_cache():
    """Load existing ath_results.json. Returns {} if file doesn't exist."""
    if not os.path.exists(OUTPUT_PATH):
        return {}
    with open(OUTPUT_PATH) as f:
        data = json.load(f)
    funds = data.get("funds") or []
    return {r["abbr"]: r for r in funds}


def save_cache(results, errors):
    output = {
        "generated":       TODAY.isoformat(),
        "today":           TODAY_STR,
        "total_processed": len(results),
        "errors":          len(errors),
        "funds":           list(results.values()),
        "error_list":      errors,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)


# ── TARGET FUNDS ──────────────────────────────────────────────────────────────

def _load_mfr_abbrs():
    """Load fund abbreviations from mfr_results.json. Returns None if file absent."""
    if not os.path.exists(MFR_RESULTS):
        return None
    with open(MFR_RESULTS) as f:
        mfr = json.load(f)
    return [f.get("abbreviation", "").strip() for f in mfr if f.get("abbreviation")]


def _resolve_targets(code_map, mfr_abbrs):
    """Determine which funds to process and log the outcome."""
    if mfr_abbrs:
        found   = [a for a in mfr_abbrs if a in code_map]
        missing = [a for a in mfr_abbrs if a not in code_map]
        print(f"  From mfr_results.json: {len(mfr_abbrs)} funds → {len(found)} matched in code map")
        if missing:
            print(f"  NOTE: still unmatched after refresh: {missing}")
        return found
    else:
        print("  mfr_results.json not found — processing all UT funds from code map")
        return list(code_map.keys())


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    cold            = "--cold" in sys.argv
    refresh_codes   = "--refresh-codes" in sys.argv
    mode            = "COLD (full history rebuild)" if cold else "WARM (incremental update)"

    print("=" * 62)
    print(f"  fetch_ath.py  |  {mode}")
    print(f"  Date: {TODAY_STR}")
    print("=" * 62)

    try:
        import requests  # noqa
    except ImportError:
        print("ERROR: requests not installed.")
        print("Run:   pip install requests --break-system-packages")
        return

    # ── Setup — session always needed (CSRF token for NAV calls) ─────────────
    session, token = get_session_and_token()

    # ── Fund code map — load from cache, auto-refresh if needed ─────────────
    # Load MFR abbrs first so we can detect any new funds missing from cache
    mfr_abbrs = _load_mfr_abbrs()
    code_map  = get_fund_code_map(
        session, token,
        force_refresh=refresh_codes,
        required_abbrs=mfr_abbrs,
    )
    target_abbrs = _resolve_targets(code_map, mfr_abbrs)
    cache          = {} if cold else load_cache()

    # ── Bulk current NAV (warm run only — 1 call covers all funds) ───────────
    bulk_navs = {}
    if not cold:
        print("\n  Fetching bulk current NAV (1 call for all funds)...", end=" ")
        bulk_navs = get_all_current_navs(session, token)
        status = f"{len(bulk_navs)} funds" if bulk_navs else "unavailable (fallback to per-fund)"
        print(status)

    # ── Per-fund processing ──────────────────────────────────────────────────
    print(f"\n  Processing {len(target_abbrs)} funds...\n")

    results = {}  # abbr → record
    errors  = []

    for i, abbr in enumerate(target_abbrs, 1):
        scheme_code = code_map[abbr]
        cached      = cache.get(abbr)
        label       = f"[{i:3d}/{len(target_abbrs)}] {abbr:<14} (sc={scheme_code:<4})"

        try:
            if cold or not cached:
                # ── Cold: fetch full history ──────────────────────────────
                print(f"  {label} COLD", end=" ", flush=True)
                series = fetch_nav_range(session, token, scheme_code, COLD_START)
                if not series:
                    print("⚠ no data")
                    errors.append({"abbr": abbr, "error": "empty cold response"})
                    continue
                ath_nav, ath_date  = series_max(series)
                last               = series[-1]
                current_nav        = float(last["Nav"])
                current_date       = last["Date"]
                data_from          = series[0]["Date"]
                n_points           = len(series)

            else:
                # ── Warm: delta from last_checked, merge with cache ───────
                last_checked = cached.get("last_checked") or cached.get("ath_date")
                # Shift one day forward so we don't re-fetch the last known point
                delta_start  = (
                    datetime.strptime(last_checked, "%Y-%m-%d").date() + timedelta(days=1)
                ).strftime("%d-%b-%Y")

                print(f"  {label} WARM Δ{delta_start}→{TODAY_STR}", end=" ", flush=True)

                # Current NAV: prefer bulk result, else take from delta series
                bulk = bulk_navs.get(abbr)
                if bulk:
                    current_nav  = bulk["nav"]
                    current_date = bulk["date"]

                # Delta series: only needed if current NAV might break ATH,
                # or if bulk call was unavailable
                delta = fetch_nav_range(session, token, scheme_code, delta_start)

                if not bulk:
                    if delta:
                        last         = delta[-1]
                        current_nav  = float(last["Nav"])
                        current_date = last["Date"]
                    else:
                        # No new data since last check — reuse cached values
                        current_nav  = cached["current_nav"]
                        current_date = cached["current_date"]

                # Check if ATH was broken in the delta window
                cached_ath_nav  = cached["ath_nav"]
                cached_ath_date = cached["ath_date"]

                if delta:
                    delta_max, delta_max_date = series_max(delta)
                    if delta_max > cached_ath_nav:
                        ath_nav, ath_date = delta_max, delta_max_date
                        print("★ NEW ATH!", end=" ")
                    else:
                        ath_nav, ath_date = cached_ath_nav, cached_ath_date
                else:
                    ath_nav, ath_date = cached_ath_nav, cached_ath_date

                data_from = cached.get("data_from")
                n_points  = cached.get("total_data_points", 0) + len(delta)

            record = build_record(abbr, ath_nav, ath_date, current_nav, current_date, data_from, n_points)
            results[abbr] = record

            dd_str = f"{record['drawdown_pct']:+.2f}%" if record["drawdown_pct"] is not None else "N/A"
            print(f"ATH={ath_nav:.4f} on {ath_date} | Now={current_nav:.4f} | DD={dd_str}")

        except Exception as e:
            print(f"✗ {e}")
            errors.append({"abbr": abbr, "error": str(e)})
            if cached:
                results[abbr] = cached  # preserve last known good data

        time.sleep(DELAY_SECONDS)

    # ── Persist ──────────────────────────────────────────────────────────────
    save_cache(results, errors)

    print(f"\n{'='*62}")
    print(f"  Done. {len(results)} funds | {len(errors)} errors | {OUTPUT_PATH}")
    print(f"{'='*62}")

    # ── Summary ──────────────────────────────────────────────────────────────
    if results:
        dds     = sorted(r["drawdown_pct"] for r in results.values() if r.get("drawdown_pct") is not None)
        buckets = {
            "At/near ATH  (>= -1%)":    sum(1 for d in dds if d >= -1.0),
            "Mild DD   (-10% to -1%)":   sum(1 for d in dds if -10.0 <= d < -1.0),
            "Moderate  (-20% to -10%)":  sum(1 for d in dds if -20.0 <= d < -10.0),
            "Deep DD      (< -20%)":     sum(1 for d in dds if d < -20.0),
        }
        median = dds[len(dds) // 2] if dds else None
        new_aths = [a for a, r in results.items()
                    if r.get("ath_date") == TODAY.isoformat() or
                       (r.get("days_from_ath") is not None and r["days_from_ath"] <= 30)]

        print("\n  Drawdown Buckets:")
        for label, count in buckets.items():
            print(f"    {label}: {count:3d} funds")
        if median is not None:
            print(f"\n  Median drawdown: {median:+.2f}%")
        if new_aths:
            print(f"\n  Funds at/near ATH (within 30 days): {', '.join(new_aths[:10])}")
            if len(new_aths) > 10:
                print(f"    ...and {len(new_aths)-10} more")


if __name__ == "__main__":
    main()

"""
portfolio.py — experience-blind 4-fund portfolio builder.

build(scores, funds, profile, shariah) -> list[Holding]

Every client gets the same structure:
  - 2 core funds (top-2 by CFS composite, excluding structurals)
  - 1 gold structural (PeEMAS)
  - 1 money-market structural (PIMMF-A if shariah else PeCDF-A)

Allocation is profile-gradient, CFS-proportional for core, normalized to 100.0.
"""

from __future__ import annotations
from typing import Any

# Sleeve midpoints from SKILL.md §4
TEMPLATE: dict[str, dict[str, float]] = {
    "Conservative":          {"core": 63.5, "gold": 6.5,  "mm": 17.5},
    "Moderate":              {"core": 63.5, "gold": 9.0,  "mm": 13.5},
    "Moderately Aggressive": {"core": 67.5, "gold": 9.0,  "mm": 11.0},
    "Aggressive":            {"core": 73.0, "gold": 10.0, "mm": 10.0},
}

GOLD_ABBR = "PeEMAS"
MM_ABBR_SHARIAH = "PIMMF-A"
MM_ABBR_CONVENTIONAL = "PeCDF-A"

STRUCTURAL_ABBRS = {GOLD_ABBR, MM_ABBR_SHARIAH, MM_ABBR_CONVENTIONAL}

Holding = dict[str, Any]


def build(
    scores: list[dict],
    funds: dict[str, dict],
    profile: str,
    shariah: bool | None,
) -> list[Holding]:
    """Return a 4-holding portfolio list.

    Args:
        scores:  List of CFSScore dicts sorted descending by composite.
        funds:   Dict abbr -> Fund.
        profile: One of the TEMPLATE keys.
        shariah: True -> use PIMMF-A; False/None -> use PeCDF-A.

    Returns:
        List of 4 Holding dicts: {"abbr", "role", "allocation_pct"}.
    """
    mm_abbr = MM_ABBR_SHARIAH if shariah is True else MM_ABBR_CONVENTIONAL

    # Pick top-2 core funds (exclude structural abbrs so they don't double-count)
    core_scores = [s for s in scores if s["abbr"] not in STRUCTURAL_ABBRS][:2]

    tmpl = TEMPLATE[profile]
    core_budget = tmpl["core"]
    gold_raw = tmpl["gold"]
    mm_raw = tmpl["mm"]

    # CFS-proportional split of core budget
    composite_sum = sum(s["composite"] for s in core_scores)
    if composite_sum == 0:
        # Equal split fallback
        core_raws = [core_budget / 2.0] * 2
    else:
        core_raws = [core_budget * s["composite"] / composite_sum for s in core_scores]

    # Assemble raw weights
    raw_weights: list[tuple[str, str, float]] = []
    for s, raw in zip(core_scores, core_raws):
        raw_weights.append((s["abbr"], "core", raw))
    raw_weights.append((GOLD_ABBR, "structural:gold", gold_raw))
    raw_weights.append((mm_abbr, "structural:money_market", mm_raw))

    # Normalize to 100.0
    total_raw = sum(w[2] for w in raw_weights)
    holdings = [
        {"abbr": abbr, "role": role, "allocation_pct": round(raw / total_raw * 100, 1)}
        for abbr, role, raw in raw_weights
    ]

    # Fix rounding residual on the largest holding
    residual = round(100.0 - sum(h["allocation_pct"] for h in holdings), 1)
    if residual != 0.0:
        largest_idx = max(range(len(holdings)), key=lambda i: holdings[i]["allocation_pct"])
        holdings[largest_idx]["allocation_pct"] = round(
            holdings[largest_idx]["allocation_pct"] + residual, 1
        )

    return holdings


def exposure_gap_pick(
    portfolio: list[Holding],
    candidates: list[dict],
    gaps: list[str],
    profile: str,
) -> list[Holding]:
    """Swap ONE exposure-gap fund into the lowest-alpha core slot.

    Returns the portfolio unchanged (same object) when:
      - any holding has role == "satellite"
      - gaps is empty
      - no candidate has 3Y alpha > 0

    Otherwise substitutes the lowest-alpha_n core holding with the
    best-qualifying candidate (highest 3Y alpha > 0), capped at 15%,
    redistributing any freed share to surviving core holdings proportionally.
    Always returns a list of the same length as the input portfolio.
    """
    # No-op: satellite present
    if any(h.get("role") == "satellite" for h in portfolio):
        return portfolio

    # No-op: no gaps
    if not gaps:
        return portfolio

    # Gate candidates: 3Y alpha > 0, pick highest
    qualified = [
        c for c in candidates
        if c.get("returns", {}).get("3y", {}).get("alpha", 0) > 0
    ]
    if not qualified:
        return portfolio

    picked = max(qualified, key=lambda c: c["returns"]["3y"]["alpha"])

    # Find core holdings; pick the one with lowest alpha_n
    core_holdings = [h for h in portfolio if h.get("role") == "core"]
    if not core_holdings:
        return portfolio

    replaced = min(core_holdings, key=lambda h: h.get("alpha_n", 0))
    replaced_pct = replaced["allocation_pct"]

    # Cap the new holding at 15%
    new_pct = min(15.0, replaced_pct)
    freed = replaced_pct - new_pct  # >= 0

    # Surviving core holdings (not the one being replaced)
    surviving_core = [h for h in portfolio if h.get("role") == "core" and h is not replaced]

    # Build new portfolio (new list; don't mutate input)
    new_portfolio: list[Holding] = []
    gap_holding: Holding = {"abbr": picked["abbr"], "role": "exposure_gap", "allocation_pct": new_pct}

    # Compute redistribution of freed share among surviving cores, proportional
    surviving_total = sum(h["allocation_pct"] for h in surviving_core)
    adjustments: dict[int, float] = {}
    if freed > 0 and surviving_core:
        if surviving_total == 0:
            # Equal redistribution fallback
            per_core = freed / len(surviving_core)
            for h in surviving_core:
                adjustments[id(h)] = h["allocation_pct"] + per_core
        else:
            for h in surviving_core:
                adjustments[id(h)] = round(
                    h["allocation_pct"] + freed * h["allocation_pct"] / surviving_total, 1
                )

    # Assemble new list preserving original order, replacing the removed core
    replaced_inserted = False
    for h in portfolio:
        if h is replaced:
            new_portfolio.append(gap_holding)
            replaced_inserted = True
        elif h.get("role") == "core" and id(h) in adjustments:
            new_portfolio.append({
                **h,
                "allocation_pct": adjustments[id(h)],
            })
        else:
            new_portfolio.append(dict(h))

    # Fix rounding residual on the largest holding so sum is exactly 100.0
    total = sum(h["allocation_pct"] for h in new_portfolio)
    residual = round(100.0 - total, 1)
    if residual != 0.0:
        largest_idx = max(range(len(new_portfolio)), key=lambda i: new_portfolio[i]["allocation_pct"])
        new_portfolio[largest_idx] = {
            **new_portfolio[largest_idx],
            "allocation_pct": round(new_portfolio[largest_idx]["allocation_pct"] + residual, 1),
        }

    return new_portfolio


def alpha_outlier(
    portfolio: list[Holding],
    scores: list[dict],
    funds: dict[str, dict],
    profile: str,
    shariah: bool | None,
) -> list[Holding]:
    """Optionally swap ONE high-alpha satellite fund into the lowest-alpha_n core slot.

    Returns the portfolio unchanged (same object) when:
      - profile == "Aggressive"
      - no candidate passes all gates (A, A2, B, C)

    Otherwise substitutes the lowest-alpha_n core holding with the satellite.
    The satellite INHERITS the replaced core's allocation_pct exactly (no redistribution).
    Always returns a list of exactly 4 holdings summing to 100.

    Args:
        portfolio: Current 4-holding portfolio list.
        scores:    CFS score list sorted descending by composite.
        funds:     Dict abbr -> Fund.
        profile:   Risk profile string.
        shariah:   True -> Shariah only; False -> conventional only; None -> no filter.
    """
    # Step 1: Aggressive skip
    if profile == "Aggressive":
        return portfolio

    # Step 2: Candidate pool — Qualified, not already held, top-5 by composite
    held_abbrs = {h["abbr"] for h in portfolio}
    candidates = [
        s for s in scores
        if funds.get(s["abbr"], {}).get("status") == "Qualified"
        and s["abbr"] not in held_abbrs
    ][:5]

    # Look up held core holdings for overlap check (gate C)
    held_cores = [h for h in portfolio if h.get("role") == "core"]

    pick_abbr: str | None = None
    for s in candidates:
        abbr = s["abbr"]
        fund = funds.get(abbr, {})

        # Gate A: 3Y alpha > 0, and 5Y alpha (if present) > 0
        returns = fund.get("returns", {})
        alpha_3y = returns.get("3y", {}).get("alpha")
        alpha_5y = returns.get("5y", {}).get("alpha")
        if alpha_3y is None or alpha_3y <= 0:
            continue
        if alpha_5y is not None and alpha_5y <= 0:
            continue

        # Gate A2: alpha_n >= 80
        if s.get("alpha_n", 0) < 80:
            continue

        # Gate B: Shariah filter
        fund_shariah = fund.get("shariah")
        if shariah is True and fund_shariah is not True:
            continue
        if shariah is False and fund_shariah is not False:
            continue

        # Gate C: overlap with each held core's top5 must be < 3
        candidate_top5 = set(fund.get("top5") or [])
        overlap_blocked = False
        for core_h in held_cores:
            core_fund = funds.get(core_h["abbr"])
            if core_fund is None:
                continue
            core_top5 = set(core_fund.get("top5") or [])
            if len(candidate_top5 & core_top5) >= 3:
                overlap_blocked = True
                break
        if overlap_blocked:
            continue

        # First candidate to pass all gates wins (scores already sorted by composite desc)
        pick_abbr = abbr
        break

    if pick_abbr is None:
        return portfolio

    # Step 5: Substitute lowest-alpha_n core holding
    if not held_cores:
        return portfolio

    replaced = min(held_cores, key=lambda h: h.get("alpha_n", 0))
    satellite: Holding = {
        "abbr": pick_abbr,
        "role": "satellite",
        "allocation_pct": replaced["allocation_pct"],
    }

    new_portfolio: list[Holding] = []
    for h in portfolio:
        if h is replaced:
            new_portfolio.append(satellite)
        else:
            new_portfolio.append(dict(h))

    return new_portfolio


def dedup_overlap(picks: list[dict]) -> list[dict]:
    """Remove picks with overlapping top-5 holdings.

    If two picks share ≥3 of their top-5 holdings, mark the one with the lower
    alpha_n for removal. Return the input list with removed picks filtered out,
    preserving the original order of survivors.

    Args:
        picks: List of pick dicts, each with "abbr", "alpha_n", "top5" keys.
               Missing or empty top5 is treated as no overlap.

    Returns:
        Filtered list of picks (same type and order, minus removed ones).
    """
    to_remove = set()

    # Check all pairs
    for i in range(len(picks)):
        for j in range(i + 1, len(picks)):
            pick_i = picks[i]
            pick_j = picks[j]

            # Get top5, defaulting to empty list
            top5_i = set(pick_i.get("top5", []))
            top5_j = set(pick_j.get("top5", []))

            # Count overlap
            overlap_count = len(top5_i & top5_j)

            if overlap_count >= 3:
                # Mark the one with lower alpha_n for removal
                alpha_i = pick_i.get("alpha_n", 0)
                alpha_j = pick_j.get("alpha_n", 0)

                if alpha_i < alpha_j:
                    to_remove.add(i)
                else:
                    to_remove.add(j)

    # Return filtered list preserving order
    return [picks[idx] for idx in range(len(picks)) if idx not in to_remove]

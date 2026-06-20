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

"""Deterministic invariant gate for portfolio validation.

``check_invariants`` is a pure function reused by ``build_portfolio`` (post-build)
and the HITL review gate (post human-edit).  No I/O, no state.
"""

from __future__ import annotations

from typing import Any

PROFILES = ("Conservative", "Moderate", "Moderately Aggressive", "Aggressive")

# Exactly 4 funds for every profile (min, max).
SIZE: dict[str, tuple[int, int]] = {p: (4, 4) for p in PROFILES}

# Maximum allocation % for any single fund.
CAP: dict[str, int] = {
    "Conservative": 50,
    "Moderate": 50,
    "Moderately Aggressive": 60,
    "Aggressive": 70,
}

# Maximum risk level allowed (inclusive), except for satellite role.
CEILING: dict[str, int] = {
    "Conservative": 2,
    "Moderate": 3,
    "Moderately Aggressive": 4,
    "Aggressive": 5,
}


def check_invariants(
    portfolio: list[dict[str, Any]],
    profile: str,
    universe: set[str],
    rl_by_abbr: dict[str, int],
) -> list[dict[str, str]]:
    """Return a list of violation dicts ``{"code": ..., "msg": ...}``.

    An empty list means the portfolio is clean.

    Parameters
    ----------
    portfolio:
        List of holdings, each ``{"abbr", "role", "allocation_pct"}``.
        ``role`` ∈ {"core","structural:gold","structural:money_market",
        "satellite","exposure_gap"}.
    profile:
        One of PROFILES.
    universe:
        Set of eligible abbrs (scored/retail-eligible universe).
    rl_by_abbr:
        Map of abbr → int risk level (1–5).  Missing keys are skipped
        for the RL check (universe check already guards membership).
    """
    violations: list[dict[str, str]] = []

    # 1. sum check
    total = sum(h["allocation_pct"] for h in portfolio)
    if abs(total - 100) > 0.5:
        violations.append({
            "code": "sum",
            "msg": f"allocations sum to {total}, expected 100",
        })

    # 2. count check
    min_size, max_size = SIZE[profile]
    n = len(portfolio)
    if not (min_size <= n <= max_size):
        violations.append({
            "code": "count",
            "msg": (
                f"portfolio has {n} fund(s), expected exactly {min_size}"
            ),
        })

    # 3. concentration cap
    cap = CAP[profile]
    for h in portfolio:
        pct = h["allocation_pct"]
        abbr = h["abbr"]
        if pct > cap:
            violations.append({
                "code": "concentration_cap",
                "msg": (
                    f"{abbr} {pct} exceeds the {profile} concentration cap of {cap}"
                ),
            })

    # 4. RL ceiling (satellite and structural roles are exempt)
    # Gold and money-market are always-included structural hedges, so they must
    # not trip the ceiling even when their RL exceeds the profile ceiling.
    _rl_exempt_roles = {"satellite", "structural:gold", "structural:money_market"}
    ceiling = CEILING[profile]
    for h in portfolio:
        abbr = h["abbr"]
        if h["role"] in _rl_exempt_roles:
            continue
        rl = rl_by_abbr.get(abbr)
        if rl is None:
            continue  # missing from lookup — universe check guards membership
        if rl > ceiling:
            violations.append({
                "code": "rl_ceiling",
                "msg": (
                    f"{abbr} has risk level {rl} which exceeds the {profile} "
                    f"ceiling of {ceiling}"
                ),
            })

    # 5. structural: both gold and money-market must be present
    roles = {h["role"] for h in portfolio}
    if "structural:gold" not in roles or "structural:money_market" not in roles:
        violations.append({
            "code": "structural",
            "msg": (
                "portfolio must contain both a structural:gold and a "
                "structural:money_market holding"
            ),
        })

    # 6. universe: every abbr must be in the eligible universe
    for h in portfolio:
        abbr = h["abbr"]
        if abbr not in universe:
            violations.append({
                "code": "universe",
                "msg": (
                    f"{abbr} is not in the scored/eligible universe"
                ),
            })

    return violations

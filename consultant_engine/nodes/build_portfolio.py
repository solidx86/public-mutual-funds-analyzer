"""build_portfolio node — composes the 4-fund portfolio with invariant gate.

Pipeline position: after score_cfs.
Inputs:  state["eligible_funds"], state["client_profile"], state["cfs_scores"],
         state.get("macro_context")  (optional; exposure_gaps read from it)
Outputs: state["portfolio"], state["proposed_allocation"]
"""

from __future__ import annotations

from consultant_engine.invariants import check_invariants
from consultant_engine.portfolio import (
    build,
    dedup_overlap,
    alpha_outlier,
    exposure_gap_pick,
)
from consultant_engine.state import ConsultantState

# Structural abbrs excluded from core-candidate ranking
STRUCTURAL = {"PeEMAS", "PeCDF-A", "PIMMF-A"}


def build_portfolio(state: ConsultantState) -> dict:
    """Compose a 4-fund portfolio and validate it against the invariant gate.

    Raises
    ------
    RuntimeError
        If the assembled portfolio violates any invariant — this is a build-time
        bug, not a user-facing error, and must be fixed at the implementation level.
    """
    funds_by_abbr: dict = {f["abbr"]: f for f in state["eligible_funds"]}
    profile: str = state["client_profile"]["risk_level"]
    shariah: bool | None = state["client_profile"].get("shariah")
    scores: list[dict] = state["cfs_scores"]

    # --- dedup core candidates BEFORE build picks top-2 ---
    # Attach each candidate's top5 from the fund dict so dedup_overlap can check
    # holding overlap between candidates.
    core_cands = [
        {**s, "top5": funds_by_abbr.get(s["abbr"], {}).get("top5", [])}
        for s in scores
        if s["abbr"] not in STRUCTURAL
    ]
    deduped = dedup_overlap(core_cands)

    # --- build the base 4-fund portfolio ---
    port = build(deduped, funds_by_abbr, profile, shariah)

    # --- satellite substitution (claims the single discretionary slot) ---
    port = alpha_outlier(port, scores, funds_by_abbr, profile, shariah)

    # --- exposure-gap pick (no-ops when satellite present or no gaps) ---
    gaps: list[str] = (state.get("macro_context") or {}).get("exposure_gaps", [])
    # Pass eligible_funds as candidates; exposure_gap_pick reads fund["returns"][...]["alpha"]
    # which is present on every fund loaded by load_funds.
    port = exposure_gap_pick(
        port,
        candidates=state["eligible_funds"],
        gaps=gaps,
        profile=profile,
    )

    # --- invariant gate ---
    # Universe = eligible abbrs ∪ structural abbrs actually in the book
    # (structural funds may not appear in eligible_funds if they were filtered out
    # by risk/shariah rules, but they are always valid structural positions)
    universe: set[str] = (
        {f["abbr"] for f in state["eligible_funds"]}
        | {h["abbr"] for h in port}
    )
    rl_by_abbr: dict[str, int] = {
        f["abbr"]: f.get("risk_level")
        for f in state["eligible_funds"]
    }
    # Also include structural funds that may have come from funds_by_abbr
    for h in port:
        abbr = h["abbr"]
        if abbr not in rl_by_abbr and abbr in funds_by_abbr:
            rl_by_abbr[abbr] = funds_by_abbr[abbr].get("risk_level")

    violations = check_invariants(port, profile, universe, rl_by_abbr)
    if violations:
        raise RuntimeError(
            f"build_portfolio invariant violations (build-time bug): {violations}"
        )

    return {
        "portfolio": port,
        "proposed_allocation": {
            "profile": profile,
            "holdings": port,
        },
    }

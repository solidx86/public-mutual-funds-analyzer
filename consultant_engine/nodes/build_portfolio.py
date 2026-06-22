"""build_portfolio node — composes the 4-fund portfolio with invariant gate.

Pipeline position: after macro_context (which runs after score_cfs).
Inputs:  state["eligible_funds"]  (universe/RL superset),
         state["filtered_funds"]  (Shariah + RL-ceiling compliant; gap candidates),
         state["client_profile"], state["cfs_scores"],
         state.get("macro_context")  (optional; exposure_gaps read from it)
Outputs: state["portfolio"], state["proposed_allocation"]
"""

from __future__ import annotations

from consultant_engine.invariants import CAP, check_invariants
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
    # Attach each candidate's top-5 holdings from the fund dict so dedup_overlap
    # can check holding overlap between candidates.
    core_cands = [
        {**s, "top5_holdings": funds_by_abbr.get(s["abbr"], {}).get("top5_holdings", [])}
        for s in scores
        if s["abbr"] not in STRUCTURAL
    ]
    deduped = dedup_overlap(core_cands)

    # --- build the base 4-fund portfolio ---
    portfolio_funds = build(deduped, profile, shariah)

    # --- satellite substitution (claims the single discretionary slot) ---
    portfolio_funds = alpha_outlier(portfolio_funds, scores, funds_by_abbr, profile, shariah)

    # --- exposure-gap pick (no-ops when satellite present or no gaps) ---
    gaps: list[str] = (state.get("macro_context") or {}).get("exposure_gaps", [])
    # Candidates come from filtered_funds — already Shariah- and risk-ceiling-
    # compliant — so a gap pick can never leak a non-Shariah / over-RL fund (I2).
    # exposure_gap_pick reads fund["returns"][...]["alpha"], present on every fund.
    portfolio_funds = exposure_gap_pick(
        portfolio_funds,
        candidates=state["filtered_funds"],
        gaps=gaps,
        profile=profile,
    )

    # --- invariant gate ---
    # Universe = eligible abbrs ∪ structural abbrs actually in the book
    # (structural funds may not appear in eligible_funds if they were filtered out
    # by risk/shariah rules, but they are always valid structural positions)
    universe: set[str] = (
        {f["abbr"] for f in state["eligible_funds"]}
        | {h["abbr"] for h in portfolio_funds}
    )
    rl_by_abbr: dict[str, int] = {
        f["abbr"]: f.get("risk_level")
        for f in state["eligible_funds"]
    }
    # Also include structural funds that may have come from funds_by_abbr
    for h in portfolio_funds:
        abbr = h["abbr"]
        if abbr not in rl_by_abbr and abbr in funds_by_abbr:
            rl_by_abbr[abbr] = funds_by_abbr[abbr].get("risk_level")

    violations = check_invariants(portfolio_funds, profile, universe, rl_by_abbr)
    if violations:
        raise RuntimeError(
            f"build_portfolio could not satisfy invariants for profile "
            f"{profile!r} (cap {CAP[profile]}): {violations}. The deterministic "
            f"clamp should make this unreachable for well-formed FundMaster data; "
            f"if you see it, the FundMaster or profile constraints are infeasible."
        )

    return {
        "portfolio": portfolio_funds,
        "proposed_allocation": {
            "profile": profile,
            "holdings": portfolio_funds,
        },
        # Persist the universe the gate re-validates against, so a re-approved
        # structural sleeve (outside eligible_funds) is not a spurious violation.
        "_universe": universe,
    }

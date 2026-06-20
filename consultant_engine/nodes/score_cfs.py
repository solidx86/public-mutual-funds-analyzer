from consultant_engine.state import ConsultantState
from consultant_engine.cfs import score_all


def score_cfs(state: ConsultantState) -> dict:
    """score_cfs node: CFS-score the filtered universe.

    Reads state["filtered_funds"] plus the client's risk_level and target return;
    returns {"cfs_scores": [...]} sorted by composite descending.
    """
    return {"cfs_scores": score_all(state["filtered_funds"],
                                    state["client_profile"]["risk_level"],
                                    state["client_profile"]["target_annual_return_pct"])}

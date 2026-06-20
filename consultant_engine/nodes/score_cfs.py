from consultant_engine.state import ConsultantState
from consultant_engine.cfs import score_all


def score_cfs(state: ConsultantState) -> dict:
    return {"cfs_scores": score_all(state["filtered_funds"],
                                    state["client_profile"]["risk_level"],
                                    state["client_profile"]["target_annual_return_pct"])}

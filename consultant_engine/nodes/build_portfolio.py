from consultant_engine.state import ConsultantState


def build_portfolio(state: ConsultantState) -> dict:
    return {"portfolio": [], "proposed_allocation": {}}

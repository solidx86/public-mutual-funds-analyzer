from consultant_engine.state import ConsultantState


def macro_context(state: ConsultantState) -> dict:
    return {"macro_context": {"events": []}}

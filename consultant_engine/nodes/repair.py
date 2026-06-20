from consultant_engine.state import ConsultantState


def repair(state: ConsultantState) -> dict:
    return {"repair_iterations": state.get("repair_iterations", 0) + 1}

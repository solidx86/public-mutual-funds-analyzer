from consultant_engine.state import ConsultantState
from consultant_engine.macro import MacroContext, load_fixture


def macro_context(state: ConsultantState) -> dict:
    mc = state.get("macro_context") or {}
    source = mc.get("source")
    if source in ("fixture", "none", None):
        return {"macro_context": load_fixture().model_dump()}
    return {"macro_context": MacroContext.model_validate(mc).model_dump()}

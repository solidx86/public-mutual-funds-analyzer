from consultant_engine.state import ConsultantState
from consultant_engine.macro import MacroContext, load_fixture


def macro_context(state: ConsultantState) -> dict:
    """macro_context node: resolve the macro context for the run.

    Preserves a live, non-empty contract (its events / exposure_gaps) when one is
    supplied; otherwise falls back to the bundled gapless fixture. Returns
    {"macro_context": {...}} as a plain dict.
    """
    mc = state.get("macro_context") or {}
    # Rule: preserve a live contract (validated, carrying its events AND
    # exposure_gaps) whenever it supplies a live payload; otherwise fall back to the
    # gapless default fixture. This keeps the CLI defaults ({"source":"none"|"fixture"})
    # and bare {} on the fixture path while letting a caller inject exposure_gaps.
    if mc.get("events") or mc.get("exposure_gaps"):
        return {"macro_context": MacroContext.model_validate(mc).model_dump()}
    return {"macro_context": load_fixture().model_dump()}

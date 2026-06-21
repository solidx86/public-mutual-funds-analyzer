from consultant_engine.state import ConsultantState
from consultant_engine.macro import MacroContext, fetch_live_macro, load_fixture


def macro_context(state: ConsultantState) -> dict:
    """macro_context node: resolve the macro context for the run.

    Resolution:
      * ``source == "live"``      -> the web-search agent (cache + fixture fallback,
                                     deterministic/offline-safe via fetch_live_macro).
      * a non-empty contract      -> preserved (its events / injected exposure_gaps).
      * otherwise                 -> the bundled gapless fixture.
    Returns ``{"macro_context": {...}}`` as a plain dict.
    """
    mc = state.get("macro_context") or {}
    if mc.get("source") == "live":
        ctx = fetch_live_macro(model=state.get("model") or "claude-sonnet-4-6")
        return {"macro_context": ctx.model_dump()}
    # A caller-supplied live contract (validated, carrying events AND/OR injected
    # exposure_gaps) is preserved; bare {} / {"source":"none"|"fixture"} → fixture.
    if mc.get("events") or mc.get("exposure_gaps"):
        return {"macro_context": MacroContext.model_validate(mc).model_dump()}
    return {"macro_context": load_fixture().model_dump()}

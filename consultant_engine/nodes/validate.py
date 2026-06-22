from consultant_engine.state import ConsultantState
from consultant_engine.rules.validation import (
    check_render_fidelity,
    validate_html,
    workbook_index,
)
from consultant_engine import __version__


def validate(state: ConsultantState) -> dict:
    """validate node: check the drafted HTML against the locked template + workbook,
    AND reconcile its Python-owned values against the engine's in-memory state.

    Reads state["proposal_html"] and state["fundmaster_path"]; returns
    {"violations": [...]} (empty when the proposal conforms).

    The workbook-passthrough checks (``validate_html``) are stateless and shared
    with the offline eval layer. ``check_render_fidelity`` is state-aware and runs
    here on EVERY validate pass (post-generate AND post-repair) — the repair pass
    round-trips the whole document through the LLM, so this is where a corrupted
    Python-owned number / label / allocation is caught, driving repair or failing
    the run if still unresolved.
    """
    idx = workbook_index(state["fundmaster_path"])
    violations = validate_html(state["proposal_html"], __version__, idx)
    violations += check_render_fidelity(state["proposal_html"], state)
    return {"violations": violations}

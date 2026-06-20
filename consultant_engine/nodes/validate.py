from consultant_engine.state import ConsultantState
from consultant_engine.rules.validation import validate_html, workbook_index
from consultant_engine import __version__


def validate(state: ConsultantState) -> dict:
    """validate node: check the drafted HTML against the locked template + workbook.

    Reads state["proposal_html"] and state["fundmaster_path"]; returns
    {"violations": [...]} (empty when the proposal conforms).
    """
    idx = workbook_index(state["fundmaster_path"])
    violations = validate_html(state["proposal_html"], __version__, idx)
    return {"violations": violations}

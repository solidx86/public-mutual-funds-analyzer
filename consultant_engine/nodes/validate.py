from consultant_engine.state import ConsultantState
from consultant_engine.rules.validation import validate_html, workbook_index
from consultant_engine import __version__


def validate(state: ConsultantState) -> dict:
    idx = workbook_index(state["fundmaster_path"])
    violations = validate_html(state["proposal_html"], __version__, idx)
    return {"violations": violations}

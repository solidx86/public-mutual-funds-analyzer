from consultant_engine.state import ConsultantState


def review_gate(state: ConsultantState) -> dict:
    return {}


def read_resume_payload(thread_id: str) -> dict:
    """Stub: Task 2.2 replaces this with real file-based resume payload reader."""
    return {"decision": "approve"}

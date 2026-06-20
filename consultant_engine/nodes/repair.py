from pathlib import Path

from consultant_engine.state import ConsultantState
from consultant_engine.llm import complete

_REPAIR_PROMPT = Path(__file__).resolve().parent.parent / "assets" / "prompts" / "repair.md"


def repair(state: ConsultantState) -> dict:
    prompt_template = _REPAIR_PROMPT.read_text()
    violations = state.get("violations", [])
    html = state.get("proposal_html", "")
    prompt = (
        f"{prompt_template}\n\n## Violations to fix\n{violations}\n\n"
        f"## Current proposal HTML\n{html}"
    )
    fixed = complete(prompt, model=state.get("model", "claude-sonnet-4-6"))
    return {
        "proposal_html": fixed,
        "repair_iterations": state.get("repair_iterations", 0) + 1,
    }

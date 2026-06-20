import json
from pathlib import Path
from pydantic import BaseModel


class MacroEvent(BaseModel):
    date: str
    theme: str
    claim: str
    source_url: str


class MacroContext(BaseModel):
    events: list[MacroEvent] = []


def load_fixture() -> MacroContext:
    p = Path(__file__).resolve().parent / "assets" / "macro_fixture.json"
    return MacroContext.model_validate(json.loads(p.read_text()))

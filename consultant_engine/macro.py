import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict


class MacroEvent(BaseModel):
    date: str
    theme: str
    claim: str
    source_url: str


class MacroContext(BaseModel):
    # extra="ignore" lets a live contract carry a routing-only "source" key without
    # tripping validation (it is not a model field).
    model_config = ConfigDict(extra="ignore")

    events: list[MacroEvent] = []
    exposure_gaps: list[str] = []


def load_fixture() -> MacroContext:
    p = Path(__file__).resolve().parent / "assets" / "macro_fixture.json"
    return MacroContext.model_validate(json.loads(p.read_text()))

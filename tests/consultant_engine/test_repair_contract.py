"""Guard: repair.md must reference only violation codes the validator can emit.

A repair rule for a code no validator produces is dead weight that advertises a
guarantee the engine does not provide (the NUMERIC_TRANSCRIPTION trap).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPAIR_MD = REPO_ROOT / "consultant_engine" / "assets" / "prompts" / "repair.md"
VALIDATION_PY = REPO_ROOT / "consultant_engine" / "rules" / "validation.py"

# Rule identifiers in the repair.md table that are NOT validation `code` literals.
# These are structural/skeleton names the prompt documents but the validator never emits.
_ALLOWED_NON_CODE = {
    "SLOT_UNRESOLVED",           # structural concept documented for context; validator emits unfilled_slot
    "COVER_META_CELLS",          # cover grid check handled by template rendering, not validation.py
    "COVER_FOOTER_SPANS",        # cover footer check handled by template rendering, not validation.py
    "FEE_TABLE_COLUMNS",         # fee table column check not yet wired into validation.py
    "JARGON_MISSING_DEFINITION", # jargon check not yet wired into validation.py
}


def _emittable_codes() -> set[str]:
    text = VALIDATION_PY.read_text()
    return {m.group(1) for m in re.finditer(r'"code":\s*"([A-Za-z_]+)"', text)}


def test_repair_md_references_no_unknown_code():
    repair_text = REPAIR_MD.read_text()
    # Extract ONLY the Rule column identifier from each table row:
    # rows look like "| `RULE_NAME` | ..." — match the first backtick-wrapped token per row.
    referenced = {
        m.group(1)
        for m in re.finditer(r"^\| `([A-Za-z][A-Za-z_]+)`", repair_text, re.MULTILINE)
    }
    emittable = {c.upper() for c in _emittable_codes()}
    unknown = {
        r for r in referenced
        if r.upper() not in emittable and r not in _ALLOWED_NON_CODE
    }
    assert not unknown, f"repair.md references rule codes the engine never emits: {unknown}"
    # NUMERIC_TRANSCRIPTION specifically must be gone from the file entirely.
    assert "NUMERIC_TRANSCRIPTION" not in repair_text

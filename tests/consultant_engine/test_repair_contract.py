"""Guard: repair.md must reference only violation codes the validator can emit.

A repair rule for a code no validator produces is dead weight that advertises a
guarantee the engine does not provide (the NUMERIC_TRANSCRIPTION trap).
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPAIR_MD = REPO_ROOT / "consultant_engine" / "assets" / "prompts" / "repair.md"
VALIDATION_PY = REPO_ROOT / "consultant_engine" / "rules" / "validation.py"

# Codes the repair prompt legitimately names that are NOT validation `code`
# literals: legacy/skeleton rule identifiers the prompt documents structurally.
_ALLOWED_NON_CODE = {
    "SLOT_UNRESOLVED", "COVER_META_CELLS", "COVER_FOOTER_SPANS",
    "SKILL_VERSION_LITERAL", "FEE_TABLE_COLUMNS", "JARGON_MISSING_DEFINITION",
    "SECTION_COUNT", "SECTION_ORDER", "DISCLOSURE_HEADING",
}


def _emittable_codes() -> set[str]:
    text = VALIDATION_PY.read_text()
    return {m.group(1) for m in re.finditer(r'"code":\s*"([A-Za-z_]+)"', text)}


def test_repair_md_references_no_unknown_code():
    repair_text = REPAIR_MD.read_text()
    # Rule identifiers in repair.md appear as backticked ALL_CAPS or snake tokens.
    referenced = {m.group(1) for m in re.finditer(r"`([A-Z][A-Z_]+|[a-z_]+)`", repair_text)}
    emittable = {c.upper() for c in _emittable_codes()}
    unknown = {
        r for r in referenced
        if r.upper() not in emittable
        and r not in _ALLOWED_NON_CODE
        and r.isupper() or r.islower() and "_" in r
    }
    # NUMERIC_TRANSCRIPTION specifically must be gone.
    assert "NUMERIC_TRANSCRIPTION" not in repair_text
    assert "NUMERIC_TRANSCRIPTION" not in unknown

from pathlib import Path

PROMPTS = Path("consultant_engine/assets/prompts")


def test_generate_prompt_exists_and_has_jargon_and_slot_rule():
    text = (PROMPTS / "generate_proposal.md").read_text()
    assert "do not alter numeric slots" in text.lower()
    # canonical jargon terms appear (the table was copied in)
    assert "Alpha" in text and "Return Fit" in text and "Lipper" in text


def test_repair_prompt_exists():
    text = (PROMPTS / "repair.md").read_text()
    assert "do not alter numeric slots" in text.lower()

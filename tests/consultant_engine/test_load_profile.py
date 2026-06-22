import json
from pathlib import Path

from consultant_engine.nodes.load_profile import load_profile


def test_experience_normalized_and_default_target():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000}})
    assert out["client_profile"]["experience"] == "new"      # profile is the sole owner of the tier
    assert out["client_profile"]["target_annual_return_pct"] == 5.0          # midpoint default


def test_experience_defaults_to_experienced_when_absent():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "shariah": None, "upfront_capital_rm": 5000}})
    assert out["client_profile"]["experience"] == "experienced"


def test_target_mismatch_note():
    out = load_profile({"client_profile": {
        "risk_level": "Conservative", "experience": "experienced",
        "shariah": None, "upfront_capital_rm": 100000, "target_annual_return_pct": 9.0}})
    assert "exceeds" in out["client_profile"]["target_note"].lower()


def test_client_name_defaults_to_empty_when_absent():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000}})
    assert out["client_profile"]["client_name"] == ""


def test_client_name_trimmed_and_internal_whitespace_collapsed():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "  Tan   Wei  Ming \n"}})
    assert out["client_profile"]["client_name"] == "Tan Wei Ming"


def test_client_name_whitespace_only_becomes_empty():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "   \t  "}})
    assert out["client_profile"]["client_name"] == ""


def test_client_name_control_chars_stripped():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "Tan\x00Wei"}})
    assert out["client_profile"]["client_name"] == "TanWei"


def test_client_name_length_capped_at_100():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": "A" * 200}})
    assert len(out["client_profile"]["client_name"]) == 100


def test_client_name_non_string_becomes_empty():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000, "client_name": 12345}})
    assert out["client_profile"]["client_name"] == ""


def test_shipped_profiles_declare_generic_client_name():
    prof_dir = Path(__file__).resolve().parents[2] / "data" / "profiles"
    files = list(prof_dir.glob("*.json"))
    assert files, "no sample profiles found"
    for p in files:
        prof = json.loads(p.read_text())
        assert prof.get("client_name", None) == "", f"{p.name} must declare client_name: ''"
        out = load_profile({"client_profile": prof})
        assert out["client_profile"]["client_name"] == ""

import re
from pathlib import Path

from consultant_engine.nodes.emit import emit

SKILL_VERSION = "1.27"  # extracted from the proposal_html stamp
SAMPLE = ('<html><body><div>fund-consultant v' + SKILL_VERSION + '</div>'
          '<h4>AI-Generated Document</h4></body></html>')


def test_emit_generic_when_no_name(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert re.fullmatch(
        r"FundProposal_generic_Moderate_\d{4}-\d{2}-\d{2}_v1\.27\.html", name), name


def test_emit_full_name_spaces_removed(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Aggressive", "client_name": "Tan Wei Ming"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert re.fullmatch(
        r"FundProposal_TanWeiMing_Aggressive_\d{4}-\d{2}-\d{2}_v1\.27\.html", name), name


def test_emit_punctuation_only_name_falls_back_to_generic(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate", "client_name": "!!!"},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert name.startswith("FundProposal_generic_Moderate_"), name


def test_emit_risk_spaces_removed(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderately Aggressive", "client_name": ""},
             "output_dir": str(tmp_path)}
    name = Path(emit(state)["output_path"]).name
    assert "_ModeratelyAggressive_" in name, name


def test_emit_writes_content_and_version_suffix(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate"},
             "output_dir": str(tmp_path)}
    p = emit(state)["output_path"]
    assert p.endswith("_v1.27.html")
    text = open(p).read()
    assert "AI-Generated Document" in text
    assert "fund-consultant v1.27" in text

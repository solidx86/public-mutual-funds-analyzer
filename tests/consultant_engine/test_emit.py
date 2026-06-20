from consultant_engine.nodes.emit import emit
import consultant_engine

SKILL_VERSION = "1.27"  # extracted from proposal_html stamp
SAMPLE = ('<html><body><div>fund-consultant v' + SKILL_VERSION + '</div>'
          '<h4>AI-Generated Document</h4></body></html>')

def test_emit_writes_versioned_file(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate"},
             "fundmaster_path": "output/fundmasters/PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
             "output_dir": str(tmp_path)}
    out = emit(state)
    p = out["output_path"]
    assert p.endswith("_v" + SKILL_VERSION + ".html")
    assert "FundProposal_Moderate_Jun2026" in p
    text = open(p).read()
    assert ("fund-consultant v" + SKILL_VERSION) in text
    assert "AI-Generated Document" in text

def test_emit_includes_client_lastname(tmp_path):
    state = {"proposal_html": SAMPLE,
             "client_profile": {"risk_level": "Moderate", "client_name": "Tan Wei Ming"},
             "fundmaster_path": "PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx",
             "output_dir": str(tmp_path)}
    out = emit(state)
    assert "_Ming_v" in out["output_path"]

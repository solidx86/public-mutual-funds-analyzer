from consultant_engine.macro import MacroContext, load_fixture
from consultant_engine.nodes.macro_context import macro_context


def test_contract_validates_dated_events():
    mc = MacroContext.model_validate({"events": [
        {"date": "2026-06-01", "theme": "rates", "claim": "BNM held OPR at 3.00%",
         "source_url": "https://example.com/bnm"}]})
    assert mc.events[0].theme == "rates"


def test_macro_context_node_normalizes(tmp_path):
    out = macro_context({"macro_context": {"source": "fixture"}})
    assert "events" in out["macro_context"]
    assert all({"date", "theme", "claim", "source_url"} <= set(e) for e in out["macro_context"]["events"])

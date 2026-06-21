"""Real-path prose fill: the LLM returns only a {slot_key: prose} JSON map and Python
substitutes fragments into the skeleton it owns — so the document structure can never be
broken by the model. (The old whole-document round-trip dropped every section against a
real model; these tests pin the robust replacement.)
"""
import consultant_engine.nodes.generate_proposal as gp


def _state():
    return {"client_profile": {"risk_level": "Moderate"}, "portfolio": [],
            "cfs_scores": [], "macro_context": {}, "model": "claude-sonnet-4-6"}


def test_prose_map_substitutes_and_falls_back_per_missing_key(monkeypatch):
    html = ('<p><!--slot:why.PIX--></p><ul><!--slot:watch.PIX--></ul>'
            '<p><!--slot:exec_summary.thesis--></p>')

    def fake(prompt, model=None, system=None):
        # only 2 of the 3 keys returned → the third must degrade per-slot, not crash
        return ('{"why.PIX": "Strong manager alpha.", "watch.PIX": "<li>Rates</li>"}',
                {"input_tokens": 10, "output_tokens": 5, "web_searches": 0, "cost_usd": 0.0})

    monkeypatch.setattr(gp, "complete_with_usage", fake)
    out = gp._fill_prose_slots_llm(html, _state())

    assert "<!--slot:" not in out                       # every slot consumed
    assert "Strong manager alpha." in out
    assert "<li>Rates</li>" in out
    assert "[exec_summary.thesis narrative]" in out      # missing key → placeholder, doc intact


def test_prose_map_bad_json_degrades_to_placeholders(monkeypatch):
    html = '<p><!--slot:why.PIX--></p>'
    monkeypatch.setattr(gp, "complete_with_usage",
                        lambda *a, **k: ("sorry, no JSON here",
                                         {"input_tokens": 1, "output_tokens": 1,
                                          "web_searches": 0, "cost_usd": 0.0}))
    out = gp._fill_prose_slots_llm(html, _state())
    assert out == "<p>[why.PIX narrative]</p>"           # no crash, structure preserved


def test_collect_prose_keys_is_unique_and_ordered():
    html = "<!--slot:a--><!--slot:b--><!--slot:a-->"
    assert gp._collect_prose_keys(html) == ["a", "b"]

"""Real-path prose fill: the LLM returns only ``@@@key@@@``-delimited prose blocks and
Python substitutes fragments into the skeleton it owns — so the document structure can
never be broken by the model. Delimiter framing (not JSON) because slot values are HTML:
embedded quotes/braces/newlines break JSON escaping (a real reply once parsed as 0/39).
"""
import consultant_engine.nodes.generate_proposal as gp


def _state():
    return {"client_profile": {"risk_level": "Moderate"}, "portfolio": [],
            "cfs_scores": [], "macro_context": {}, "model": "claude-sonnet-4-6"}


def _usage():
    return {"input_tokens": 10, "output_tokens": 5, "web_searches": 0, "cost_usd": 0.0}


def test_blocks_substitute_and_fall_back_per_missing_key(monkeypatch):
    html = ('<p><!--slot:why.PIX--></p><ul><!--slot:watch.PIX--></ul>'
            '<p><!--slot:exec_summary.thesis--></p>')
    # only 2 of the 3 keys returned → the third must degrade per-slot, not crash
    reply = "@@@why.PIX@@@\nStrong manager alpha.\n@@@watch.PIX@@@\n<li>Rates</li>\n"
    monkeypatch.setattr(gp, "complete_with_usage", lambda *a, **k: (reply, _usage()))
    out = gp._fill_prose_slots_llm(html, _state())

    assert "<!--slot:" not in out                       # every slot consumed
    assert "Strong manager alpha." in out
    assert "<li>Rates</li>" in out
    assert "[exec_summary.thesis narrative]" in out      # missing key → placeholder, doc intact


def test_no_markers_degrades_to_placeholders(monkeypatch):
    html = '<p><!--slot:why.PIX--></p>'
    monkeypatch.setattr(gp, "complete_with_usage",
                        lambda *a, **k: ("sorry, no markers here", _usage()))
    out = gp._fill_prose_slots_llm(html, _state())
    assert out == "<p>[why.PIX narrative]</p>"           # no crash, structure preserved


def test_parse_blocks_survives_html_that_breaks_json():
    # The exact payload class that broke JSON: quotes, braces, newlines in HTML values.
    text = ('@@@a@@@\n<a href="x">"q" {b}</a>\n'
            '@@@watch.PIX@@@\n<li>one</li>\n<li>two</li>')
    out = gp._parse_prose_blocks(text)
    assert out["a"] == '<a href="x">"q" {b}</a>'
    assert out["watch.PIX"] == "<li>one</li>\n<li>two</li>"


def test_collect_prose_keys_is_unique_and_ordered():
    html = "<!--slot:a--><!--slot:b--><!--slot:a-->"
    assert gp._collect_prose_keys(html) == ["a", "b"]

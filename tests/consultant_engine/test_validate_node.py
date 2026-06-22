"""Integration test: proposal produced by the real pipeline passes the real validator.

Task 4.2 — validate node.
"""
from consultant_engine.nodes.load_funds import load_funds
from consultant_engine.nodes.load_profile import load_profile
from consultant_engine.nodes.filter_universe import filter_universe
from consultant_engine.nodes.score_cfs import score_cfs
from consultant_engine.nodes.build_portfolio import build_portfolio
from consultant_engine.nodes.macro_context import macro_context
from consultant_engine.nodes.generate_proposal import generate_proposal
from consultant_engine.nodes.validate import validate


def _pipeline(fundmaster_4fund):
    s = {"client_profile": {"risk_level": "Moderate", "shariah": False},
         "fundmaster_path": fundmaster_4fund, "macro_context": {"source": "fixture"}}
    for step in (load_profile, load_funds, filter_universe, score_cfs,
                 macro_context, build_portfolio, generate_proposal):
        s.update(step(s))
    return s


def test_generated_proposal_validates_clean(fundmaster_4fund):
    s = _pipeline(fundmaster_4fund)
    out = validate(s)
    assert out["violations"] == [], out["violations"]


def test_broken_html_produces_violations(fundmaster_4fund):
    s = _pipeline(fundmaster_4fund)
    s["proposal_html"] = s["proposal_html"].replace("fund-consultant v", "fund-consultant vX")  # corrupt version stamp
    out = validate(s)
    assert out["violations"]


def test_named_client_validates_clean(fundmaster_4fund):
    s = {"client_profile": {"risk_level": "Moderate", "shariah": False,
                            "client_name": "Tan Wei Ming"},
         "fundmaster_path": fundmaster_4fund, "macro_context": {"source": "fixture"}}
    for step in (load_profile, load_funds, filter_universe, score_cfs,
                 macro_context, build_portfolio, generate_proposal):
        s.update(step(s))
    assert 'class="cover-prepared-for"' in s["proposal_html"]
    out = validate(s)
    assert out["violations"] == [], out["violations"]

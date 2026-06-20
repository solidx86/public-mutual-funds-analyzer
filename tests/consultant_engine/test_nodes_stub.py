from consultant_engine.nodes import (
    load_profile,
    load_funds,
    filter_universe,
    score_cfs,
    build_portfolio,
    review_gate,
    macro_context,
    generate_proposal,
    validate,
    repair,
    emit,
)


def test_stub_nodes_return_dict():
    """Verify all stub nodes return dicts (sentinels for skeleton test)."""
    assert isinstance(load_profile.load_profile({}), dict)
    assert isinstance(load_funds.load_funds({}), dict)
    assert isinstance(filter_universe.filter_universe({}), dict)
    assert isinstance(score_cfs.score_cfs({}), dict)
    assert isinstance(build_portfolio.build_portfolio({}), dict)
    assert isinstance(review_gate.review_gate({}), dict)
    assert isinstance(macro_context.macro_context({}), dict)
    assert isinstance(generate_proposal.generate_proposal({}), dict)
    assert isinstance(validate.validate({}), dict)
    assert isinstance(repair.repair({}), dict)
    assert isinstance(emit.emit({"proposal_html": "<html></html>"}), dict)


def test_emit_returns_output_path():
    """Verify emit stub returns output_path key."""
    result = emit.emit({"proposal_html": "<html></html>"})
    assert "output_path" in result

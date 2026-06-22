"""LangGraph assembly for the consultant engine.

Wires the pipeline nodes into a directed graph and compiles it against a
checkpointer (SQLite in the CLI). Flow:

    load_profile -> load_funds -> filter_universe -> score_cfs -> macro_context
    -> build_portfolio -> review_gate -> generate_proposal -> validate
       -> (emit | repair -> validate | fail)

The review gate pauses for human edits via LangGraph ``interrupt``; the
validate/repair loop self-corrects the draft up to MAX_REPAIR times before
failing loudly rather than emitting a broken proposal. ``build_graph`` is the
entry point used by the CLI.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from consultant_engine.state import ConsultantState
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
from consultant_engine.nodes.review_gate import build_proposed_allocation, write_artifact, apply_resume

MAX_REPAIR = 3
MAX_REVIEW_ROUNDS = 3


def _review(state: ConsultantState) -> dict:
    """Review-gate node: pause for consultant edits, then validate and apply them.

    With ``no_review`` set, returns immediately (auto-approve for evals/CI/batch).
    Otherwise writes the review artifact, pauses via ``interrupt``, and applies the
    resumed decision. Each edit that reintroduces a violation re-pauses, bounded by
    MAX_REVIEW_ROUNDS.

    Returns:
        {} to approve as-is, or {"portfolio": ...} with the corrected allocation.

    Raises:
        RuntimeError: edits still violated invariants after MAX_REVIEW_ROUNDS.
    """
    if state.get("no_review"):
        return {}                       # auto-approve path (evals / CI / batch)

    artifact = build_proposed_allocation(state)
    write_artifact("data/review", state["thread_id"], artifact)
    decision = interrupt(artifact)      # pauses; resumed value returned here
    result = apply_resume(state, decision)

    # Re-pause on each violating edit and apply the correction, bounded.
    rounds = 0
    while result.get("violations") and rounds < MAX_REVIEW_ROUNDS:
        rounds += 1
        artifact = build_proposed_allocation(state)
        artifact["review"]["violations"] = result["violations"]
        write_artifact("data/review", state["thread_id"], artifact)
        decision = interrupt(artifact)      # re-pause — and USE this resume value
        result = apply_resume(state, decision)

    if result.get("violations"):
        # Still violating after the cap — fail loudly, never emit a broken proposal.
        raise RuntimeError(
            f"review edits did not validate after {MAX_REVIEW_ROUNDS} rounds: "
            f"{result['violations']}"
        )
    return result          # {} (approve-as-is) or {"portfolio": ...}


def _after_validate(state: ConsultantState) -> str:
    """Route after validation: 'emit' if clean, else 'repair' until MAX_REPAIR, then 'fail'."""
    if not state.get("violations"):
        return "emit"
    if state.get("repair_iterations", 0) >= MAX_REPAIR:
        return "fail"
    return "repair"


def _fail_loudly(state: ConsultantState) -> dict:
    """Terminal node: raise when validation never converged (never emit a broken proposal)."""
    raise RuntimeError(f"validation did not converge: {state.get('violations')}")


def build_graph(checkpointer):
    """Assemble and compile the consultant pipeline graph.

    Args:
        checkpointer: A LangGraph checkpointer (e.g. SqliteSaver) that persists
            state so the review-gate interrupt can pause and later resume.

    Returns:
        The compiled graph, ready for ``.invoke``.
    """
    g = StateGraph(ConsultantState)
    g.add_node("load_profile", load_profile.load_profile)
    g.add_node("load_funds", load_funds.load_funds)
    g.add_node("filter_universe", filter_universe.filter_universe)
    g.add_node("score_cfs", score_cfs.score_cfs)
    g.add_node("build_portfolio", build_portfolio.build_portfolio)
    g.add_node("review_gate", _review)
    g.add_node("macro_context", macro_context.macro_context)
    g.add_node("generate_proposal", generate_proposal.generate_proposal)
    g.add_node("validate", validate.validate)
    g.add_node("repair", repair.repair)
    g.add_node("emit", emit.emit)
    g.add_node("fail", _fail_loudly)

    g.add_edge(START, "load_profile")
    g.add_edge("load_profile", "load_funds")
    g.add_edge("load_funds", "filter_universe")
    g.add_edge("filter_universe", "score_cfs")
    # macro_context runs BEFORE build_portfolio so a contract's exposure_gaps reach
    # the gap-substitution branch (I2). The review gate still pauses after the final
    # allocation (build), and generate_proposal still has macro_context available.
    g.add_edge("score_cfs", "macro_context")
    g.add_edge("macro_context", "build_portfolio")
    g.add_edge("build_portfolio", "review_gate")
    g.add_edge("review_gate", "generate_proposal")
    g.add_edge("generate_proposal", "validate")
    g.add_conditional_edges(
        "validate",
        _after_validate,
        {"repair": "repair", "emit": "emit", "fail": "fail"},
    )
    g.add_edge("repair", "validate")
    g.add_edge("emit", END)
    g.add_edge("fail", END)
    return g.compile(checkpointer=checkpointer)

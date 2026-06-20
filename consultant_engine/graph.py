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


def _review(state: ConsultantState) -> dict:
    if state.get("no_review"):
        return {}                       # auto-approve path (evals / CI / batch)
    artifact = build_proposed_allocation(state)
    write_artifact("data/review", state["thread_id"], artifact)
    decision = interrupt(artifact)      # pauses; resumed value returned here
    result = apply_resume(state, decision)
    if result.get("violations"):
        if state.get("no_review"):
            raise RuntimeError(f"resume edit failed re-validation: {result['violations']}")
        # review ON: re-pause with a violations-annotated artifact
        artifact2 = build_proposed_allocation(state)
        artifact2["review"]["violations"] = result["violations"]
        write_artifact("data/review", state["thread_id"], artifact2)
        interrupt(artifact2)
    return result          # {} (approve-as-is) or {"portfolio": ...}


def _after_validate(state: ConsultantState) -> str:
    if not state.get("violations"):
        return "emit"
    if state.get("repair_iterations", 0) >= MAX_REPAIR:
        return "fail"
    return "repair"


def _fail_loudly(state: ConsultantState) -> dict:
    raise RuntimeError(f"validation did not converge: {state.get('violations')}")


def build_graph(checkpointer):
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
    g.add_edge("score_cfs", "build_portfolio")
    g.add_edge("build_portfolio", "review_gate")
    g.add_edge("review_gate", "macro_context")
    g.add_edge("macro_context", "generate_proposal")
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

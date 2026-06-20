# Primitives → LangGraph Mapping

_Capstone learning artifact — Track 0: Headless Consultant Engine_

---

## Why the rewrite

The old interactive `fund-consultant` skill was a prose procedure: a sequence of
natural-language instructions that Claude followed step-by-step in a chat session.
Every "primitive" — conditional branching, retry loops, shared state, human
checkpoints — was implicit, carried in the prompt text and maintained by the
conversation context window. There was no graph, no checkpointer, no testable
unit; the whole thing existed only while the session was alive.

The new `consultant_engine/` package gives each of those primitives a
**first-class, inspectable expression** in LangGraph. The graph is compiled once,
persisted to SQLite, and can be paused and resumed across processes. Every node is
a plain Python function with a typed input/output contract, so individual steps are
unit-testable without running the full pipeline.

---

## The determinism boundary

A second architectural principle shapes the whole engine: **Python owns all
numbers; the LLM writes prose**. The proposal skeleton is a locked HTML template
with two kinds of placeholders:

- `data-slot="KEY"` — numeric/factual slots filled deterministically by
  `templates.fill_slots` (CFS scores, allocation percentages, return figures).
  `fill_slots` raises `ValueError` on any unfilled slot, so a silent gap is
  impossible.
- `<!--slot:KEY-->` prose markers — left untouched by `fill_slots` and handed to
  the LLM in `generate_proposal`. The LLM writes narrative _into_ a document where
  every number is already correct; it cannot hallucinate a figure because there are
  no numeric placeholders left for it to fill.

After generation the `validate → repair` loop checks structural conformance — slot
completeness, disclosure rules, CFS recomputation. This guards _transcription_
(did the LLM drop a required section?), not arithmetic (the numbers were already
correct before the LLM touched the document).

---

## Primitive → LangGraph mapping

| Old primitive (skill procedure) | LangGraph expression | Realization in `consultant_engine/` |
|---|---|---|
| **Conditional dispatch** — "if valid, emit; if not, repair; if repair cap hit, fail" | `add_conditional_edges` with a routing function | `graph.py` — `build_graph` calls `g.add_conditional_edges("validate", _after_validate, {"repair": "repair", "emit": "emit", "fail": "fail"})` (line 76–80); routing logic in `_after_validate` (line 40–45) |
| **Retry-until-valid loop** — keep asking the LLM to fix the proposal until it passes, up to a cap | `validate ⇄ repair` cycle; `MAX_REPAIR = 3` guards infinite loops | `graph.py` — `g.add_edge("repair", "validate")` (line 81) + `_after_validate` checks `repair_iterations >= MAX_REPAIR`; `nodes/repair.py` — `repair()` increments `repair_iterations` and returns corrected `proposal_html` |
| **Shared-state blackboard** — all steps read/write a single mutable context dict | `ConsultantState` TypedDict; channels are the typed keys | `state.py` — `ConsultantState` TypedDict (line 45) carries all pipeline state: `eligible_funds`, `portfolio`, `cfs_scores`, `proposal_html`, `violations`, `repair_iterations`, etc. |
| **Planner–executor split** — compute the plan (what funds, what weights), then produce the document | Separate compute node (planner) feeds a generation node (executor) | `nodes/build_portfolio.py` — `build_portfolio()` assembles and invariant-gates the portfolio plan; `nodes/generate_proposal.py` — `generate_proposal()` executes it into HTML |
| **Agent handoff / subgraph seam** — hand off to a specialist for macro research, receive a typed result back | Typed contract boundary; future subgraph replaces the fixture loader | `macro.py` — `MacroContext` Pydantic model (line 13) is the contract; `nodes/macro_context.py` — `macro_context()` resolves source (`"fixture"` / `"none"` / validated dict) and writes `{"macro_context": ...}` into state — the seam where ENH-6's real researcher agent will plug in |
| **Human-in-the-loop** — pause, let the consultant edit the allocation, resume | `interrupt()` + SQLite checkpointer (exit-and-resume across processes) | `graph.py` — `_review()` calls `interrupt(artifact)` (line 27) after writing a JSON+HTML review artifact; `cli.py` — `SqliteSaver` (line 3, line 26–29) persists the checkpoint; `--resume` flag triggers `app.invoke(Command(resume=...))` (line 35) |
| **Tool use** — read external data sources (FundMaster workbook) as a deterministic action | Deterministic openpyxl read inside a node; no LLM involved | `nodes/load_funds.py` — `load_funds()` reads the FundMaster `.xlsx` via `openpyxl` (line 14–134); the determinism boundary means the LLM never sees raw spreadsheet data |
| **Deterministic-numbers / LLM-prose split** — Python computes all figures; LLM authors narrative into a pre-filled document | Locked skeleton + `fill_slots` (numeric pass) then prose-slot authoring | `templates.py` — `fill_slots()` (line 128) fills `data-slot` elements and raises on any missing key; `nodes/generate_proposal.py` — `generate_proposal()` calls `fill_slots` first (line 365) then `_fill_prose_slots_llm` / `_fill_prose_slots_fake` for `<!--slot:-->` markers |

---

_The HTML companion (`primitives-to-langgraph.html`) is generated from this
markdown file, per the repo convention that every spec/plan/note ships a
standalone self-contained HTML copy alongside it._

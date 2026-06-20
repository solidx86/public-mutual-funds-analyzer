# Track 0 — Headless Consultant Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `fund-consultant` generate→validate→repair procedure as a runnable, headless LangGraph `StateGraph` (Python package `consultant_engine/`) that emits a version-stamped HTML proposal passing `tests/test_proposal_validation.py`, then retire the skill bundle.

**Architecture:** One linear graph — `load_profile → load_funds(+1b) → filter_universe → score_cfs → build_portfolio → [interrupt: consultant review] → macro_context → generate_proposal → validate ⇄ repair → emit`. Python owns all numbers (deterministic ground truth); the LLM writes prose and fills a locked, slotted HTML skeleton. Built horizontally in four layers — L0 skeleton+stubs, L1 deterministic compute, L2 LLM generation, L3 validate/repair + HITL — each green before the next.

**Tech Stack:** Python 3 · LangGraph `StateGraph` + SQLite checkpointer (`langgraph-checkpoint-sqlite`) · Anthropic SDK · pydantic (contracts) · openpyxl (FundMaster read) · pytest. Source spec: `docs/superpowers/specs/2026-06-19-track0-headless-consultant-engine-design.md`.

---

## Conventions for every task

- **Run from the repo root.** All paths below are repo-root-relative.
- **TDD:** write the failing test, run it red, implement minimal code, run it green, commit.
- **Test command base:** `python3 -m pytest <path> -v` (the repo uses bare `pytest` in CI; `python3 -m pytest` is equivalent and venv-safe).
- **Commit style:** `git commit -m "feat(engine): <what>"` (or `test(engine):`, `chore(engine):`). Co-author line not required for local commits.
- **Never touch** the live gitignored dirs (`output/fund_proposals/`, `output/fundmasters/`) — tests and runs write under temp dirs or `output/examples/`.

## File structure (locked here)

```
consultant_engine/
  __init__.py            # __version__ = "0.1.0"  (the new version source)
  __main__.py            # `python -m consultant_engine` → cli.main()
  cli.py                 # argparse: --profile --fundmaster --macro -o --no-review --resume --model
  state.py               # TypedDict state schema + sub-types
  graph.py               # build_graph(checkpointer) → compiled StateGraph
  llm.py                 # Anthropic wrapper, stub-able via env/inject
  cfs.py                 # pure CFS math (dims, weights, normalize, compose)
  portfolio.py           # pure allocation (templates, structural, diversification, exposure-gap, satellite)
  invariants.py          # deterministic invariant checks (sum, ceiling, concentration, structural, eligibility, count)
  macro.py               # macro contract (pydantic) + fixture/producer
  templates.py           # slot-fill + deterministic structural-card render
  nodes/
    __init__.py
    load_profile.py  load_funds.py  filter_universe.py  score_cfs.py
    build_portfolio.py  review_gate.py  macro_context.py
    generate_proposal.py  validate.py  repair.py  emit.py
  rules/
    __init__.py
    validation.py        # SHARED rule module — the checks as pure fns → violations[]
  assets/
    design_system.css            # moved verbatim from fund-consultant-skill/references/
    proposal_skeleton.html       # slotted skeleton derived from proposal_template.md
    prompts/generate_proposal.md
    prompts/repair.md
tests/consultant_engine/
  conftest.py            # tiny FundMaster fixture builder, profile + macro fixtures
  test_*.py              # one per module
  fixtures/proposal_good.html  proposal_bad_section.html  proposal_bad_cfs.html
data/review/             # runtime artifacts (gitignored)
```

`data/review/` and the engine's runtime outputs are gitignored — add to `.gitignore` in Task 0.1.

---

# Phase L0 — Graph skeleton + stubs (runs end-to-end)

Goal: a compiled graph with every node stubbed, a CLI that runs it start→finish, the SQLite checkpointer wired, and the interrupt present as a no-op. No real logic yet.

### Task 0.1: Dependencies + package scaffold

**Files:**
- Modify: `requirements.txt`
- Create: `consultant_engine/__init__.py`, `consultant_engine/nodes/__init__.py`, `consultant_engine/rules/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add dependencies**

Append to `requirements.txt`:

```
langgraph>=0.2
langgraph-checkpoint-sqlite>=2.0
anthropic>=0.40
pydantic>=2.7
```

- [ ] **Step 2: Install**

Run: `pip install -r requirements.txt`
Expected: installs langgraph, anthropic, pydantic without error.

- [ ] **Step 3: Create package files**

`consultant_engine/__init__.py`:
```python
"""Headless Public Mutual fund-consultant engine (Track 0)."""

__version__ = "0.1.0"
```
`consultant_engine/nodes/__init__.py` and `consultant_engine/rules/__init__.py`: empty files.

- [ ] **Step 4: Gitignore runtime artifacts**

Append to `.gitignore`:
```
data/review/
```

- [ ] **Step 5: Verify import**

Run: `python3 -c "import consultant_engine; print(consultant_engine.__version__)"`
Expected: prints `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt consultant_engine/ .gitignore
git commit -m "chore(engine): scaffold consultant_engine package + deps"
```

### Task 0.2: State schema

**Files:**
- Create: `consultant_engine/state.py`
- Test: `tests/consultant_engine/test_state.py`

- [ ] **Step 1: Write the failing test**

`tests/consultant_engine/test_state.py`:
```python
from consultant_engine.state import ConsultantState, ClientProfile

def test_state_is_constructable_with_partial_keys():
    # TypedDict total=False → partial construction is legal at runtime
    s: ConsultantState = {"thread_id": "t1", "repair_iterations": 0}
    assert s["thread_id"] == "t1"

def test_client_profile_keys():
    p: ClientProfile = {
        "risk_level": "Moderate", "shariah": False, "experience": "experienced",
        "upfront_capital_rm": 50000.0, "e_target": 5.0, "goals": None,
    }
    assert p["risk_level"] == "Moderate"
```

- [ ] **Step 2: Run red**

Run: `python3 -m pytest tests/consultant_engine/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: consultant_engine.state`

- [ ] **Step 3: Implement**

`consultant_engine/state.py`:
```python
from typing import TypedDict, Literal, Optional

class ClientProfile(TypedDict):
    risk_level: str          # Conservative|Moderate|Moderately Aggressive|Aggressive
    shariah: Optional[bool]  # True | False | None (no preference)
    experience: Literal["new", "experienced"]
    upfront_capital_rm: float
    e_target: float          # percent p.a., e.g. 5.0
    goals: Optional[str]

class Fund(TypedDict, total=False):
    abbr: str
    name: str
    shariah: bool
    fund_type: str
    risk_level: int
    status: str              # "Qualified" | "Disqualified"
    weighted_alpha: float
    returns: dict            # {"ytd":{"fund","bench","alpha"}, "1y":..., "3y":..., "5y":..., "10y":...}
    ae: dict                 # {"ytd","1y","3y","5y","10y"}
    assets: dict             # {"dom_equity","for_equity","fi","mm","deposits","other"}
    geo: dict                # %/country, exact FundMaster headers: {"USA","Taiwan","Korea","Japan","France","Germany","China","Singapore","Netherlands","Indonesia","Australia","Geo Other"}
    top5: list
    vf: float
    lipper_class: str
    benchmark: str
    drawdown: Optional[float]
    days_from_ath: Optional[int]

class CFSScore(TypedDict):
    abbr: str
    alpha_n: float
    returnfit_n: float
    efficiency_n: float
    momentum_n: float
    composite: float
    weights: dict            # {"alpha","returnfit","efficiency","momentum"}
    derived_class: str       # Equity-equivalent | Balanced | Defensive

class Holding(TypedDict):
    abbr: str
    role: str                # core | structural:gold | structural:money_market | satellite | exposure_gap
    allocation_pct: float

class ConsultantState(TypedDict, total=False):
    # inputs
    client_profile: ClientProfile
    macro_context: dict
    fundmaster_path: str
    thread_id: str
    no_review: bool
    model: str
    output_dir: str
    # computed
    eligible_funds: list
    filtered_funds: list
    cfs_scores: list
    portfolio: list
    fees: dict
    # review
    proposed_allocation: dict
    resume_payload: dict
    # generation
    proposal_html: str
    # validation
    violations: list
    repair_iterations: int
    # output
    output_path: str
```

- [ ] **Step 4: Run green**

Run: `python3 -m pytest tests/consultant_engine/test_state.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add consultant_engine/state.py tests/consultant_engine/test_state.py
git commit -m "feat(engine): typed state schema"
```

### Task 0.3: Stub all nodes

**Files:**
- Create: `consultant_engine/nodes/{load_profile,load_funds,filter_universe,score_cfs,build_portfolio,review_gate,macro_context,generate_proposal,validate,repair,emit}.py`
- Test: `tests/consultant_engine/test_nodes_stub.py`

Each node is a function `def <name>(state: ConsultantState) -> dict:` returning a partial state update. Stubs return a sentinel so the skeleton test can prove the node ran.

- [ ] **Step 1: Write the failing test**

```python
from consultant_engine.nodes import load_profile, score_cfs, emit

def test_stub_nodes_return_dict():
    assert isinstance(load_profile.load_profile({}), dict)
    assert isinstance(score_cfs.score_cfs({}), dict)
    assert "output_path" in emit.emit({"proposal_html": "<html></html>"})
```

- [ ] **Step 2: Run red**

Run: `python3 -m pytest tests/consultant_engine/test_nodes_stub.py -v`
Expected: FAIL — import errors.

- [ ] **Step 3: Implement stubs**

Pattern for each file (example `consultant_engine/nodes/score_cfs.py`):
```python
from consultant_engine.state import ConsultantState

def score_cfs(state: ConsultantState) -> dict:
    return {"cfs_scores": []}
```
Per-node stub return values:
- `load_profile` → `{"client_profile": {"experience": "experienced"}}`
- `load_funds` → `{"eligible_funds": []}`
- `filter_universe` → `{"filtered_funds": []}`
- `score_cfs` → `{"cfs_scores": []}`
- `build_portfolio` → `{"portfolio": [], "proposed_allocation": {}}`
- `review_gate` → `{}`  (interrupt wired in graph, not here, at L0)
- `macro_context` → `{"macro_context": {"events": []}}`
- `generate_proposal` → `{"proposal_html": "<html><body>stub</body></html>"}`
- `validate` → `{"violations": []}`
- `repair` → `{"repair_iterations": state.get("repair_iterations", 0) + 1}`
- `emit` → writes nothing yet, returns `{"output_path": "STUB"}`

- [ ] **Step 4: Run green**

Run: `python3 -m pytest tests/consultant_engine/test_nodes_stub.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add consultant_engine/nodes/ tests/consultant_engine/test_nodes_stub.py
git commit -m "feat(engine): stub all graph nodes"
```

### Task 0.4: Graph wiring + checkpointer + interrupt (no-op)

**Files:**
- Create: `consultant_engine/graph.py`
- Test: `tests/consultant_engine/test_graph_skeleton.py`

- [ ] **Step 1: Write the failing test**

```python
from langgraph.checkpoint.memory import MemorySaver
from consultant_engine.graph import build_graph

def test_graph_runs_end_to_end_with_stubs():
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}}
    # no_review=True skips the interrupt so a single invoke runs to emit
    out = app.invoke(
        {"thread_id": "t1", "no_review": True, "fundmaster_path": "x", "client_profile": {}},
        cfg,
    )
    assert out["output_path"] == "STUB"
    assert out["proposal_html"]
```

- [ ] **Step 2: Run red**

Run: `python3 -m pytest tests/consultant_engine/test_graph_skeleton.py -v`
Expected: FAIL — no `build_graph`.

- [ ] **Step 3: Implement the graph**

`consultant_engine/graph.py`:
```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from consultant_engine.state import ConsultantState
from consultant_engine.nodes import (
    load_profile, load_funds, filter_universe, score_cfs, build_portfolio,
    review_gate, macro_context, generate_proposal, validate, repair, emit,
)

MAX_REPAIR = 3

def _review(state: ConsultantState) -> dict:
    if state.get("no_review"):
        return {}                       # auto-approve path (evals / CI / batch)
    decision = interrupt(state.get("proposed_allocation", {}))  # pauses; resumed value returned here
    return {"resume_payload": decision} if decision else {}

def _after_validate(state: ConsultantState) -> str:
    if not state.get("violations"):
        return "emit"
    if state.get("repair_iterations", 0) >= MAX_REPAIR:
        return "fail"
    return "repair"

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
    g.add_conditional_edges("validate", _after_validate,
                            {"repair": "repair", "emit": "emit", "fail": "fail"})
    g.add_edge("repair", "validate")
    g.add_edge("emit", END)
    g.add_edge("fail", END)
    return g.compile(checkpointer=checkpointer)

def _fail_loudly(state: ConsultantState) -> dict:
    raise RuntimeError(f"validation did not converge: {state.get('violations')}")
```

Note: the **experience branch** is handled *inside* `generate_proposal` (prompt selection, keyed on `client_profile["experience"]`), not as a graph edge — keeps topology to one conditional (the validate loop) plus the interrupt, per spec §4.

- [ ] **Step 4: Run green**

Run: `python3 -m pytest tests/consultant_engine/test_graph_skeleton.py -v`
Expected: PASS

- [ ] **Step 5: Add the interrupt/resume test**

Append:
```python
import pytest
from langgraph.types import Command

def test_interrupt_pauses_then_resumes():
    app = build_graph(MemorySaver())
    cfg = {"configurable": {"thread_id": "t2"}}
    out = app.invoke({"thread_id": "t2", "client_profile": {}, "fundmaster_path": "x"}, cfg)
    assert "__interrupt__" in out                      # paused at review_gate
    out2 = app.invoke(Command(resume={"decision": "approve"}), cfg)
    assert out2["output_path"] == "STUB"               # resumed to completion
```

Run: `python3 -m pytest tests/consultant_engine/test_graph_skeleton.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Commit**

```bash
git add consultant_engine/graph.py tests/consultant_engine/test_graph_skeleton.py
git commit -m "feat(engine): wire graph + checkpointer + review interrupt"
```

### Task 0.5: CLI entry (invoke + resume)

**Files:**
- Create: `consultant_engine/cli.py`, `consultant_engine/__main__.py`
- Test: `tests/consultant_engine/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
import json, subprocess, sys
from pathlib import Path

def test_cli_runs_with_no_review(tmp_path):
    prof = tmp_path / "p.json"
    prof.write_text(json.dumps({
        "risk_level": "Moderate", "shariah": False, "experience": "experienced",
        "upfront_capital_rm": 50000, "e_target": 5.0
    }))
    r = subprocess.run(
        [sys.executable, "-m", "consultant_engine",
         "--profile", str(prof), "--fundmaster", "x.xlsx",
         "--macro", "none", "--no-review", "-o", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Run red** → FAIL (no CLI).

- [ ] **Step 3: Implement**

`consultant_engine/cli.py`:
```python
import argparse, json, sqlite3, sys
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from consultant_engine.graph import build_graph

def _thread_id(args) -> str:
    if args.resume:
        return args.resume
    stem = Path(args.profile).stem
    return f"{stem}"

def main(argv=None) -> int:
    ap = argparse.ArgumentParser("consultant_engine")
    ap.add_argument("--profile")
    ap.add_argument("--fundmaster")
    ap.add_argument("--macro", default="none")
    ap.add_argument("-o", "--output", default="output/fund_proposals")
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--resume")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args(argv)

    Path("data/review").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect("data/review/checkpoints.sqlite", check_same_thread=False)
    saver = SqliteSaver(conn)
    app = build_graph(saver)
    cfg = {"configurable": {"thread_id": _thread_id(args)}}

    if args.resume:
        from langgraph.types import Command
        from consultant_engine.nodes.review_gate import read_resume_payload
        out = app.invoke(Command(resume=read_resume_payload(args.resume)), cfg)
    else:
        profile = json.loads(Path(args.profile).read_text())
        out = app.invoke({
            "thread_id": cfg["configurable"]["thread_id"],
            "client_profile": profile,
            "fundmaster_path": args.fundmaster,
            "macro_context": {"source": args.macro},
            "no_review": args.no_review,
            "model": args.model,
            "output_dir": args.output,
        }, cfg)

    if "__interrupt__" in out:
        tid = cfg["configurable"]["thread_id"]
        print(f"  ⏸  Paused for consultant review.\n"
              f"      Edit  data/review/{tid}.json\n"
              f"      Resume: python -m consultant_engine --resume {tid}")
        return 0
    print(f"  ✓  Proposal written to {out.get('output_path')}")
    return 0
```
`consultant_engine/__main__.py`:
```python
import sys
from consultant_engine.cli import main
sys.exit(main())
```
For L0, add a temporary `read_resume_payload` stub in `review_gate.py` returning `{"decision": "approve"}`; Task 2.2 replaces it.

- [ ] **Step 4: Run green** → `python3 -m pytest tests/consultant_engine/test_cli.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add consultant_engine/cli.py consultant_engine/__main__.py consultant_engine/nodes/review_gate.py tests/consultant_engine/test_cli.py
git commit -m "feat(engine): CLI entry with invoke + resume wiring"
```

**L0 exit check:** `python3 -m pytest tests/consultant_engine/ -v` all green; `python -m consultant_engine --profile <p> --fundmaster x --no-review -o /tmp` exits 0.

---

# Phase L1 — Deterministic compute (full parity)

Goal: real Python for every compute node, unit-TDD'd against the formulas in `fund-consultant-skill/SKILL.md`. The LLM nodes stay stubbed. **e-Series / shortlist is OUT** (spec decision 6) — one linear build for all clients.

### Task 1.1: `load_profile` node

Parses the client-profile dict, **normalizes `experience` in-place** (defaults to `"experienced"` when absent — `client_profile` is the single owner of the tier; there is no separate `experience_tier` channel), defaults `e_target` from the profile midpoint when absent, attaches a mismatch note when `e_target` exceeds the profile ceiling.

**Files:** `consultant_engine/nodes/load_profile.py`, `tests/consultant_engine/test_load_profile.py`

Reference (SKILL.md Step 0): midpoints Conservative 3.5, Moderate 5, Moderately Aggressive 7, Aggressive 9; ceilings 4/6/8/10; >10% always "unrealistic".

- [ ] **Step 1: Failing test**
```python
from consultant_engine.nodes.load_profile import load_profile

def test_experience_normalized_and_default_target():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "experience": "new", "shariah": None,
        "upfront_capital_rm": 5000}})
    assert out["client_profile"]["experience"] == "new"      # profile is the sole owner of the tier
    assert out["client_profile"]["e_target"] == 5.0          # midpoint default

def test_experience_defaults_to_experienced_when_absent():
    out = load_profile({"client_profile": {
        "risk_level": "Moderate", "shariah": None, "upfront_capital_rm": 5000}})
    assert out["client_profile"]["experience"] == "experienced"

def test_target_mismatch_note():
    out = load_profile({"client_profile": {
        "risk_level": "Conservative", "experience": "experienced",
        "shariah": None, "upfront_capital_rm": 100000, "e_target": 9.0}})
    assert "exceeds" in out["client_profile"]["target_note"].lower()
```
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement**
```python
from consultant_engine.state import ConsultantState

MIDPOINT = {"Conservative": 3.5, "Moderate": 5.0,
            "Moderately Aggressive": 7.0, "Aggressive": 9.0}
CEILING = {"Conservative": 4.0, "Moderate": 6.0,
           "Moderately Aggressive": 8.0, "Aggressive": 10.0}

def load_profile(state: ConsultantState) -> dict:
    p = dict(state["client_profile"])
    rl = p["risk_level"]
    p.setdefault("experience", "experienced")   # normalize the tier into the profile (single owner)
    p.setdefault("e_target", MIDPOINT[rl])
    note = ""
    if p["e_target"] > CEILING[rl]:
        note = (f"Target {p['e_target']}% p.a. exceeds the realistic ceiling "
                f"for a {rl} profile ({CEILING[rl]}%).")
    p["target_note"] = note
    return {"client_profile": p}
```
- [ ] **Step 4: Run green.**
- [ ] **Step 5: Commit** `feat(engine): load_profile node (target defaulting + mismatch note)`

### Task 1.2: `load_funds` + Step 1b retail-eligibility

Reads the FundMaster `Master` sheet (header row 3, data from row 4) into normalized `Fund` dicts and drops Step-1b-excluded rows. Column map from SKILL.md Step 1 (1-indexed): 1 Name, 2 Abbr, 3 Shariah, 4 Type, 6 Risk Level, 8 Size, 10 Status, 14 Weighted Alpha; returns block cols 15–29 (YTD/1Y/3Y/5Y/10Y × fund/bench/alpha); AE cols 30–34; assets cols 35–40; geo cols 41–52; top5 col 64; VF col 65; Lipper col 67; benchmark col 68; ATH drawdown col 72; days-from-ATH col 73.

**Files:** `consultant_engine/nodes/load_funds.py`, `tests/consultant_engine/conftest.py` (tiny workbook builder), `tests/consultant_engine/test_load_funds.py`

- [ ] **Step 1: Build a tiny-workbook fixture in conftest**
```python
import openpyxl, pytest

def _row(ws, r, name, abbr, shariah, ftype, rl, status, walpha, **kw):
    ws.cell(r, 1, name); ws.cell(r, 2, abbr); ws.cell(r, 3, shariah)
    ws.cell(r, 4, ftype); ws.cell(r, 6, rl); ws.cell(r, 10, status); ws.cell(r, 14, walpha)
    for col, val in kw.items():
        ws.cell(r, int(col[1:]), val)         # pass c35=.. style overrides

@pytest.fixture
def tiny_fundmaster(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Master"
    ws.cell(3, 1, "Fund Name")                 # header marker on row 3
    _row(ws, 4, "Public Index Fund", "PIX", "No", "Equity", 3, "Qualified", 2.1,
         c72=-3.0, c73=20)
    _row(ws, 5, "PB Growth Fund", "PBGF", "No", "Equity", 4, "Qualified", 1.0)   # PB → excluded
    _row(ws, 6, "Public e-Cash Deposit", "PeCDF-B", "No", "Money Market", 1, "Qualified", 0.1)  # -B → excluded
    _row(ws, 7, "Public Wholesale", "PWSIF", "No", "Equity", 5, "Qualified", 3.0)  # wholesale → excluded
    _row(ws, 8, "Public e-Cash Deposit", "PeCDF-A", "No", "Money Market", 1, "Qualified", 0.1)
    p = tmp_path / "PublicMutual_FundMaster_Jun2026_v0.1.0.xlsx"; wb.save(p)
    return str(p)
```
- [ ] **Step 2: Failing test**
```python
from consultant_engine.nodes.load_funds import load_funds

def test_step1b_exclusions(tiny_fundmaster):
    out = load_funds({"fundmaster_path": tiny_fundmaster})
    abbrs = {f["abbr"] for f in out["eligible_funds"]}
    assert abbrs == {"PIX", "PeCDF-A"}           # PB / -B / wholesale dropped
    pix = next(f for f in out["eligible_funds"] if f["abbr"] == "PIX")
    assert pix["risk_level"] == 3 and pix["drawdown"] == -3.0
```
- [ ] **Step 3: Run red.**
- [ ] **Step 4: Implement** — `load_funds(state)` opens `state["fundmaster_path"]`, reads `Master`, builds `Fund` dicts from the column map, then applies Step 1b:
```python
WHOLESALE = {"PBCPF", "PWSIF", "PIWSIF", "PeWS20F"}

def _excluded(name, abbr):
    return name.startswith("PB ") or abbr.endswith("-B") or abbr in WHOLESALE
```
Use explicit `None` checks for drawdown/days (SKILL.md note: `0.0` is valid, never `or`-default). Map `shariah` "Yes"→True else False.
- [ ] **Step 5: Run green. Commit** `feat(engine): load_funds + Step 1b eligibility`

### Task 1.3: `filter_universe` (Step 2)

Shariah filter + risk-level ceiling. Ceilings: Conservative 2, Moderate 3, Moderately Aggressive 4, Aggressive 5.

**Files:** `consultant_engine/nodes/filter_universe.py`, `tests/consultant_engine/test_filter_universe.py`

- [ ] **Step 1: Failing test**
```python
from consultant_engine.nodes.filter_universe import filter_universe

FUNDS = [
    {"abbr": "A", "shariah": True,  "risk_level": 2},
    {"abbr": "B", "shariah": False, "risk_level": 4},
    {"abbr": "C", "shariah": True,  "risk_level": 3},
]

def test_shariah_and_ceiling():
    out = filter_universe({"eligible_funds": FUNDS,
                           "client_profile": {"risk_level": "Moderate", "shariah": True}})
    assert {f["abbr"] for f in out["filtered_funds"]} == {"A", "C"}  # shariah + RL<=3
```
- [ ] **Step 2–4: red → implement → green.** `shariah is None` ⇒ no Shariah filter; `shariah is False` ⇒ exclude shariah-compliant (conventional-only). Ceiling map as above.
- [ ] **Step 5: Commit** `feat(engine): filter_universe (Shariah + RL ceiling)`

### Task 1.4: `cfs.derived_class` + `percentile_rank`

Derived class via asset look-through: Equity-equivalent if dom+for equity ≥ 60; Defensive if fi+mm+deposits ≥ 60; else Balanced. Percentile rank: top→100, bottom→0; ties share the rank.

**Files:** `consultant_engine/cfs.py`, `tests/consultant_engine/test_cfs.py`

- [ ] **Step 1: Failing test**
```python
from consultant_engine.cfs import derived_class, percentile_rank

def test_derived_class():
    assert derived_class({"assets": {"dom_equity": 70, "for_equity": 10, "fi": 0,
                                     "mm": 10, "deposits": 0, "other": 10}}) == "Equity-equivalent"
    assert derived_class({"assets": {"dom_equity": 5, "for_equity": 0, "fi": 50,
                                     "mm": 20, "deposits": 10, "other": 15}}) == "Defensive"

def test_percentile_rank():
    pop = [10, 20, 30, 40, 50]
    assert percentile_rank(50, pop) == 100
    assert percentile_rank(10, pop) == 0
    assert percentile_rank(30, pop) == 50
```
- [ ] **Step 2–4: red → implement → green.**
```python
def derived_class(fund) -> str:
    a = fund["assets"]
    eq = a.get("dom_equity", 0) + a.get("for_equity", 0)
    deff = a.get("fi", 0) + a.get("mm", 0) + a.get("deposits", 0)
    if eq >= 60: return "Equity-equivalent"
    if deff >= 60: return "Defensive"
    return "Balanced"

def percentile_rank(value, population) -> float:
    pop = sorted(population)
    if len(pop) <= 1: return 100.0
    below = sum(1 for x in pop if x < value)
    return round(100 * below / (len(pop) - 1), 1)
```
- [ ] **Step 5: Commit** `feat(engine): CFS derived-class + percentile rank`

### Task 1.5: `cfs` Alpha_N (weighted raw + penalties + missing-period)

Raw = 3Y·0.4 + 5Y·0.3 + 1Y·0.2 + YTD·0.1; missing periods redistribute their weight proportionally across available; halve if 3Y alpha < 0; halve again if 5Y alpha < 0.

**Files:** `consultant_engine/cfs.py`, `tests/consultant_engine/test_cfs.py`

- [ ] **Step 1: Failing test**
```python
from consultant_engine.cfs import weighted_blend, raw_alpha_penalised

def test_weighted_blend_full():
    periods = {"ytd": 1.0, "1y": 2.0, "3y": 3.0, "5y": 4.0}
    assert weighted_blend(periods) == round(3*.4 + 4*.3 + 2*.2 + 1*.1, 4)

def test_weighted_blend_redistributes_missing():
    # only 3Y + 5Y present → weights .4/.3 renormalize to .571/.429
    v = weighted_blend({"3y": 10.0, "5y": 10.0})
    assert round(v, 2) == 10.0

def test_penalties_halve_on_negative_long_alpha():
    fund = {"returns": {"3y": {"alpha": -1.0}, "5y": {"alpha": 2.0},
                        "1y": {"alpha": 5.0}, "ytd": {"alpha": 5.0}}}
    base = raw_alpha_penalised(fund, penalize=False)
    pen = raw_alpha_penalised(fund, penalize=True)
    assert pen == base / 2          # 3Y<0 halves once
```
- [ ] **Step 2–4: red → implement → green.**
```python
WEIGHTS = {"3y": 0.4, "5y": 0.3, "1y": 0.2, "ytd": 0.1}

def weighted_blend(periods: dict) -> float:
    avail = {k: v for k, v in periods.items() if v is not None and k in WEIGHTS}
    if not avail: return 0.0
    total_w = sum(WEIGHTS[k] for k in avail)
    return round(sum(v * WEIGHTS[k] for k, v in avail.items()) / total_w, 4)

def raw_alpha_penalised(fund, penalize=True) -> float:
    alpha_periods = {k: fund["returns"].get(k, {}).get("alpha") for k in WEIGHTS}
    raw = weighted_blend(alpha_periods)
    if penalize:
        if (fund["returns"].get("3y", {}).get("alpha") or 0) < 0: raw /= 2
        if (fund["returns"].get("5y", {}).get("alpha") or 0) < 0: raw /= 2
    return raw
```
- [ ] **Step 5: Commit** `feat(engine): CFS Alpha_N raw + penalties`

### Task 1.6: `cfs` ReturnFit_N (weighted fund return / E_target → piecewise curve)

Wtd_Return uses the same period weights on **fund** returns; Return_Ratio = Wtd_Return / E_target; piecewise-linear curve (anchors: ≥1.5→100, 1.0→80, 0.75→50, 0.5→20, ≤0.25→5, ≤0→0). Bear-market exception (all-negative within class → relative) is a class-level pass handled in Task 1.10's `score_all`.

**Files:** `consultant_engine/cfs.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.cfs import returnfit_score

def test_returnfit_anchors():
    assert returnfit_score(1.5) == 100
    assert returnfit_score(1.0) == 80
    assert returnfit_score(0.75) == 50
    assert returnfit_score(0.0) == 0

def test_returnfit_interpolates():
    assert 80 < returnfit_score(1.25) < 100      # between 1.0 and 1.5
```
- [ ] **Step 2–4: red → implement → green.**
```python
_ANCHORS = [(0.0, 0), (0.25, 5), (0.5, 20), (0.75, 50), (1.0, 80), (1.5, 100)]

def returnfit_score(ratio: float) -> float:
    if ratio <= 0: return 0.0
    if ratio >= 1.5: return 100.0
    for (x0, y0), (x1, y1) in zip(_ANCHORS, _ANCHORS[1:]):
        if x0 <= ratio <= x1:
            return round(y0 + (y1 - y0) * (ratio - x0) / (x1 - x0), 1)
    return 0.0
```
- [ ] **Step 5: Commit** `feat(engine): CFS ReturnFit_N curve`

### Task 1.7: `cfs` Efficiency_raw

`Efficiency_raw = 3Y AE` (FundMaster col 32) with fallback to 1Y AE. Normalized to percentile within class in `score_all`.

**Files:** `consultant_engine/cfs.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.cfs import efficiency_raw
def test_efficiency_prefers_3y_then_1y():
    assert efficiency_raw({"ae": {"3y": 1.2, "1y": 0.5}}) == 1.2
    assert efficiency_raw({"ae": {"3y": None, "1y": 0.5}}) == 0.5
```
- [ ] **Step 2–4: red → implement → green** (`fund["ae"].get("3y")` else `.get("1y")` else 0).
- [ ] **Step 5: Commit** `feat(engine): CFS Efficiency_raw`

### Task 1.8: `cfs` Momentum_N (absolute, with recovery bonus + None guard)

Base from drawdown bands; recovery bonus from days-from-ATH; clamp [0,100]. **None-check drawdown before defaulting** (SKILL.md: `0.0` is valid; never `or`-default to −50).

**Files:** `consultant_engine/cfs.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.cfs import momentum_score
def test_momentum_at_ath_fast_recovery():
    assert momentum_score(0.0, 10) == 95          # band 80 + <30d bonus 15
def test_momentum_none_drawdown_defaults_to_minus_50():
    # None drawdown defaults to -50.0; compare against -50.0 with the SAME days
    assert momentum_score(None, None) == momentum_score(-50.0, None)
def test_momentum_clamped():
    assert momentum_score(-3.0, 500) == 70        # 80 base + (-10) old → 70
```
- [ ] **Step 2–4: red → implement → green.**
```python
def _dd_base(dd):
    for hi, score in [(-5,80),(-10,70),(-15,60),(-25,40),(-40,20)]:
        if dd >= hi: return score
    return 10

def _recovery(days):
    if days is None: return 0
    if days < 30: return 15
    if days <= 90: return 10
    if days <= 180: return 5
    if days <= 365: return 0
    return -10

def momentum_score(drawdown, days) -> float:
    dd = drawdown if drawdown is not None else -50.0
    return max(0.0, min(100.0, _dd_base(dd) + _recovery(days)))
```
- [ ] **Step 5: Commit** `feat(engine): CFS Momentum_N (None-safe)`

### Task 1.9: `cfs` weights (base + E_target stretch + clamp + normalize)

Base weights per profile (SKILL.md table). Stretch = (E_target − midpoint)/midpoint; above → shift ≤+10pp w_A→w_R proportional to stretch; below → shift ≤+5pp w_R→w_A. Clamp each to [5,50], renormalize to 100.

**Files:** `consultant_engine/cfs.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.cfs import profile_weights

def test_base_weights_sum_100():
    w = profile_weights("Moderate", 5.0)        # at midpoint → no stretch
    assert round(sum(w.values())) == 100
    assert w["returnfit"] == 40

def test_stretch_above_shifts_alpha_to_returnfit():
    w = profile_weights("Moderate", 6.0)        # +20% stretch
    base = profile_weights("Moderate", 5.0)
    assert w["returnfit"] > base["returnfit"] and w["alpha"] < base["alpha"]
```
- [ ] **Step 2–4: red → implement → green.**
```python
BASE = {
  "Conservative":          {"alpha":28,"returnfit":40,"efficiency":25,"momentum":7},
  "Moderate":              {"alpha":28,"returnfit":40,"efficiency":20,"momentum":12},
  "Moderately Aggressive": {"alpha":26,"returnfit":40,"efficiency":17,"momentum":17},
  "Aggressive":            {"alpha":30,"returnfit":40,"efficiency":13,"momentum":17},
}
MID = {"Conservative":3.5,"Moderate":5.0,"Moderately Aggressive":7.0,"Aggressive":9.0}

def profile_weights(profile, e_target) -> dict:
    w = dict(BASE[profile]); mid = MID[profile]
    stretch = (e_target - mid) / mid
    if stretch > 0:
        shift = min(10.0, 10.0 * stretch); w["alpha"] -= shift; w["returnfit"] += shift
    elif stretch < 0:
        shift = min(5.0, 5.0 * abs(stretch)); w["returnfit"] -= shift; w["alpha"] += shift
    w = {k: max(5.0, min(50.0, v)) for k, v in w.items()}
    total = sum(w.values())
    return {k: round(v * 100 / total, 2) for k, v in w.items()}
```
- [ ] **Step 5: Commit** `feat(engine): CFS profile weights + stretch modifier`

### Task 1.10: `cfs.score_all` (compose + class-normalize + bear exception + tiebreaker)

Computes per-fund dims, percentile-normalizes Alpha/ReturnFit/Efficiency **within derived class**, leaves Momentum absolute, composes CFS, returns `CFSScore` list sorted desc with tiebreak (CFS within 2 → higher Alpha_N, then Efficiency_N). Bear-market: if all `Wtd_Return` in a class < 0, ReturnFit becomes relative (percentile) within class.

**Files:** `consultant_engine/cfs.py`, `consultant_engine/nodes/score_cfs.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.cfs import score_all

def _f(abbr, a3, ret3, ae3, dd):
    return {"abbr": abbr, "assets": {"dom_equity": 80, "for_equity": 0, "fi": 0,
            "mm": 10, "deposits": 0, "other": 10},
            "returns": {"3y": {"alpha": a3, "fund": ret3}, "5y": {"alpha": a3, "fund": ret3},
                        "1y": {"alpha": a3, "fund": ret3}, "ytd": {"alpha": a3, "fund": ret3}},
            "ae": {"3y": ae3}, "drawdown": dd, "days_from_ath": 20}

def test_score_all_ranks_higher_alpha_first():
    funds = [_f("LOW", 1.0, 5.0, 0.3, -3.0), _f("HIGH", 8.0, 12.0, 1.5, -3.0)]
    scores = score_all(funds, "Moderate", 5.0)
    assert scores[0]["abbr"] == "HIGH"
    assert 0 <= scores[0]["composite"] <= 100
```
- [ ] **Step 2–4: red → implement → green.** `score_all(funds, profile, e_target)`: group by `derived_class`; per class compute raw alpha/returnfit-ratio/efficiency, then percentile-normalize within class; momentum absolute; `composite = Σ w·dim/100` using `profile_weights`; sort with tiebreaker. `score_cfs` node: `return {"cfs_scores": score_all(state["filtered_funds"], state["client_profile"]["risk_level"], state["client_profile"]["e_target"])}`.
- [ ] **Step 5: Commit** `feat(engine): CFS score_all + tiebreaker + bear exception`

### Task 1.11: `invariants` module

Pure checks reused by `build_portfolio` (post-build) and the review gate (post-edit): allocations sum to 100 (±0.5), **exactly four funds**, no single fund over the concentration cap, every fund's RL ≤ profile ceiling (except a disclosed satellite), gold + money-market structural positions both present, all funds retail-eligible + in the scored universe.

**Files:** `consultant_engine/invariants.py`, `tests/consultant_engine/test_invariants.py`

Concentration cap + portfolio size — the build is **always 4 funds** (gold + MM + 2 discretionary), so count is exactly four for every profile: `SIZE = {p: (4, 4) for p in PROFILES}` (satellite / exposure-gap *substitute* a slot, never add a fifth). The per-fund concentration cap is a **backstop sized for the 4-fund structure** — with only two core funds absorbing a whole asset-band each after normalization, it is looser than the old 6-fund caps: `CAP = {"Conservative":50,"Moderate":50,"Moderately Aggressive":60,"Aggressive":70}` (derived from the profile's largest asset-band ceiling in SKILL.md Step-4, with headroom for normalization). The deterministic allocator's band logic does the real shaping; the cap only catches a single fund dominating the book (and guards human edits at the review gate).

- [ ] **Step 1: Failing test**
```python
from consultant_engine.invariants import check_invariants

PORT = [
    {"abbr": "PIX", "role": "core", "allocation_pct": 60},
    {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
    {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10},
    {"abbr": "PeDiv", "role": "core", "allocation_pct": 20},
]
UNIVERSE = {"PIX", "PeEMAS", "PeCDF-A", "PeDiv"}

def test_concentration_violation():
    v = check_invariants(PORT, "Moderate", UNIVERSE, rl_by_abbr={a: 3 for a in UNIVERSE})
    assert any("cap" in x["msg"].lower() for x in v)     # PIX 60 > 50 cap

def test_clean_portfolio_has_no_violations():
    clean = [{"abbr":"PIX","role":"core","allocation_pct":40},
             {"abbr":"PeDiv","role":"core","allocation_pct":40},
             {"abbr":"PeEMAS","role":"structural:gold","allocation_pct":10},
             {"abbr":"PeCDF-A","role":"structural:money_market","allocation_pct":10}]
    v = check_invariants(clean, "Moderate", UNIVERSE, rl_by_abbr={a: 3 for a in UNIVERSE})
    assert v == []
```
- [ ] **Step 2–4: red → implement → green.** Return `list[{"code","msg"}]`.
- [ ] **Step 5: Commit** `feat(engine): deterministic invariants`

### Task 1.12: `portfolio` templates + structural gold/MM

`build(scores, funds, profile, shariah)` → `list[Holding]`. **Experience-blind** — every client gets the same **4-fund** portfolio: the top-2 CFS core funds for the profile, then always appends gold `PeEMAS` and money-market `PeCDF-A` (or `PIMMF-A` if shariah). Allocation % from the template gradient, normalized to 100.

**Files:** `consultant_engine/portfolio.py`, `tests/consultant_engine/test_build_portfolio.py`

- [ ] **Step 1: Failing test**
```python
from consultant_engine.portfolio import build

def test_structural_always_present_and_sums_100():
    scores = [{"abbr": f"E{i}", "composite": 90 - i, "derived_class": "Equity-equivalent",
               "alpha_n": 50} for i in range(6)]
    funds = {f"E{i}": {"abbr": f"E{i}", "fund_type": "Equity", "risk_level": 3,
                       "top5": [], "shariah": False} for i in range(6)}
    funds["PeEMAS"] = {"abbr": "PeEMAS", "fund_type": "Gold", "risk_level": 3, "top5": []}
    funds["PeCDF-A"] = {"abbr": "PeCDF-A", "fund_type": "Money Market", "risk_level": 1, "top5": []}
    port = build(scores, funds, "Moderate", shariah=None)
    roles = {h["role"] for h in port}
    assert "structural:gold" in roles and "structural:money_market" in roles
    assert len(port) == 4                                      # gold + MM + 2 core, always
    assert round(sum(h["allocation_pct"] for h in port)) == 100
```
- [ ] **Step 2–4: red → implement → green.** Encode template ranges (use midpoints, then normalize). Always take exactly the top-2 core picks so total funds = 4 (gold + MM + 2 core) for every client.
- [ ] **Step 5: Commit** `feat(engine): portfolio templates + structural positions`

### Task 1.13: `portfolio` diversification (top-holdings overlap dedup)

If two equity/mixed picks share ≥3 of top-5 holdings, drop the lower-alpha one and pull the next-ranked candidate.

**Files:** `consultant_engine/portfolio.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.portfolio import dedup_overlap
def test_overlap_drops_lower_alpha():
    picks = [{"abbr": "A", "alpha_n": 80, "top5": ["x","y","z","p","q"]},
             {"abbr": "B", "alpha_n": 60, "top5": ["x","y","z","m","n"]}]   # shares x,y,z
    kept = dedup_overlap(picks)
    assert [p["abbr"] for p in kept] == ["A"]
```
- [ ] **Step 2–4: red → implement → green** (pairwise top-5 intersection ≥3 → keep higher `alpha_n`).
- [ ] **Step 5: Commit** `feat(engine): diversification overlap dedup`

### Task 1.14: `portfolio` exposure-gap pick

Conditional **exposure-gap pick** when macro flags an exposure no core fund covers. Because the portfolio is fixed at 4 funds, the pick **substitutes the lowest-alpha core slot** — never a fifth fund — and **no-ops when an alpha-outlier satellite is already present** (satellite wins the single discretionary substitution, per spec decision 10). The gap fund is capped at 15%; the freed slot share is redistributed to the surviving non-structural holdings so the book still sums to 100. Gates: positive 3Y alpha, ≤1 per portfolio, ≤15% allocation, profile supports it. (Macro-driven; in L1 the trigger comes from `state["macro_context"]["exposure_gaps"]`, empty by default.)

**Files:** `consultant_engine/portfolio.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.portfolio import exposure_gap_pick

CAND = [{"abbr": "PUSEQ", "returns": {"3y": {"alpha": 1.5}}, "fund_type": "Equity"}]
CORE = [{"abbr": "PIX", "role": "core", "allocation_pct": 45, "alpha_n": 70},
        {"abbr": "PLO", "role": "core", "allocation_pct": 35, "alpha_n": 30},
        {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
        {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10}]

def test_gap_pick_substitutes_lowest_alpha_core_capped_15():
    out = exposure_gap_pick(CORE, candidates=CAND, gaps=["US equity"], profile="Moderate")
    abbrs = {h["abbr"] for h in out}
    assert "PUSEQ" in abbrs and "PLO" not in abbrs           # replaced the lower-alpha core slot
    assert len(out) == 4 and round(sum(h["allocation_pct"] for h in out)) == 100
    assert next(h for h in out if h["abbr"] == "PUSEQ")["allocation_pct"] <= 15

def test_no_gap_returns_portfolio_unchanged():
    assert exposure_gap_pick(CORE, CAND, gaps=[], profile="Moderate") == CORE

def test_skip_when_satellite_present():
    with_sat = CORE + [{"abbr": "STAR", "role": "satellite", "allocation_pct": 8}]
    assert exposure_gap_pick(with_sat, CAND, gaps=["US equity"], profile="Moderate") == with_sat
```
- [ ] **Step 2–4: red → implement → green.** Signature `exposure_gap_pick(portfolio, candidates, gaps, profile) -> list[Holding]`; **no-op if a satellite is already present** (precedence) or no gap/candidate; else swap the lowest-alpha core for the gap fund, cap it at 15%, redistribute the freed slot to the surviving non-structural holdings (sum stays 100). Gate on positive 3Y alpha + ≤1 pick + ≤15%.
- [ ] **Step 5: Commit** `feat(engine): exposure-gap pick`

### Task 1.15: `portfolio` alpha-outlier satellite + carve

Scan qualified universe (Status=Qualified); top-5 by CFS minus held; gates A (3Y>0, 5Y>0 if present), A2 (Alpha_N≥80), B (Shariah), C (overlap<3); pick ≤1; size per profile cap; Aggressive skips. Because the portfolio is fixed at 4 funds, the satellite **substitutes the lowest-alpha core slot** (never a fifth fund), **inheriting that core's allocation** so the book stays at 100 (a small-tilt satellite + redistribute is infeasible here — it would over-concentrate the one surviving core past the cap). It carries alpha-qualified precedence over any exposure-gap pick (spec decision 10).

**Files:** `consultant_engine/portfolio.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.portfolio import alpha_outlier

def test_outlier_substitutes_lowest_alpha_core():
    portfolio = [{"abbr": "CORE_HI", "role": "core", "allocation_pct": 45, "alpha_n": 70},
                 {"abbr": "CORE_LO", "role": "core", "allocation_pct": 35, "alpha_n": 40},
                 {"abbr": "PeEMAS", "role": "structural:gold", "allocation_pct": 10},
                 {"abbr": "PeCDF-A", "role": "structural:money_market", "allocation_pct": 10}]
    scores = [{"abbr": "STAR", "composite": 99, "alpha_n": 95, "derived_class": "Equity-equivalent"}]
    funds = {"STAR": {"abbr": "STAR", "status": "Qualified", "shariah": False,
                      "risk_level": 5, "top5": [], "returns": {"3y": {"alpha": 9.0}, "5y": {"alpha": 7.0}}}}
    out = alpha_outlier(portfolio, scores, funds, "Moderate", shariah=None)
    abbrs = {h["abbr"] for h in out}
    assert "STAR" in abbrs and "CORE_LO" not in abbrs        # took the lowest-alpha core's slot
    assert next(h for h in out if h["abbr"] == "STAR")["role"] == "satellite"
    assert len(out) == 4 and round(sum(h["allocation_pct"] for h in out)) == 100

def test_aggressive_skips_outlier():
    assert alpha_outlier([], [], {}, "Aggressive", None) == []
```
- [ ] **Step 2–4: red → implement → green.** Signature `alpha_outlier(portfolio, scores, funds, profile, shariah) -> list[Holding]`; gates A/A2/B/C from SKILL.md Step 4d; substitutes the lowest-alpha core (keeps the book at 4 funds); Aggressive returns input unchanged.
- [ ] **Step 5: Commit** `feat(engine): alpha-outlier satellite + carve`

### Task 1.16: `build_portfolio` node (compose + invariants)

Wires 1.12–1.15 into `build_portfolio(state)`: build → dedup → **satellite → exposure-gap** (satellite runs first so it claims the single discretionary substitution; exposure-gap no-ops when a satellite was taken — spec decision 10) → normalize → `check_invariants`; raise on any invariant violation (a build-time bug, not a human edit). Also emits `proposed_allocation` (the review artifact payload, Task 2.1 fills detail).

**Files:** `consultant_engine/nodes/build_portfolio.py`, `tests/consultant_engine/test_build_portfolio_node.py`

- [ ] **Step 1: Failing test** — full pipeline from `tiny_fundmaster` → `load_funds → filter → score → build_portfolio` yields a 100%-summing portfolio with gold+MM and no invariant violations.
- [ ] **Step 2–4: red → implement → green.**
- [ ] **Step 5: Commit** `feat(engine): build_portfolio node (compose + invariant gate)`

**L1 exit check:** `python3 -m pytest tests/consultant_engine/ -v` green; running the graph to the interrupt produces a real, invariant-clean portfolio (LLM nodes still stubbed).

---

# Phase 2 — Review gate (HITL: exit-and-resume + edit re-validation)

Goal: implement the artifact contract from spec §7.

### Task 2.1: Write review artifact + HTML preview at interrupt

`build_proposed_allocation(state) -> dict` builds the JSON contract (`context`, `constraints`, `allocation`, `review`); `_review` (graph.py) writes it to `data/review/<thread_id>.json` + `data/review/<thread_id>.html` before calling `interrupt()`.

**Files:** `consultant_engine/nodes/review_gate.py`, `tests/consultant_engine/test_review_gate.py`

- [ ] **Step 1: Failing test**
```python
import json
from consultant_engine.nodes.review_gate import build_proposed_allocation, write_artifact

def test_artifact_has_three_blocks(tmp_path):
    state = {"thread_id": "t1", "client_profile": {"risk_level": "Moderate", "e_target": 5.0,
             "shariah": False, "experience": "experienced", "upfront_capital_rm": 50000},
             "fundmaster_path": "fm.xlsx",
             "portfolio": [{"abbr": "PIX", "role": "core", "allocation_pct": 40}],
             "cfs_scores": [{"abbr": "PIX", "composite": 88, "alpha_n": 90}]}
    art = build_proposed_allocation(state)
    assert set(art) >= {"context", "constraints", "allocation", "review"}
    assert art["constraints"]["allocations_sum_to_pct"] == 100
    p = write_artifact(tmp_path, "t1", art)
    assert json.loads(p.read_text())["allocation"][0]["abbrev"] == "PIX"
```
- [ ] **Step 2–4: red → implement → green.** `constraints` derived from profile (cap, count range, RL ceiling, required structural). `allocation[].cfs/rank/risk_level/eligible` are display-only copies from `cfs_scores`/funds.
- [ ] **Step 5: Commit** `feat(engine): review artifact + preview`

### Task 2.2: Resume re-validation (intent vs facts)

`apply_resume(state, resume_payload) -> dict`: read edited `allocation` (only `abbrev` + `allocation_pct` honored), **re-derive** facts from `cfs_scores`/universe, run `check_invariants`. Clean → updated `portfolio`. Violations → with review ON, re-interrupt (write artifact with a `violations` block); with `--no-review`, raise (fail loudly). Replace the L0 `read_resume_payload` stub with a real reader of `data/review/<thread_id>.json`.

**Files:** `consultant_engine/nodes/review_gate.py`, `consultant_engine/graph.py`, test.

- [ ] **Step 1: Failing test**
```python
from consultant_engine.nodes.review_gate import apply_resume

def test_overcap_edit_is_rejected():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [{"abbr": "PIX", "alpha_n": 90}, {"abbr": "PeDiv", "alpha_n": 80}],
             "_universe": {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"abbrev": "PIX", "allocation_pct": 60},        # over the 40 cap
        {"abbrev": "PeDiv", "allocation_pct": 20},
        {"abbrev": "PeEMAS", "allocation_pct": 10},
        {"abbrev": "PeCDF-A", "allocation_pct": 10}]}
    out = apply_resume(state, payload)
    assert out["violations"]                              # re-validation caught the cap breach

def test_clean_edit_accepted():
    state = {"client_profile": {"risk_level": "Moderate"}, "filtered_funds": [],
             "cfs_scores": [{"abbr": "PIX", "alpha_n": 90}, {"abbr": "PeDiv", "alpha_n": 80}],
             "_universe": {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}}
    payload = {"allocation": [
        {"abbrev": "PIX", "allocation_pct": 40},
        {"abbrev": "PeDiv", "allocation_pct": 40},
        {"abbrev": "PeEMAS", "allocation_pct": 10},
        {"abbrev": "PeCDF-A", "allocation_pct": 10}]}
    out = apply_resume(state, payload)
    assert out.get("violations", []) == []
    assert {h["abbr"] for h in out["portfolio"]} == {"PIX", "PeDiv", "PeEMAS", "PeCDF-A"}
```
- [ ] **Step 2–4: red → implement → green.** Wire into `_review`: on resume, call `apply_resume`; if it returns violations and not `no_review`, re-`interrupt`.
- [ ] **Step 5: Commit** `feat(engine): resume re-validation (intent vs facts)`

**Phase-2 exit check:** end-to-end CLI: invoke pauses + writes `data/review/<tid>.json`; hand-edit over the cap → `--resume` re-pauses; edit clean → resumes to (stubbed) generation.

---

# Phase L2 — Real generation (LLM prose + slotted HTML)

### Task 3.0: Macro contract + fixture + real `macro_context` node

The macro-context seam (spec §6, deliverable 3): a pydantic schema, a fixture producer, and a `macro_context` node that normalizes/validates the contract. Live web-search producer is **deferred to ENH-6** — ship the contract + fixture only.

**Files:** `consultant_engine/macro.py`, `consultant_engine/assets/macro_fixture.json`, `consultant_engine/nodes/macro_context.py`, `tests/consultant_engine/test_macro.py`

- [ ] **Step 1: Failing test**
```python
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
    assert all({"date","theme","claim","source_url"} <= set(e) for e in out["macro_context"]["events"])
```
- [ ] **Step 2: Run red** → FAIL (no `consultant_engine.macro`).
- [ ] **Step 3: Implement**
```python
# consultant_engine/macro.py
import json
from pathlib import Path
from pydantic import BaseModel, HttpUrl

class MacroEvent(BaseModel):
    date: str
    theme: str
    claim: str
    source_url: str

class MacroContext(BaseModel):
    events: list[MacroEvent] = []

def load_fixture() -> MacroContext:
    p = Path(__file__).resolve().parent.parent / "consultant_engine/assets/macro_fixture.json"
    return MacroContext.model_validate(json.loads(p.read_text()))
```
`macro_context` node: if `state["macro_context"].get("source") == "fixture"` (or `"none"`), return `{"macro_context": load_fixture().model_dump()}`; else validate the passed dict through `MacroContext` and return its `model_dump()`. The fixture JSON holds 2–3 dated events spanning themes (rates, ringgit, AI/tech).
- [ ] **Step 4: Run green** → PASS.
- [ ] **Step 5: Commit** `feat(engine): macro contract + fixture + macro_context node`

### Task 3.1: Move design system + build slotted skeleton

Copy `fund-consultant-skill/references/design_system.css` → `consultant_engine/assets/design_system.css` verbatim. Derive `consultant_engine/assets/proposal_skeleton.html` from `references/proposal_template.md`: keep the locked structure (cover, 9 numbered sections in the order from `tests/test_proposal_validation.py::LOCKED_SECTIONS`), convert each `[BRACKETED]` token into an explicit slot — numeric slots as `data-slot="cfs.PIX.composite"` attributes, prose slots as `<!--slot:why.PIX-->` markers — so `validate` can diff numbers by slot. Include the **conditional Foundation Intro** block (rendered for new investors only) as a **3-note** block — *What is a Unit Trust / How Returns Work / Cooling-Off Right*; **drop the old "Why a Starter Portfolio (vs a full 6-fund)" note**, since every client now gets the same focused 4-fund build.

**Files:** `consultant_engine/assets/design_system.css`, `consultant_engine/assets/proposal_skeleton.html`, `tests/consultant_engine/test_assets.py`

- [ ] **Step 1: Failing test** — skeleton contains all 9 `LOCKED_SECTIONS` titles in order, exactly 9 `<div class="section">`, the 4 disclaimer `<h4>`s, and the `fund-consultant v[SKILL_VERSION]`→`{{version}}` slot.
- [ ] **Step 2–4: red → build asset → green.**
- [ ] **Step 5: Commit** `feat(engine): move design system + slotted skeleton`

### Task 3.2: `templates` — deterministic structural cards + slot fill

`render_structural_card(holding, fund)` builds the gold + money-market cards deterministically (no LLM — per spec §14 they leave the LLM map set). `fill_slots(skeleton, slot_values)` substitutes numeric slots + version.

**Files:** `consultant_engine/templates.py`, test.

- [ ] **Step 1: Failing test** — gold card carries the `#b7791f` border + no alpha-warning; `fill_slots` replaces `{{version}}` and a `data-slot` value; unknown leftover slot raises.
- [ ] **Step 2–4: red → implement → green.**
- [ ] **Step 5: Commit** `feat(engine): structural-card templating + slot fill`

### Task 3.3: Generation prompt assets

Author `consultant_engine/assets/prompts/generate_proposal.md` from SKILL.md Steps 6–7: per-fund "Why/Watch" prose, macro alignment, investment strategy, the two-layer jargon rule keyed on `client_profile["experience"]`, tone/compliance language rules, and the instruction to fill prose slots only (numbers come pre-filled). Include the canonical jargon table verbatim.

**Files:** `consultant_engine/assets/prompts/generate_proposal.md` (+ `repair.md`)

- [ ] **Step 1:** Write the prompt; no test (asset). Smoke: file exists + contains the jargon table + "do not alter numeric slots".
- [ ] **Step 2: Commit** `feat(engine): generation + repair prompt assets`

### Task 3.4: `llm` wrapper (configurable + stub-able)

`complete(prompt, model, system=None) -> str` over the Anthropic SDK; honor `CONSULTANT_ENGINE_FAKE_LLM` env (returns a deterministic canned HTML) so tests + CI never hit the network.

**Files:** `consultant_engine/llm.py`, `tests/consultant_engine/test_llm.py`

- [ ] **Step 1: Failing test** — with the fake env set, `complete(...)` returns the canned string without an API key.
- [ ] **Step 2–4: red → implement → green.**
- [ ] **Step 5: Commit** `feat(engine): Anthropic wrapper with fake-LLM mode`

### Task 3.5: `generate_proposal` node

Pre-fill all numeric slots deterministically (CFS bars, performance tables, allocations, portfolio summary, exposure pies from SKILL.md 7b/7c), render structural cards deterministically, then call the LLM (selecting the prompt by `client_profile["experience"]`) to fill prose slots only. The **Foundation Intro** block renders only for new investors (conditional skeleton block). Returns `{"proposal_html": ...}`.

**Files:** `consultant_engine/nodes/generate_proposal.py`, test (run under fake-LLM).

- [ ] **Step 1: Failing test** — under fake-LLM, output contains the cover, all 9 sections, a CFS bar whose numeric slots equal the state CFS, and the version stamp.
- [ ] **Step 2–4: red → implement → green.**
- [ ] **Step 5: Commit** `feat(engine): generate_proposal (numeric prefill + LLM prose)`

### Task 3.6: `emit` node (version-stamped filename + write)

Filename `FundProposal_<Profile>_<MonYYYY>[_<ClientLastName>]_v<__version__>.html` into `state["output_dir"]`; footer/disclaimer stamp from `consultant_engine.__version__`. MonYYYY from the FundMaster filename.

**Files:** `consultant_engine/nodes/emit.py`, test.

- [ ] **Step 1: Failing test** — writes a file whose name ends `_v0.1.0.html` and whose text contains `fund-consultant v0.1.0` (stamp string kept identical so the existing validator matches) and `AI-Generated Document`.
- [ ] **Step 2–4: red → implement → green.** (Stamp label stays `fund-consultant v<ver>` so the locked-template validator continues to match; the version source is now the package — see Task 4.4.)
- [ ] **Step 5: Commit** `feat(engine): emit with package-version stamping`

**L2 exit check:** `python -m consultant_engine ... --no-review` (fake-LLM) writes a complete proposal HTML to the output dir.

---

# Phase L3 — Validate ⇄ repair + shared rule module

### Task 4.1: Extract shared rule module

`consultant_engine/rules/validation.py` exposes pure functions returning `list[{"code","msg"}]`, lifted from `tests/test_proposal_validation.py`: `check_sections(html)`, `check_version_and_disclosure(html, version)`, `check_cfs_consistency(html)`, `check_funds_in_workbook(html, workbook_index)`, `check_alpha_warning(html, workbook_index)`, `check_retail_eligibility(html, workbook_index)`, plus `validate_html(html, version, workbook_index) -> list`. Reuse the existing regex helpers (`fund_cards`, `workbook_index`).

**Files:** `consultant_engine/rules/validation.py`, `tests/consultant_engine/test_validation_rules.py`, fixtures `proposal_good.html`, `proposal_bad_section.html`, `proposal_bad_cfs.html`.

- [ ] **Step 1: Failing test** (this is the *validate-the-validator* layer)
```python
from consultant_engine.rules.validation import validate_html
from consultant_engine import __version__

def test_good_proposal_has_no_violations(good_html, wb_index):
    assert validate_html(good_html, __version__, wb_index) == []

def test_section_drift_is_caught(bad_section_html, wb_index):
    codes = {v["code"] for v in validate_html(bad_section_html, __version__, wb_index)}
    assert "section_order" in codes

def test_cfs_inconsistency_is_caught(bad_cfs_html, wb_index):
    codes = {v["code"] for v in validate_html(bad_cfs_html, __version__, wb_index)}
    assert "cfs_recompute" in codes
```
- [ ] **Step 2–4: red → implement → green.** Port each check; `proposal_good.html` is a known-clean fixture (copy a curated `output/examples/fund_proposals/*` proposal, re-stamped to `__version__`); the bad fixtures mutate one rule each.
- [ ] **Step 5: Commit** `feat(engine): shared validation rule module + good/bad fixtures`

### Task 4.2: `validate` node

`validate(state)` builds the workbook index from `fundmaster_path`, runs `validate_html(state["proposal_html"], __version__, idx)`, returns `{"violations": [...]}`.

**Files:** `consultant_engine/nodes/validate.py`, test.

- [ ] **Step 1: Failing test** — clean generated HTML → `violations == []`; a hand-broken HTML → non-empty.
- [ ] **Step 2–4: red → implement → green.**
- [ ] **Step 5: Commit** `feat(engine): validate node`

### Task 4.3: `repair` node + loop + fail-loud

`repair(state)` sends `violations` + current HTML + the repair prompt to the LLM, returns `{"proposal_html": fixed, "repair_iterations": n+1}`. The `_after_validate`/`MAX_REPAIR=3`/`fail` wiring already exists (Task 0.4) — add a test proving cap → `RuntimeError`.

**Files:** `consultant_engine/nodes/repair.py`, test.

- [ ] **Step 1: Failing test** — with a fake-LLM that never fixes the injected violation, the graph raises `RuntimeError` after 3 repairs (fail-loud), and `repair_iterations == 3`.
- [ ] **Step 2–4: red → implement → green.**
- [ ] **Step 5: Commit** `feat(engine): repair node + fail-loud at MAX`

### Task 4.4: Refactor `tests/test_proposal_validation.py` onto the shared module + package version

Re-point `skill_version()` to `consultant_engine.__version__`; replace the inline checks with calls into `consultant_engine.rules.validation` so the suite and the runtime node share one source of truth. Keep `KNOWN_*` pin sets empty.

**Files:** `tests/test_proposal_validation.py`

- [ ] **Step 1:** Change `skill_version()`:
```python
def skill_version():
    from consultant_engine import __version__
    return __version__
```
- [ ] **Step 2:** Re-stamp curated `output/examples/fund_proposals/*.html` filenames + footers to `_v0.1.0` (so the version-stamp test passes against the new source). Keep one curated sample per profile.
- [ ] **Step 3:** Replace each `test_*` body with a thin wrapper calling the shared functions (logic now lives in `rules/validation.py`).
- [ ] **Step 4: Run** `python3 -m pytest tests/test_proposal_validation.py -v` → PASS.
- [ ] **Step 5: Commit** `refactor(tests): proposal validation onto shared rule module + package version`

**L3 exit check:** full `python3 -m pytest` green; a real (fake-LLM) end-to-end run emits a proposal that the standalone suite also passes.

---

# Phase 5 — Cutover (retire the skill bundle, keep CI green)

### Task 5.1: Retire `fund-consultant-skill/` bundle

Delete the bundle (its CSS/skeleton/prompts now live in `consultant_engine/assets/`). Confirm nothing else imports it (`grep -rn "fund-consultant-skill" --include=*.py`).

**Files:** remove `fund-consultant-skill/`; `tests/` references.

- [ ] **Step 1:** `grep -rn "fund-consultant-skill" . --include=*.py --include=*.md` → resolve every hit (the only `.py` user was `skill_version()`, fixed in 4.4).
- [ ] **Step 2:** `git rm -r fund-consultant-skill/`
- [ ] **Step 3: Run** `python3 -m pytest` → green.
- [ ] **Step 4: Commit** `chore: retire fund-consultant skill bundle (superseded by consultant_engine)`

### Task 5.2: Update CLAUDE.md + README + sync-private references

Update the CLAUDE.md skill table (drop the `fund-consultant` row; document the engine CLI), the "Where the logic lives" + outputs/versioning sections (version source is now `consultant_engine.__version__`), and `scripts/sync-private.sh` if it referenced the skill path. README "Public/private split" + consulting-layer description.

**Files:** `CLAUDE.md`, `README.md`, `scripts/sync-private.sh`

- [ ] **Step 1:** Edit the docs; replace trigger-phrase row with: consultant is now `python -m consultant_engine …`.
- [ ] **Step 2:** Verify `scripts/sync-private.sh` still resolves outputs (proposals dir unchanged).
- [ ] **Step 3: Commit** `docs: point consultant docs at consultant_engine CLI`

### Task 5.3: CI + golden anchor

Confirm `.github/workflows/ci.yml` `pytest` covers `tests/consultant_engine/`. Pin one curated proposal as the **golden anchor** referenced by the spec §14 parity item (a `test_golden_structure` asserting the engine's fake-LLM output matches the golden's section/slot structure).

**Files:** `.github/workflows/ci.yml` (verify only), `tests/consultant_engine/test_golden.py`

- [ ] **Step 1: Failing test** — engine fake-LLM output and the golden share identical `LOCKED_SECTIONS` order + numeric-slot keys.
- [ ] **Step 2–4: red → implement → green.**
- [ ] **Step 5: Commit** `test(engine): golden structural parity anchor`

### Task 5.4: "Primitives ↔ framework" mapping note (deliverable 2)

A short doc mapping the hand-rolled orchestration primitives in the old skill to their LangGraph expressions in this engine — the learning artifact for the Phase-1 capstone.

**Files:** `docs/superpowers/notes/primitives-to-langgraph.md` (+ `.html` companion per the CLAUDE.md convention)

- [ ] **Step 1:** Write the note as a table — each row a primitive → its LangGraph expression → the file/line in `consultant_engine/` that realizes it:
  - conditional dispatch → `add_conditional_edges` (`graph.py` `_after_validate`)
  - retry-until-valid loop → `validate ⇄ repair` cycle + `MAX_REPAIR` cap
  - shared-state blackboard → `ConsultantState` TypedDict channels (`state.py`)
  - planner–executor → compute nodes produce plan (`portfolio`), generation executes it
  - agent handoff / subgraph → the ENH-6 macro-researcher seam (`macro.py` contract)
  - human-in-the-loop → `interrupt()` + SQLite checkpointer (`review_gate.py`)
  - tool use → openpyxl/PHS reads inside nodes
  - MCP-tool → node → the macro producer swap behind the contract
- [ ] **Step 2:** Generate the `.html` companion (same basename) per the standing convention.
- [ ] **Step 3: Commit** `docs: primitives↔LangGraph mapping note (Track 0 deliverable)`

**Final exit check:** `pip install -r requirements.txt pytest && pytest` fully green; `python -m consultant_engine --profile <p> --fundmaster <wb> -o /tmp` (review ON) pauses, writes the artifact, and `--resume` completes to a validator-passing proposal.

---

## Open items carried from spec §14 (decide as they arise)

- Exact `MAX` repair iterations (default 3) — encoded as `graph.MAX_REPAIR`.
- Macro-contract schema fields + theme taxonomy — Track 0 ships the contract + a fixture only; live producer is ENH-6.
- Fan-out vs single-node generation — **single-node is the default** here (Task 3.5); structural cards already templated out of the LLM set. Revisit only if isolation/repair-cost demands it.
- Model selection per node + token budget — `--model` flag; Sonnet default.

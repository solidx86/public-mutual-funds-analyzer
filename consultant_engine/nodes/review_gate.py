from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import consultant_engine
from consultant_engine.invariants import CAP, CEILING, SIZE
from consultant_engine.state import ConsultantState


# ---------------------------------------------------------------------------
# Artifact builder
# ---------------------------------------------------------------------------

def build_proposed_allocation(state: dict[str, Any]) -> dict:
    """Build the HITL review artifact (spec §7).

    Returns a dict that is serialisable to JSON and contains four top-level
    blocks: context, constraints, allocation, review.
    """
    profile = state["client_profile"]["risk_level"]
    min_size, max_size = SIZE[profile]

    # --- constraints (derived from invariants — no hardcoded numbers) ---
    constraints = {
        "_comment": (
            "Re-validation enforces these on resume. Stay within them or it "
            "re-pauses (review ON) / fails loudly (--no-review)."
        ),
        "allocations_sum_to_pct": 100,
        "fund_count": {"min": min_size, "max": max_size},
        "per_fund_cap_pct": CAP[profile],
        "risk_level_ceiling": CEILING[profile],
        "required_structural": {"gold": 1, "money_market": 1},
        "universe": (
            "scored eligible funds only (retail-eligible, risk <= ceiling, "
            "Shariah filter applied)"
        ),
    }

    # --- allocation block ---
    cfs_scores: list[dict] = state.get("cfs_scores") or []
    # Build lookup: abbr -> composite (and rank is 1-based position in the sorted list)
    cfs_by_abbr: dict[str, float | None] = {
        entry["abbr"]: entry["composite"] for entry in cfs_scores
    }
    rank_by_abbr: dict[str, int] = {
        entry["abbr"]: idx + 1 for idx, entry in enumerate(cfs_scores)
    }

    # Risk level lookup — try filtered_funds first, then eligible_funds
    fund_list: list[dict] = state.get("filtered_funds") or state.get("eligible_funds") or []
    rl_by_abbr: dict[str, int | None] = {
        f["abbr"]: f.get("risk_level") for f in fund_list
    }

    # Scored universe set (present in cfs_scores OR eligible_funds)
    scored_universe: set[str] = set(cfs_by_abbr.keys()) | {f["abbr"] for f in fund_list}

    allocation: list[dict] = []
    for holding in state.get("portfolio") or []:
        abbr = holding["abbr"]
        entry: dict[str, Any] = {
            "abbrev": abbr,
            "role": holding["role"],
            "allocation_pct": holding["allocation_pct"],
            "cfs": cfs_by_abbr.get(abbr),          # None if not scored
            "rank": rank_by_abbr.get(abbr),         # None if not scored
            "risk_level": rl_by_abbr.get(abbr),     # None if not in fund list
            "eligible": abbr in scored_universe,
        }
        allocation.append(entry)

    # --- context block ---
    context = {
        "client_profile": state["client_profile"],
        "fundmaster": state.get("fundmaster_path", ""),
        "engine_version": consultant_engine.__version__,
        "generated_at": datetime.now().astimezone().isoformat(),
    }

    return {
        "thread_id": state["thread_id"],
        "schema_version": "1.0",
        "context": context,
        "constraints": constraints,
        "allocation": allocation,
        "review": {"decision": "approve", "note": ""},
    }


# ---------------------------------------------------------------------------
# Artifact writer
# ---------------------------------------------------------------------------

def write_artifact(directory: str | Path, thread_id: str, artifact: dict) -> Path:
    """Write ``<directory>/<thread_id>.json`` (pretty) and a read-only HTML preview.

    Creates the directory if it does not exist.  Returns the JSON Path.
    """
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{thread_id}.json"
    json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))

    html_path = out_dir / f"{thread_id}.html"
    html_path.write_text(_build_html(artifact))

    return json_path


def _build_html(artifact: dict) -> str:
    """Return a simple read-only HTML preview of the allocation."""
    thread_id = artifact.get("thread_id", "")
    generated_at = artifact.get("context", {}).get("generated_at", "")
    rows = ""
    for e in artifact.get("allocation", []):
        rows += (
            f"<tr>"
            f"<td>{e['abbrev']}</td>"
            f"<td>{e['role']}</td>"
            f"<td>{e['allocation_pct']}</td>"
            f"<td>{e['cfs'] if e['cfs'] is not None else '—'}</td>"
            f"<td>{e['rank'] if e['rank'] is not None else '—'}</td>"
            f"<td>{e['risk_level'] if e['risk_level'] is not None else '—'}</td>"
            f"</tr>\n"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Review Preview — {thread_id}</title>
<style>
  body {{ font-family: sans-serif; padding: 1rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
  th {{ background: #f0f0f0; }}
  .notice {{ background: #fffbe6; border: 1px solid #e6c800; padding: 0.6rem 1rem;
             margin-bottom: 1rem; border-radius: 4px; }}
</style>
</head>
<body>
<div class="notice">
  <strong>READ-ONLY PREVIEW</strong> — this file is regenerated automatically.
  To edit the allocation, modify the JSON file (<code>{thread_id}.json</code>)
  and resume the graph run.
</div>
<h2>Proposed Allocation — thread <code>{thread_id}</code></h2>
<p>Generated at: {generated_at}</p>
<table>
  <thead>
    <tr>
      <th>Abbrev</th>
      <th>Role</th>
      <th>Allocation %</th>
      <th>CFS</th>
      <th>Rank</th>
      <th>Risk Level</th>
    </tr>
  </thead>
  <tbody>
{rows}  </tbody>
</table>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Stubs kept for Task 2.2
# ---------------------------------------------------------------------------

def review_gate(state: ConsultantState) -> dict:
    return {}


def read_resume_payload(thread_id: str) -> dict:
    """Stub: Task 2.2 replaces this with real file-based resume payload reader."""
    return {"decision": "approve"}


# ---------------------------------------------------------------------------
# Task 2.2 — resume re-validation
# ---------------------------------------------------------------------------

_GOLD_ABBR = "PeEMAS"
_MONEY_MARKET_ABBRS = {"PeCDF-A", "PIMMF-A"}


def _role_for(abbr: str) -> str:
    """Derive the structural role for a fund abbreviation."""
    if abbr == _GOLD_ABBR:
        return "structural:gold"
    if abbr in _MONEY_MARKET_ABBRS:
        return "structural:money_market"
    return "core"


def apply_resume(state: dict[str, Any], resume_payload: dict[str, Any]) -> dict[str, Any]:
    """Re-validate a human-edited resume payload against engine-derived facts.

    Parameters
    ----------
    state:
        Current ConsultantState (facts come from here, never from the payload).
    resume_payload:
        Parsed content of data/review/<thread_id>.json returned by interrupt().

    Returns
    -------
    {}
        Bare approve-as-is (no ``"allocation"`` key in payload) — existing
        ``state["portfolio"]`` stands unchanged.
    {"violations": [...]}
        The edited allocation violated one or more invariants.
    {"portfolio": [...], "violations": []}
        The edited allocation passed all invariants; caller should merge into
        state.
    """
    # Step 1: bare approve — no allocation key means approve-as-is
    if "allocation" not in resume_payload:
        return {}

    # Step 2: extract only abbrev + allocation_pct from payload; derive the rest
    allocation_entries = resume_payload["allocation"]
    holdings = [
        {
            "abbr": e["abbrev"],
            "role": _role_for(e["abbrev"]),
            "allocation_pct": e["allocation_pct"],
        }
        for e in allocation_entries
    ]

    # Step 4: re-derive validation inputs from state (NOT from payload)
    profile = state["client_profile"]["risk_level"]
    universe: set[str] = state.get("_universe") or {
        f["abbr"] for f in state.get("eligible_funds", [])
    }
    fund_list: list[dict] = (
        state.get("filtered_funds") or state.get("eligible_funds") or []
    )
    rl_by_abbr: dict[str, int | None] = {
        f["abbr"]: f.get("risk_level") for f in fund_list
    }

    # Step 5: run invariant check
    from consultant_engine.invariants import check_invariants
    violations = check_invariants(holdings, profile, universe, rl_by_abbr)

    # Step 6: return
    if violations:
        return {"violations": violations}
    return {"portfolio": holdings, "violations": []}


def read_resume_payload(thread_id: str) -> dict[str, Any]:
    """Read data/review/<thread_id>.json and return parsed dict.

    Falls back to ``{"decision": "approve"}`` when the file does not exist,
    so a resume without an edited file still proceeds as approve-as-is.
    """
    review_path = Path("data/review") / f"{thread_id}.json"
    if not review_path.exists():
        return {"decision": "approve"}
    return json.loads(review_path.read_text())

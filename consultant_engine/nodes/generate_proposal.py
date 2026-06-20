"""
consultant_engine/nodes/generate_proposal.py — Task 3.5

generate_proposal(state) -> {"proposal_html": <full html string>}

Steps:
  1. Load skeleton + CSS.
  2. Foundation block: keep content (strip markers only) for new investors; remove entire
     block (markers + content) for experienced investors.
  3. Build per-fund card HTML dynamically (render_structural_card for structural holdings;
     a deterministic card for core/alpha holdings). Substitute into <!--slot:fund_cards-->.
  4. Build fee-table rows for <!--slot:fee_table.fund_rows-->.
  5. Build portfolio-summary rows for <!--slot:portfolio_summary.fund_rows-->.
  6. Numeric prefill: call fill_slots(skeleton, slot_values) for all live data-slot keys.
  7. Prose fill: replace each <!--slot:KEY--> marker with prose.
     - Fake-LLM mode (CONSULTANT_ENGINE_FAKE_LLM=1): replace each marker with a readable
       placeholder like "[KEY narrative]".
     - Real-LLM mode: pass the numerically-filled document to llm.complete for prose authoring.
  8. Return {"proposal_html": result}.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import consultant_engine
from consultant_engine.llm import complete
from consultant_engine.state import ConsultantState
from consultant_engine.templates import fill_slots, render_structural_card

_ASSETS = Path(__file__).parent.parent / "assets"
_SKELETON_PATH = _ASSETS / "proposal_skeleton.html"
_CSS_PATH = _ASSETS / "design_system.css"
_PROMPT_PATH = _ASSETS / "prompts" / "generate_proposal.md"

# ─── Foundation block ────────────────────────────────────────────────────────
_FOUNDATION_BLOCK_RE = re.compile(
    r"<!--FOUNDATION_START-->.*?<!--FOUNDATION_END-->",
    re.DOTALL,
)
_FOUNDATION_START_MARKER = "<!--FOUNDATION_START-->"
_FOUNDATION_END_MARKER = "<!--FOUNDATION_END-->"

# ─── prose slot replacement ──────────────────────────────────────────────────
_PROSE_SLOT_RE = re.compile(r"<!--slot:([^>]+)-->")


# ─── Foundation handling ──────────────────────────────────────────────────────

def _handle_foundation_block(skeleton: str, experience: str) -> str:
    """Keep Foundation content (strip markers only) for new investors;
    remove entire block for experienced investors."""
    if experience == "new":
        # Keep the Foundation content — just strip the marker comments
        skeleton = skeleton.replace(_FOUNDATION_START_MARKER, "")
        skeleton = skeleton.replace(_FOUNDATION_END_MARKER, "")
    else:
        # Remove the entire block (markers + content including the .page wrapper)
        skeleton = _FOUNDATION_BLOCK_RE.sub("", skeleton)
    return skeleton


# ─── helpers ─────────────────────────────────────────────────────────────────

def _lookup_fund(abbr: str, eligible_funds: list[dict]) -> dict:
    """Return the fund dict for a given abbr, or a minimal fallback."""
    for f in eligible_funds:
        if f.get("abbr") == abbr:
            return f
    return {"abbr": abbr, "name": abbr, "risk_level": 3}


def _cfs_for(abbr: str, cfs_scores: list[dict]) -> dict | None:
    """Return the CFS score dict for abbr, or None if not found."""
    for c in cfs_scores:
        if c.get("abbr") == abbr:
            return c
    return None


def _build_core_fund_card(holding: dict, fund: dict, cfs: dict | None, e_target: float) -> str:
    """Build a fund-card HTML block for a core/alpha holding (not structural)."""
    abbr = holding["abbr"]
    alloc = holding["allocation_pct"]
    name = fund.get("name", abbr)
    rl = fund.get("risk_level", "—")
    disqualified = fund.get("status") == "Disqualified"

    # CFS values
    if cfs:
        composite = cfs.get("composite", 0)
        alpha_n = cfs.get("alpha_n", 0)
        returnfit_n = cfs.get("returnfit_n", 0)
        efficiency_n = cfs.get("efficiency_n", 0)
        momentum_n = cfs.get("momentum_n", 0)
        weights = cfs.get("weights", {"alpha": 28, "returnfit": 40, "efficiency": 20, "momentum": 12})
        alpha_w = weights.get("alpha", 28)
        returnfit_w = weights.get("returnfit", 40)
        efficiency_w = weights.get("efficiency", 20)
        momentum_w = weights.get("momentum", 12)
    else:
        composite = alpha_n = returnfit_n = efficiency_n = momentum_n = 0
        alpha_w = returnfit_w = efficiency_w = momentum_w = 0

    return f"""\
<div class="fund-card">
  <div class="fund-card-header equity">
    <h3>{name} &middot; {abbr}</h3>
    <span class="alloc">{alloc}%</span>
  </div>
  <div class="fund-meta">
    <span><strong>Type:</strong> <!--slot:meta.{abbr}.type--></span>
    <span><strong>RL:</strong> {rl}</span>
    <span><strong>VF:</strong> —</span>
    <span><strong>Shariah:</strong> <!--slot:meta.{abbr}.shariah--></span>
    <span><strong>AUM:</strong> RM —M</span>
    <span><strong>Lipper:</strong> <!--slot:meta.{abbr}.lipper--></span>
  </div>
  <div class="fund-card-body">
    {"<div class=\"alpha-warning\"><!--slot:alpha_warning." + abbr + "--></div>" if disqualified else ""}
    <div class="cfs-bar">
      <div class="cfs-title">COMPOSITE FUND SCORE: {composite} / 100</div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Alpha (Manager Skill)</span>
          <span>{alpha_n} / 100 &middot; {alpha_w}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill alpha" style="width:{alpha_n}%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Return Fit (vs {e_target}% target)</span>
          <span>{returnfit_n} / 100 &middot; {returnfit_w}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill return-fit" style="width:{returnfit_n}%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Efficiency (Risk-Adjusted)</span>
          <span>{efficiency_n} / 100 &middot; {efficiency_w}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill efficiency" style="width:{efficiency_n}%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Momentum (ATH Proximity)</span>
          <span>{momentum_n} / 100 &middot; {momentum_w}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill momentum" style="width:{momentum_n}%;"></div></div>
      </div>
    </div>
    <h4>Performance vs Benchmark</h4>
    <div class="table-wrap">
      <table class="perf-table">
        <thead><tr><th>Period</th><th>Fund %</th><th>Bench %</th><th>Alpha %</th></tr></thead>
        <tbody><!--slot:perf.{abbr}.rows--></tbody>
      </table>
    </div>
    <h4>Cost &amp; Alpha</h4>
    <div class="cost-alpha-mini">
      <div class="cell"><span class="label">Sales Charge</span><span class="value">—</span></div>
      <div class="cell"><span class="label">Mgmt Fee p.a.</span><span class="value">—</span></div>
      <div class="cell"><span class="label">Trustee Fee p.a.</span><span class="value">—</span></div>
      <div class="cell"><span class="label">Annual Cost</span><span class="value">—</span></div>
      <div class="cell"><span class="label">3Y Alpha</span><span class="value">—</span></div>
      <div class="cell"><span class="label">Net Value-Add</span><span class="value">—</span></div>
      <div class="source">Fees from <code>{abbr}_PHS.pdf</code> &middot; PHS dated <!--slot:fees.{abbr}.phs_date--></div>
    </div>
    <h4>Why We Chose It</h4>
    <p><!--slot:why.{abbr}--></p>
    <h4>What to Watch</h4>
    <ul><!--slot:watch.{abbr}--></ul>
  </div>
</div>"""


def _build_fund_cards_html(portfolio: list[dict], cfs_scores: list[dict],
                            eligible_funds: list[dict], e_target: float) -> str:
    """Build the full fund-cards section HTML: one card per holding."""
    cards = []
    for holding in portfolio:
        abbr = holding["abbr"]
        role = holding.get("role", "core")
        fund = _lookup_fund(abbr, eligible_funds)
        if role in ("structural:gold", "structural:money_market"):
            cards.append(render_structural_card(holding, fund))
        else:
            cfs = _cfs_for(abbr, cfs_scores)
            cards.append(_build_core_fund_card(holding, fund, cfs, e_target))
    return "\n".join(cards)


def _build_fee_table_rows(portfolio: list[dict]) -> str:
    """Build fee table <tr> rows for Section 8."""
    rows = []
    for holding in portfolio:
        abbr = holding["abbr"]
        rows.append(
            f"<tr>"
            f"<td><strong>{abbr}</strong></td>"
            f"<td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>"
            f"<td><!--slot:fees.{abbr}.phs_date--></td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _build_portfolio_summary_rows(portfolio: list[dict], cfs_scores: list[dict],
                                   eligible_funds: list[dict]) -> str:
    """Build portfolio summary table <tr> rows for Section 5."""
    rows = []
    for holding in portfolio:
        abbr = holding["abbr"]
        alloc = holding["allocation_pct"]
        fund = _lookup_fund(abbr, eligible_funds)
        rl = fund.get("risk_level", "—")
        role = holding.get("role", "core")
        cfs = _cfs_for(abbr, cfs_scores)
        cfs_val = f"{cfs['composite']}" if cfs else "—"
        alpha_val = f"{cfs['alpha_n']}" if cfs else "—"
        ftype = (
            "Gold" if role == "structural:gold"
            else ("Money Market" if role == "structural:money_market" else "Equity")
        )
        rows.append(
            f"<tr><td>{abbr}</td><td>{ftype}</td><td>{alloc}%</td>"
            f"<td>{cfs_val}</td><td>{alpha_val}</td><td>RL{rl}</td></tr>"
        )
    return "\n".join(rows)


def _compute_portfolio_metrics(portfolio: list[dict], cfs_scores: list[dict],
                                eligible_funds: list[dict]) -> dict:
    """Compute weighted portfolio metrics from portfolio holdings + CFS scores."""
    wtd_cfs = 0.0
    wtd_alpha = 0.0
    wtd_rl = 0.0
    for holding in portfolio:
        abbr = holding["abbr"]
        alloc = holding["allocation_pct"] / 100.0
        cfs = _cfs_for(abbr, cfs_scores)
        fund = _lookup_fund(abbr, eligible_funds)
        rl = fund.get("risk_level", 3)
        if cfs:
            wtd_cfs += cfs.get("composite", 0) * alloc
            wtd_alpha += cfs.get("alpha_n", 0) * alloc
        wtd_rl += rl * alloc
    return {
        "wtd_cfs": f"{wtd_cfs:.1f}",
        "wtd_alpha": f"{wtd_alpha:.1f}",
        "wtd_rl": f"{wtd_rl:.1f}",
    }


def _build_slot_values(state: ConsultantState, portfolio_metrics: dict) -> dict:
    """Build the slot_values dict for fill_slots — covering all live data-slot keys
    in the cleaned skeleton."""
    client = state["client_profile"]
    portfolio = state["portfolio"]
    eligible_funds = state.get("eligible_funds", [])

    e_target = client.get("e_target", 8.0)
    funds_selected = len(portfolio)
    funds_screened = len(eligible_funds)

    return {
        # Scalar {{...}} replacements
        "version": consultant_engine.__version__,
        "design_system_css": _CSS_PATH.read_text(encoding="utf-8").replace(
            "[SKILL_VERSION]", consultant_engine.__version__
        ),
        # Cover
        "cover.e_target": str(e_target),
        "cover.funds_selected_n": str(funds_selected),
        "cover.funds_screened_m": str(funds_screened),
        # Profile
        "profile.e_target": str(e_target),
        # Portfolio (weighted)
        "portfolio.cfs_composite": portfolio_metrics["wtd_cfs"],
        "portfolio.alpha_3y": portfolio_metrics["wtd_alpha"],
        "portfolio.vf": "—",
        "portfolio.wtd_cfs": portfolio_metrics["wtd_cfs"],
        "portfolio.wtd_alpha": portfolio_metrics["wtd_alpha"],
        "portfolio.wtd_rl": portfolio_metrics["wtd_rl"],
        # Exposure — placeholders (look-through data not in state for this task)
        "exposure.asset.domestic_equity_pct": "—",
        "exposure.asset.foreign_equity_pct": "—",
        "exposure.asset.fixed_income_pct": "—",
        "exposure.asset.money_market_pct": "—",
        "exposure.asset.gold_pct": "—",
    }


def _fill_prose_slots_fake(html: str) -> str:
    """Replace all <!--slot:KEY--> markers with readable placeholders (fake-LLM mode)."""
    def _replace(m: re.Match) -> str:
        key = m.group(1).strip()
        return f"[{key} narrative]"
    return _PROSE_SLOT_RE.sub(_replace, html)


def _fill_prose_slots_llm(html: str, state: ConsultantState) -> str:
    """Send the numerically-filled document to the LLM for prose authoring."""
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    client = state["client_profile"]
    portfolio = state["portfolio"]
    macro = state.get("macro_context", {})
    cfs_scores = state.get("cfs_scores", [])
    fundmaster_path = state.get("fundmaster_path", "")

    context_block = (
        f"Client profile: {client}\n"
        f"Portfolio: {portfolio}\n"
        f"CFS scores: {cfs_scores}\n"
        f"Macro context: {macro}\n"
        f"FundMaster: {fundmaster_path}\n\n"
        f"Document (fill each <!--slot:KEY--> with appropriate prose):\n\n{html}"
    )

    result = complete(context_block, system=system_prompt)

    # If LLM didn't fill prose slots inline, fall back to fake placeholders
    if "<!--slot:" in result:
        return _fill_prose_slots_fake(result)
    return result


def generate_proposal(state: ConsultantState) -> dict:
    """Turn the locked skeleton + deterministic state into a complete proposal HTML.

    Returns
    -------
    dict with key ``proposal_html`` containing the fully-filled HTML string.
    """
    # 1. Load skeleton
    skeleton = _SKELETON_PATH.read_text(encoding="utf-8")

    # 2. Foundation block handling (before any slot substitution)
    experience = state["client_profile"].get("experience", "experienced")
    skeleton = _handle_foundation_block(skeleton, experience)

    # 3. Build dynamic per-fund HTML sections from state
    portfolio = state["portfolio"]
    cfs_scores = state.get("cfs_scores", [])
    eligible_funds = state.get("eligible_funds", [])
    e_target = state["client_profile"].get("e_target", 8.0)

    fund_cards_html = _build_fund_cards_html(portfolio, cfs_scores, eligible_funds, e_target)
    fee_rows_html = _build_fee_table_rows(portfolio)
    portfolio_summary_rows = _build_portfolio_summary_rows(portfolio, cfs_scores, eligible_funds)

    # Substitute dynamic sections at their prose-slot markers BEFORE fill_slots
    skeleton = skeleton.replace("<!--slot:fund_cards-->", fund_cards_html)
    skeleton = skeleton.replace("<!--slot:fee_table.fund_rows-->", fee_rows_html)
    skeleton = skeleton.replace("<!--slot:portfolio_summary.fund_rows-->", portfolio_summary_rows)

    # 4. Compute portfolio metrics
    portfolio_metrics = _compute_portfolio_metrics(portfolio, cfs_scores, eligible_funds)

    # 5. Numeric prefill via fill_slots (raises on any unfilled data-slot)
    slot_values = _build_slot_values(state, portfolio_metrics)
    skeleton = fill_slots(skeleton, slot_values)

    # 6. Prose fill
    fake_mode = bool(os.environ.get("CONSULTANT_ENGINE_FAKE_LLM"))
    if fake_mode:
        html = _fill_prose_slots_fake(skeleton)
    else:
        html = _fill_prose_slots_llm(skeleton, state)

    return {"proposal_html": html}

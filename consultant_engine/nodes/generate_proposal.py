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
from datetime import datetime
from pathlib import Path

import consultant_engine
from consultant_engine import exposure
from consultant_engine.llm import complete, complete_with_usage
from consultant_engine.nodes.filter_universe import RISK_CEILING
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


# ─── Deterministic (Python-owned) fact rendering ──────────────────────────────
# These cells are facts the determinism thesis reserves for Python, never the
# LLM: per-fund performance rows, fund metadata, and macro Event/Date cells.

_PERIOD_LABELS = [("ytd", "YTD"), ("1y", "1Y"), ("3y", "3Y"), ("5y", "5Y"), ("10y", "10Y")]


def _fmt_pct(v) -> str:
    """Format a percentage cell: an em-dash for None, else the compact ``%g`` form."""
    return "&mdash;" if v is None else f"{v:g}"


def _build_perf_rows(returns: dict) -> str:
    """Deterministic <tr> rows for the per-fund performance table.

    Rows are Python-owned: Alpha is shown as stored, and the validator
    re-checks Alpha == Fund - Bench.
    """
    rows = []
    returns = returns or {}
    for key, label in _PERIOD_LABELS:
        period = returns.get(key) or {}
        fund = period.get("fund")
        bench = period.get("bench")
        alpha = period.get("alpha")
        if fund is None and bench is None and alpha is None:
            continue  # period absent entirely — omit the row
        if alpha is None:
            alpha_cell = "<td>&mdash;</td>"
        else:
            cls = "alpha-pos" if alpha >= 0 else "alpha-neg"
            sign = "+" if alpha >= 0 else ""
            alpha_cell = f'<td class="{cls}">{sign}{alpha:g}</td>'
        rows.append(
            f"<tr><td>{label}</td><td>{_fmt_pct(fund)}</td>"
            f"<td>{_fmt_pct(bench)}</td>{alpha_cell}</tr>"
        )
    return "\n".join(rows)


def _fmt_macro_date(raw: str) -> str:
    """Format an ISO macro date as '%d %b %Y'; pass non-ISO strings (e.g. 'Q2 2026') through."""
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return raw if raw else "&mdash;"   # non-ISO like "Q2 2026" passes through


def _build_macro_rows(events: list) -> str:
    """Deterministic macro <tr> rows: Event + Date are Python-owned facts;
    each row's Implication stays a prose slot the LLM fills."""
    rows = []
    for i, ev in enumerate(events or []):
        claim = ev.get("claim", "")
        date = _fmt_macro_date(ev.get("date", ""))
        rows.append(
            f"<tr><td>{claim}</td><td>{date}</td>"
            f"<td><!--slot:macro.impact.{i}--></td></tr>"
        )
    return "\n".join(rows)


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


_DEFAULT_CFS_WEIGHTS = {"alpha": 28, "returnfit": 40, "efficiency": 20, "momentum": 12}


def _cfs_card_values(cfs: dict | None) -> dict:
    """Scalar scores + dimension weights a fund card renders. No score → all zeros
    (an unscored card shows 0/100 at 0% weight, never the default weights)."""
    score_keys = ("composite", "alpha_n", "returnfit_n", "efficiency_n", "momentum_n")
    weight_keys = ("alpha_w", "returnfit_w", "efficiency_w", "momentum_w")
    if not cfs:
        return {k: 0 for k in (*score_keys, *weight_keys)}
    weights = cfs.get("weights", _DEFAULT_CFS_WEIGHTS)
    return {
        **{k: cfs.get(k, 0) for k in score_keys},
        "alpha_w": weights.get("alpha", 28),
        "returnfit_w": weights.get("returnfit", 40),
        "efficiency_w": weights.get("efficiency", 20),
        "momentum_w": weights.get("momentum", 12),
    }


def _build_core_fund_card(holding: dict, fund: dict, cfs: dict | None, target_annual_return_pct: float) -> str:
    """Build a fund-card HTML block for a core/alpha holding (not structural)."""
    abbr = holding["abbr"]
    alloc = holding["allocation_pct"]
    name = fund.get("name", abbr)
    fund_risk_level = fund.get("risk_level", "—")
    disqualified = fund.get("status") == "Disqualified"
    c = _cfs_card_values(cfs)

    # Python-owned facts (C2b): rendered inline, never authored by the LLM.
    fund_type = fund.get("fund_type") or "&mdash;"
    shariah = "Shariah" if fund.get("shariah") else "Conventional"
    lipper = fund.get("lipper_class") or "&mdash;"
    volatility_factor = f"{fund['volatility_factor']:g}" if fund.get("volatility_factor") is not None else "&mdash;"

    perf_rows = _build_perf_rows(fund.get("returns", {}))

    return f"""\
<div class="fund-card">
  <div class="fund-card-header equity">
    <h3>{name} &middot; {abbr}</h3>
    <span class="alloc">{alloc}%</span>
  </div>
  <div class="fund-meta">
    <span><strong>Type:</strong> {fund_type}</span>
    <span><strong>RL:</strong> {fund_risk_level}</span>
    <span><strong>VF:</strong> {volatility_factor}</span>
    <span><strong>Shariah:</strong> {shariah}</span>
    <span><strong>AUM:</strong> &mdash;</span>
    <span><strong>Lipper:</strong> {lipper}</span>
  </div>
  <div class="fund-card-body">
    {"<div class=\"alpha-warning\"><!--slot:alpha_warning." + abbr + "--></div>" if disqualified else ""}
    <div class="cfs-bar">
      <div class="cfs-title">COMPOSITE FUND SCORE: <span class="cfs-score">{c['composite']}</span> / 100</div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Alpha (Manager Skill)</span>
          <span>{c['alpha_n']} / 100 &middot; {c['alpha_w']}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill alpha" style="width:{c['alpha_n']}%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Return Fit (vs {target_annual_return_pct}% target)</span>
          <span>{c['returnfit_n']} / 100 &middot; {c['returnfit_w']}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill return-fit" style="width:{c['returnfit_n']}%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Efficiency (Risk-Adjusted)</span>
          <span>{c['efficiency_n']} / 100 &middot; {c['efficiency_w']}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill efficiency" style="width:{c['efficiency_n']}%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label">
          <span>Momentum (ATH Proximity)</span>
          <span>{c['momentum_n']} / 100 &middot; {c['momentum_w']}% weight</span>
        </div>
        <div class="cfs-track"><div class="cfs-fill momentum" style="width:{c['momentum_n']}%;"></div></div>
      </div>
    </div>
    <h4>Performance vs Benchmark</h4>
    <div class="table-wrap">
      <table class="perf-table">
        <thead><tr><th>Period</th><th>Fund %</th><th>Bench %</th><th>Alpha %</th></tr></thead>
        <tbody>{perf_rows}</tbody>
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
      <div class="source">Fees pending PHS extraction &middot; source <code>{abbr}_PHS.pdf</code></div>
    </div>
    <h4>Why We Chose It</h4>
    <p><!--slot:why.{abbr}--></p>
    <h4>What to Watch</h4>
    <ul><!--slot:watch.{abbr}--></ul>
  </div>
</div>"""


def _build_fund_cards_html(portfolio: list[dict], cfs_scores: list[dict],
                            eligible_funds: list[dict], target_annual_return_pct: float) -> str:
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
            cards.append(_build_core_fund_card(holding, fund, cfs, target_annual_return_pct))
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
            f"<td>&mdash;</td>"
            f"</tr>"
        )
    return "\n".join(rows)


# Holding role → portfolio-summary "Type" label; core/alpha holdings fall back to Equity.
_ROLE_LABEL = {"structural:gold": "Gold", "structural:money_market": "Money Market"}


def _build_portfolio_summary_rows(portfolio: list[dict], cfs_scores: list[dict],
                                   eligible_funds: list[dict]) -> str:
    """Build portfolio summary table <tr> rows for Section 5."""
    rows = []
    for holding in portfolio:
        abbr = holding["abbr"]
        alloc = holding["allocation_pct"]
        fund = _lookup_fund(abbr, eligible_funds)
        fund_risk_level = fund.get("risk_level", "—")
        role = holding.get("role", "core")
        cfs = _cfs_for(abbr, cfs_scores)
        cfs_val = f"{cfs['composite']}" if cfs else "—"
        alpha_val = f"{cfs['alpha_n']}" if cfs else "—"
        ftype = _ROLE_LABEL.get(role, "Equity")
        rows.append(
            f"<tr><td>{abbr}</td><td>{ftype}</td><td>{alloc}%</td>"
            f"<td>{cfs_val}</td><td>{alpha_val}</td><td>RL{fund_risk_level}</td></tr>"
        )
    return "\n".join(rows)


def _compute_portfolio_metrics(portfolio: list[dict], cfs_scores: list[dict],
                                eligible_funds: list[dict]) -> dict:
    """Compute weighted portfolio metrics from portfolio holdings + CFS scores."""
    weighted_cfs = 0.0
    weighted_alpha = 0.0
    weighted_risk_level = 0.0
    for holding in portfolio:
        abbr = holding["abbr"]
        alloc = holding["allocation_pct"] / 100.0
        cfs = _cfs_for(abbr, cfs_scores)
        fund = _lookup_fund(abbr, eligible_funds)
        fund_risk_level = fund.get("risk_level", 3)
        if cfs:
            weighted_cfs += cfs.get("composite", 0) * alloc
            weighted_alpha += cfs.get("alpha_n", 0) * alloc
        weighted_risk_level += fund_risk_level * alloc
    return {
        "weighted_cfs": f"{weighted_cfs:.1f}",
        "weighted_alpha": f"{weighted_alpha:.1f}",
        "weighted_risk_level": f"{weighted_risk_level:.1f}",
    }


def _build_slot_values(
    state: ConsultantState, portfolio_metrics: dict, asset_exposure: dict[str, float]
) -> dict:
    """Build the slot_values dict for fill_slots — covering all live data-slot keys
    in the cleaned skeleton."""
    client = state["client_profile"]
    portfolio = state["portfolio"]
    eligible_funds = state.get("eligible_funds", [])

    target_annual_return_pct = client["target_annual_return_pct"]   # guaranteed by load_profile (setdefault); fail loud if absent
    funds_selected = len(portfolio)
    funds_screened = len(eligible_funds)

    return {
        # Scalar {{...}} replacements
        "version": consultant_engine.__version__,
        "design_system_css": _CSS_PATH.read_text(encoding="utf-8").replace(
            "[SKILL_VERSION]", consultant_engine.__version__
        ),
        # Cover
        "cover.target_annual_return_pct": str(target_annual_return_pct),
        "cover.funds_selected_n": str(funds_selected),
        "cover.funds_screened_m": str(funds_screened),
        # Profile
        "profile.target_annual_return_pct": str(target_annual_return_pct),
        # Portfolio (weighted)
        "portfolio.cfs_composite": portfolio_metrics["weighted_cfs"],
        "portfolio.alpha_3y": portfolio_metrics["weighted_alpha"],
        "portfolio.volatility_factor": "—",
        "portfolio.weighted_cfs": portfolio_metrics["weighted_cfs"],
        "portfolio.weighted_alpha": portfolio_metrics["weighted_alpha"],
        "portfolio.weighted_risk_level": portfolio_metrics["weighted_risk_level"],
        # Exposure — deterministic look-through (Python-owned, never the LLM's).
        "exposure.asset.domestic_equity_pct": f"{asset_exposure['exposure.asset.domestic_equity_pct']}%",
        "exposure.asset.foreign_equity_pct": f"{asset_exposure['exposure.asset.foreign_equity_pct']}%",
        "exposure.asset.fixed_income_pct": f"{asset_exposure['exposure.asset.fixed_income_pct']}%",
        "exposure.asset.money_market_pct": f"{asset_exposure['exposure.asset.money_market_pct']}%",
        "exposure.asset.gold_pct": f"{asset_exposure['exposure.asset.gold_pct']}%",
    }


def _fill_prose_slots_fake(html: str) -> str:
    """Replace all <!--slot:KEY--> markers with readable placeholders (fake-LLM mode)."""
    def _replace(m: re.Match) -> str:
        key = m.group(1).strip()
        return f"[{key} narrative]"
    return _PROSE_SLOT_RE.sub(_replace, html)


def _collect_prose_keys(html: str) -> list[str]:
    """Unique, order-preserving list of remaining <!--slot:KEY--> prose keys."""
    return list(dict.fromkeys(k.strip() for k in _PROSE_SLOT_RE.findall(html)))


def _parse_prose_blocks(text: str) -> dict:
    """Parse ``@@@key@@@``-delimited blocks into ``{key: prose}``.

    Delimiter framing (not JSON) because slot values are HTML — embedded quotes,
    braces and newlines break JSON escaping (a real reply once parsed as 0/39). A
    marker line is ``@@@<key>@@@`` on its own line; the prose is everything up to the
    next marker, so HTML content can contain anything but that literal marker.
    """
    parts = re.split(r"(?m)^[ \t]*@@@([^@\n]+?)@@@[ \t]*$", text)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        key, body = parts[i].strip(), parts[i + 1].strip()
        if key:
            out[key] = body
    return out


def _fill_prose_slots_llm(html: str, state: ConsultantState) -> str:
    """Author prose via the LLM WITHOUT round-tripping the document.

    The model returns only a JSON map of slot-key -> prose; Python substitutes each
    fragment into the skeleton it owns. The document structure is therefore never at
    the model's mercy: a malformed or missing value degrades to a per-slot placeholder,
    never a broken doc. (The old whole-document round-trip silently failed against a
    real model — it truncated/paraphrased and dropped every section.)
    """
    keys = _collect_prose_keys(html)
    if not keys:
        return html

    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    instruction = (
        "Author the prose for this Public Mutual investment proposal using the client "
        "context below. For EACH slot key, output a line containing exactly @@@<key>@@@ "
        "on its own line, then the slot's HTML prose on the following line(s). Fill EVERY "
        "key listed. For keys starting 'watch.' output 2-4 <li>…</li> items; for every "
        "other key output inline HTML with no wrapping block tag. Output nothing except "
        "these @@@<key>@@@ blocks.\n\n"
        f"Client profile: {state['client_profile']}\n"
        f"Portfolio: {state['portfolio']}\n"
        f"CFS scores: {state.get('cfs_scores', [])}\n"
        f"Macro context: {state.get('macro_context', {})}\n\n"
        f"Slot keys to fill ({len(keys)}):\n" + "\n".join(keys)
    )

    text, usage = complete_with_usage(instruction, model=state.get("model") or "claude-sonnet-4-6",
                                      system=system_prompt)
    filled = _parse_prose_blocks(text)

    missing = [k for k in keys if k not in filled]
    if usage.get("cost_usd"):
        print(f"  prose: {len(keys) - len(missing)}/{len(keys)} slots filled — "
              f"{usage['input_tokens']} in + {usage['output_tokens']} out tokens "
              f"≈ ${usage['cost_usd']:.4f}")
    if missing:
        print(f"  prose: {len(missing)} slot(s) fell back to placeholder: {missing[:6]}")

    return _PROSE_SLOT_RE.sub(lambda m: filled.get(m.group(1).strip(),
                                                    f"[{m.group(1).strip()} narrative]"), html)


def _workbook_month_year(fundmaster_path: str) -> str:
    """The source workbook's vintage as 'Mon YYYY' (e.g. 'Apr 2026'), parsed from its
    filename exactly like emit derives the proposal name — a Python-owned fact, never
    LLM-authored (the LLM used to guess today's month onto the cover Data Source)."""
    m = re.search(r"PublicMutual_FundMaster_([A-Za-z]+)(\d{4})_v", Path(fundmaster_path).name)
    return f"{m.group(1)} {m.group(2)}" if m else "&mdash;"


# ─── Profile facts are Python-owned (NOT LLM prose) ───────────────────────────
# These cells describe the client's risk profile / preferences. They are facts the
# pipeline already knows, so Python substitutes them before prose fill — the LLM
# never authors them and so can never drift them.

# 3-way Shariah preference label (client preference, NOT a per-fund workbook value).
_SHARIAH_LABEL = {
    True: "Shariah-compliant",
    False: "Conventional",
    None: "No preference (both)",
}

# One label-led sentence per risk profile (Section 3 "Profile" row).
_NAME_DESCRIPTION = {
    "Conservative": (
        "Conservative — capital preservation is the priority; you accept lower expected "
        "returns in exchange for low volatility and short-term stability."
    ),
    "Moderate": (
        "Moderate — a balanced investor seeking steady long-term growth while tolerating "
        "moderate short-term fluctuations."
    ),
    "Moderately Aggressive": (
        "Moderately Aggressive — growth-oriented; you pursue above-average returns and can "
        "withstand meaningful short-term volatility over a longer horizon."
    ),
    "Aggressive": (
        "Aggressive — maximum long-term growth is the goal; you accept high volatility and "
        "the potential for significant short-term losses."
    ),
}

# Fixed-income fund_type matcher (case-insensitive). Real workbook strings include
# "Fixed Income"; bond/sukuk variants are matched for robustness across vintages.
_BOND_RE = re.compile(r"bond|fixed\s*income|sukuk", re.IGNORECASE)


def _classify_holding(holding: dict, eligible_funds: list[dict]) -> str:
    """Classify a portfolio holding into a composition label.

    structural roles map directly; everything else is looked up in eligible_funds
    by abbr and classified by fund_type (fixed-income strings → bond, else equity).
    """
    role = holding.get("role", "core")
    if role == "structural:gold":
        return "gold"
    if role == "structural:money_market":
        return "MM"
    fund = _lookup_fund(holding["abbr"], eligible_funds)
    fund_type = fund.get("fund_type") or ""
    return "bond" if _BOND_RE.search(fund_type) else "equity"


# Display order for the composition string (omit zero counts).
_COMPOSITION_ORDER = ["equity", "bond", "gold", "MM"]


def _composition_string(portfolio: list[dict], eligible_funds: list[dict]) -> str:
    """e.g. '2 equity, 1 gold, 1 MM' — comma-joined '<n> <label>', zero counts omitted."""
    counts: dict[str, int] = {}
    for holding in portfolio:
        label = _classify_holding(holding, eligible_funds)
        counts[label] = counts.get(label, 0) + 1
    return ", ".join(f"{counts[label]} {label}" for label in _COMPOSITION_ORDER if counts.get(label))


def _profile_facts(state: ConsultantState) -> dict:
    """Map each Python-owned profile/cover/exec prose marker to its substituted value.

    Applied BEFORE prose fill in generate_proposal so these markers never reach the
    LLM (they then disappear from _collect_prose_keys). Mirrors the cover-facts block.
    """
    client = state["client_profile"]
    risk_level = client["risk_level"]
    portfolio = state["portfolio"]
    eligible_funds = state.get("eligible_funds", [])

    shariah_label = _SHARIAH_LABEL[client.get("shariah")]
    experience_label = (
        "New investor" if client.get("experience") == "new" else "Experienced investor"
    )
    # Computed realism warning when present, else the static within-range qualifier.
    target_note = client.get("target_note") or (
        f"within the realistic range for a {risk_level} profile — "
        "historical guide, not guaranteed"
    )
    macro_my = _workbook_month_year(state["fundmaster_path"])

    return {
        "<!--slot:cover.profile-->": risk_level,
        "<!--slot:exec_summary.profile-->": risk_level,
        "<!--slot:cover.shariah-->": shariah_label,
        "<!--slot:profile.shariah-->": shariah_label,
        "<!--slot:profile.experience_level-->": experience_label,
        "<!--slot:profile.rl_ceiling-->": str(RISK_CEILING[risk_level]),
        "<!--slot:profile.name_description-->": _NAME_DESCRIPTION[risk_level],
        "<!--slot:profile.target_note-->": target_note,
        "<!--slot:exec_summary.composition-->": _composition_string(portfolio, eligible_funds),
        "<!--slot:macro.month_year-->": f"in {macro_my}",
    }


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
    target_annual_return_pct = state["client_profile"]["target_annual_return_pct"]   # guaranteed by load_profile; fail loud if absent

    fund_cards_html = _build_fund_cards_html(portfolio, cfs_scores, eligible_funds, target_annual_return_pct)
    fee_rows_html = _build_fee_table_rows(portfolio)
    portfolio_summary_rows = _build_portfolio_summary_rows(portfolio, cfs_scores, eligible_funds)
    macro_rows_html = _build_macro_rows(state.get("macro_context", {}).get("events", []))

    # Portfolio Exposure (Section 6) — deterministic look-through. Python owns the
    # pies and the geo legend; the LLM never authors these numbers.
    funds_by_abbr = {f["abbr"]: f for f in eligible_funds if f.get("abbr")}
    asset_exposure = exposure.compute_asset_exposure(portfolio, funds_by_abbr)
    asset_pie_html = exposure.render_pie(exposure.asset_pie_slices(portfolio, funds_by_abbr))
    geo_slices = exposure.compute_geo_exposure(portfolio, funds_by_abbr)
    geo_pie_html = exposure.render_pie(exposure.geo_pie_pairs(geo_slices))
    geo_legend_html = exposure.render_geo_legend(geo_slices)

    # Substitute dynamic sections at their prose-slot markers BEFORE fill_slots
    skeleton = skeleton.replace("<!--slot:fund_cards-->", fund_cards_html)
    skeleton = skeleton.replace("<!--slot:fee_table.fund_rows-->", fee_rows_html)
    skeleton = skeleton.replace("<!--slot:portfolio_summary.fund_rows-->", portfolio_summary_rows)
    skeleton = skeleton.replace("<!--slot:macro.events_rows-->", macro_rows_html)
    skeleton = skeleton.replace("<!--slot:exposure.asset_class.pie_chart-->", asset_pie_html)
    skeleton = skeleton.replace("<!--slot:exposure.geo.pie_chart-->", geo_pie_html)
    skeleton = skeleton.replace("<!--slot:exposure.geo.legend_items-->", geo_legend_html)

    # Cover facts are Python-owned (NOT LLM prose): the Data Source month is the source
    # workbook's vintage (parsed from its filename, like emit), and the proposal/prepared
    # dates are today. Substituted before prose fill so the model can't author or drift them.
    _wb_my = _workbook_month_year(state["fundmaster_path"])
    _today = datetime.now().strftime("%d %b %Y")
    for _marker, _val in (
        ("<!--slot:cover.fundmaster_month_year-->", _wb_my),
        ("<!--slot:cover.month_year-->", _wb_my),
        ("<!--slot:cover.proposal_date-->", _today),
        ("<!--slot:cover.prepared_date-->", _today),
    ):
        skeleton = skeleton.replace(_marker, _val)

    # Profile facts are Python-owned too (risk level, Shariah/experience labels, RL
    # ceiling, name description, target note, composition, macro vintage). Substituted
    # before prose fill so they disappear from _collect_prose_keys — the LLM never
    # authors them. Each marker (e.g. cover.profile) may appear more than once.
    for _marker, _val in _profile_facts(state).items():
        skeleton = skeleton.replace(_marker, _val)

    # 4. Compute portfolio metrics
    portfolio_metrics = _compute_portfolio_metrics(portfolio, cfs_scores, eligible_funds)

    # 5. Numeric prefill via fill_slots (raises on any unfilled data-slot)
    slot_values = _build_slot_values(state, portfolio_metrics, asset_exposure)
    skeleton = fill_slots(skeleton, slot_values)

    # 6. Prose fill
    fake_mode = bool(os.environ.get("CONSULTANT_ENGINE_FAKE_LLM"))
    if fake_mode:
        html = _fill_prose_slots_fake(skeleton)
    else:
        html = _fill_prose_slots_llm(skeleton, state)

    return {"proposal_html": html}

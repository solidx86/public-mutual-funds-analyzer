"""
consultant_engine/templates.py — Task 3.2
Deterministic structural-card templating + slot fill.

Two public functions:
  render_structural_card(holding, fund) -> str
  fill_slots(skeleton, slot_values)     -> str

No LLM calls. All output is templated from inputs.

Slot-fill substitution method
──────────────────────────────
fill_slots works in three ordered passes:

  1. Scalar {{key}} replacements — {{version}} and {{design_system_css}} are
     replaced by their values in slot_values. After pass 1 any remaining
     {{...}} placeholder (other than prose <!--slot:-->) raises ValueError.

  2. data-slot="KEY" element text replacement — uses re.sub with a pattern
     that matches:
         data-slot="KEY"[optional whitespace]>[old text]<
     and replaces with:
         data-slot="KEY">[new_value]<
     This handles both self-closing-like and inline elements safely.
     After pass 2, any data-slot="..." attribute whose key was NOT in
     slot_values is collected and raises ValueError listing all missing keys.

  3. <!--slot:...--> prose markers are intentionally left untouched — they
     are the LLM's territory (Task 3.5).
"""

from __future__ import annotations

import re


# ─────────────────────────────────────────────────────────────────────────────
# render_structural_card
# ─────────────────────────────────────────────────────────────────────────────

_STRUCTURAL_ROLES = {"structural:gold", "structural:money_market"}

_GOLD_CARD_TEMPLATE = """\
<div class="fund-card">
  <div class="fund-card-header gold" style="border-left: 4px solid #b7791f;">
    <h3>{name} &middot; {abbr}</h3>
    <span class="alloc">{allocation_pct}%</span>
  </div>
  <div class="fund-meta">
    <span><strong>Type:</strong> Gold</span>
    <span><strong>Role:</strong> Structural — Gold / Inflation Hedge</span>
  </div>
  <div class="fund-card-body">
    {alpha_warning}
    <p style="color:var(--text-mid); font-style:italic; font-size:13px;">
      Structural position — allocated deterministically as a gold/inflation hedge,
      not selected through alpha-qualification screening.
    </p>
  </div>
</div>"""

_MM_CARD_TEMPLATE = """\
<div class="fund-card">
  <div class="fund-card-header money-market">
    <h3>{name} &middot; {abbr}</h3>
    <span class="alloc">{allocation_pct}%</span>
  </div>
  <div class="fund-meta">
    <span><strong>Type:</strong> Money Market</span>
    <span><strong>Role:</strong> Structural — Dry Powder / Liquidity Reserve</span>
  </div>
  <div class="fund-card-body">
    {alpha_warning}
    <p style="color:var(--text-mid); font-style:italic; font-size:13px;">
      Structural position — allocated deterministically as a liquidity reserve / dry powder,
      not selected through alpha-qualification screening.
    </p>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# render_alpha_warning — static, Python-owned disclosure block (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

# Lead sentence shared by every Disqualified holding, regardless of role.
_ALPHA_WARNING_LEAD = (
    "Disqualified &mdash; weighted alpha &le; 0%, below the qualification threshold."
)

# Role → trailing clause. The clause interpolates the holding's allocation %.
# Structural roles get their structural rationale; any other role (core/alpha)
# falls through to the generic diversifier clause via .get(role, default).
_ALPHA_WARNING_CLAUSE = {
    "structural:gold": (
        " Held at {allocation_pct}% as a structural gold / inflation hedge for "
        "diversification, not manager skill; we monitor its alpha trend."
    ),
    "structural:money_market": (
        " Held at {allocation_pct}% as a structural liquidity reserve (dry powder), "
        "not selected for alpha."
    ),
}

_ALPHA_WARNING_DEFAULT_CLAUSE = (
    " Included at {allocation_pct}% as a diversifier; we monitor alpha recovery over "
    "the coming quarters."
)


def render_alpha_warning(role: str, allocation_pct: int | float) -> str:
    """Static disclosure block (no LLM) for a Disqualified holding, varying by role.

    Returns the full ``<div class="alpha-warning">…</div>`` block. The lead states
    the disqualification fact (weighted alpha ≤ 0%); a role-specific clause then
    explains why the fund is still held at its allocation. core/alpha roles get the
    generic diversifier clause.

    Args:
        role: Holding role, e.g. ``"structural:gold"`` or ``"core"``.
        allocation_pct: The holding's allocation percentage (interpolated verbatim).

    Returns:
        The full ``<div class="alpha-warning">…</div>`` disclosure block string.
    """
    clause = _ALPHA_WARNING_CLAUSE.get(role, _ALPHA_WARNING_DEFAULT_CLAUSE).format(
        allocation_pct=allocation_pct
    )
    return f'<div class="alpha-warning">{_ALPHA_WARNING_LEAD}{clause}</div>'


def render_structural_card(holding: dict, fund: dict) -> str:
    """Return the HTML for a structural fund card (gold or money-market).

    Args:
        holding: Dict with keys ``abbr``, ``role``, ``allocation_pct``.
        fund: Dict with keys ``abbr``, ``name`` (and optionally others).

    Returns:
        Self-contained fund-card HTML (no LLM involvement).

    Raises:
        ValueError: If ``role`` is not one of the two recognised structural roles.
    """
    role = holding.get("role", "")
    if role not in _STRUCTURAL_ROLES:
        raise ValueError(
            f"render_structural_card: unrecognised role {role!r}. "
            f"Expected one of {sorted(_STRUCTURAL_ROLES)}."
        )

    abbr = fund.get("abbr", holding.get("abbr", ""))

    # Compliance disclosure gate: a structural sleeve carries the alpha-warning
    # block iff the fund failed screening in the workbook — rendered here by Python
    # as static disclosure text (no LLM) so the gate is deterministic for structural
    # roles too, exactly as _build_core_fund_card does for core holdings.
    disqualified = fund.get("status") == "Disqualified"
    alpha_warning = (
        render_alpha_warning(role, holding["allocation_pct"]) if disqualified else ""
    )

    ctx = {
        "abbr": abbr,
        "name": fund.get("name", ""),
        "allocation_pct": holding["allocation_pct"],
        "alpha_warning": alpha_warning,
    }

    if role == "structural:gold":
        return _GOLD_CARD_TEMPLATE.format(**ctx)
    else:  # structural:money_market
        return _MM_CARD_TEMPLATE.format(**ctx)


# ─────────────────────────────────────────────────────────────────────────────
# fill_slots
# ─────────────────────────────────────────────────────────────────────────────

# Matches data-slot="KEY"> ... < — captures the key and any existing inner text.
# The inner text may be empty or a placeholder like "0".
# Group 1 = key, Group 2 = old text content (may be empty).
_DATA_SLOT_RE = re.compile(r'data-slot="([^"]+)"(\s*)>([^<]*)<')

# Matches any remaining {{SOMETHING}} placeholder (not yet consumed).
_DOUBLE_BRACE_RE = re.compile(r'\{\{([^}]+)\}\}')


def fill_slots(skeleton: str, slot_values: dict) -> str:
    """Fill deterministic slots in the proposal skeleton string.

    Substitution method (three ordered passes):

    Pass 1 — Scalar {{key}} replacements:
        • Replaces ``{{version}}`` with slot_values["version"] (if present).
        • Replaces ``{{design_system_css}}`` with slot_values["design_system_css"]
          (if present).
        • Any remaining ``{{...}}`` placeholders raise ValueError.

    Pass 2 — data-slot="KEY" element text replacement:
        • For every ``data-slot="KEY">OLD<`` pattern found, if KEY is in
          slot_values the OLD text is replaced with slot_values[KEY].
        • After pass 2, any data-slot attribute whose key was *not* in
          slot_values raises ValueError listing all missing keys.

    Pass 3 — <!--slot:...--> prose markers are left untouched (LLM territory).

    Args:
        skeleton: HTML string (the proposal skeleton or a fragment thereof).
        slot_values: Mapping of slot key → string value. Values should already be
            formatted as display strings (e.g. "88.0", "0.1.0").

    Returns:
        The skeleton with all deterministic slots filled.

    Raises:
        ValueError: If any ``{{...}}`` placeholder other than the two handled ones
            remains after pass 1, or if any ``data-slot="KEY"`` element's key has no
            entry in slot_values.
    """
    result = skeleton

    # ── Pass 1: scalar {{key}} replacements ──────────────────────────────────
    for scalar_key in ("version", "design_system_css"):
        if scalar_key in slot_values:
            result = result.replace(f"{{{{{scalar_key}}}}}", slot_values[scalar_key])

    # Check for any leftover {{...}} placeholders (not prose <!--slot:--> comments)
    leftover = _DOUBLE_BRACE_RE.findall(result)
    if leftover:
        raise ValueError(
            f"fill_slots: unhandled {{{{...}}}} placeholder(s) remain after "
            f"scalar substitution: {leftover!r}. "
            "Add them to slot_values or handle them explicitly."
        )

    # ── Pass 2: data-slot="KEY" numeric/text replacement ─────────────────────
    missing_keys: list[str] = []
    filled_keys: list[str] = []

    def _replace_slot(m: re.Match) -> str:
        key = m.group(1)
        whitespace = m.group(2)  # preserve any whitespace between attr and >
        if key in slot_values:
            filled_keys.append(key)
            return f'data-slot="{key}"{whitespace}>{slot_values[key]}<'
        else:
            missing_keys.append(key)
            return m.group(0)  # leave unchanged; we'll raise after the full scan

    result = _DATA_SLOT_RE.sub(_replace_slot, result)

    if missing_keys:
        raise ValueError(
            f"fill_slots: data-slot element(s) with no value in slot_values: "
            f"{missing_keys!r}. Provide all numeric slot values."
        )

    # Pass 3: prose <!--slot:--> markers intentionally left for LLM (Task 3.5).
    return result

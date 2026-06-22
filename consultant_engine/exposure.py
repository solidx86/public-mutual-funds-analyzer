"""
consultant_engine/exposure.py — Task I-new-1

Deterministic, Python-owned Portfolio Exposure look-through (proposal Section 6).

The determinism thesis: Python owns every number; the LLM only writes prose.
This module computes the two exposure pies — asset-class and geographic — from
each holding's underlying ``assets`` and ``geo`` allocations (carried on the
fund dicts that ``load_funds`` builds), then renders the conic-gradient pies and
the geographic legend. No LLM involvement.

Algorithm recovered from the retired fund-consultant skill (Step 7b/7c).
"""

from __future__ import annotations

# ── Asset-class slices (legend order matches the skeleton's fixed swatches) ───
# Each entry: (data-slot key, [source asset keys], pie color).
_ASSET_SLICES: list[tuple[str, list[str], str]] = [
    ("exposure.asset.domestic_equity_pct", ["dom_equity"], "var(--equity)"),
    ("exposure.asset.foreign_equity_pct", ["for_equity"], "var(--teal)"),
    ("exposure.asset.fixed_income_pct", ["fi"], "var(--fixed-income)"),
    ("exposure.asset.money_market_pct", ["mm", "deposits"], "var(--money-market)"),
    ("exposure.asset.gold_pct", ["other"], "var(--gold)"),
]

# Legend labels per asset slot (mirror the skeleton's fixed swatch labels).
_ASSET_LABELS: dict[str, str] = {
    "exposure.asset.domestic_equity_pct": "Equity (Domestic)",
    "exposure.asset.foreign_equity_pct": "Equity (Foreign)",
    "exposure.asset.fixed_income_pct": "Fixed Income / Sukuk",
    "exposure.asset.money_market_pct": "Money Market &amp; Cash",
    "exposure.asset.gold_pct": "Gold / Other",
}

# Structural roles (set on each Holding by build_portfolio) override the workbook
# asset breakdown: a structural gold/MM sleeve's exposure IS gold / money market,
# so its full weighted allocation lands on a single slice rather than being split
# by its for_equity/mm cells. Maps role → target asset slot key.
_STRUCTURAL_ROLE_SLOT: dict[str, str] = {
    "structural:gold": "exposure.asset.gold_pct",
    "structural:money_market": "exposure.asset.money_market_pct",
}

# The neutral fallback slice (used when a pie's group total is 0).
_NEUTRAL_COLOR = "#a0aec0"

# ── Geographic columns + colors ───────────────────────────────────────────────
# Canonical foreign-geo column order load_funds reads back (cols 41-52).
# load_funds keys each fund's ``geo`` dict by the workbook's LITERAL header
# strings, which carry a " (%)" suffix (e.g. "USA (%)"). We strip that suffix on
# read (see _geo_value) so these BARE names match.
_GEO_COLUMNS: list[str] = [
    "USA", "Taiwan", "Korea", "Japan", "France", "Germany",
    "China", "Singapore", "Netherlands", "Indonesia", "Australia", "Geo Other",
]

# Hardcoded hex colors (NOT CSS vars) for the geographic pie/legend.
_GEO_COLORS: dict[str, str] = {
    "Malaysia": "#1a365d",
    "USA": "#c53030",
    "China": "#c05621",
    "Taiwan": "#2c7a7b",
    "Japan": "#b83280",
    "Korea": "#6b46c1",
    "Singapore": "#b7791f",
    "France": "#4a5568",
    "Germany": "#2d3748",
    "Netherlands": "#319795",
    "Indonesia": "#744210",
    "Australia": "#276749",
    "Other": _NEUTRAL_COLOR,
}

# Countries below this weighted percentage are merged into "Other".
_MERGE_THRESHOLD = 2.0


# ── Shared helpers ────────────────────────────────────────────────────────────

def _holding_weights(portfolio: list[dict], funds_by_abbr: dict[str, dict]):
    """Yield ``(weight, fund)`` pairs; weight is allocation_pct / 100."""
    for holding in portfolio:
        weight = holding.get("allocation_pct", 0.0) / 100.0
        fund = funds_by_abbr.get(holding.get("abbr"), {})
        yield weight, fund


def _num(value) -> float:
    """Coerce a possibly-None allocation cell to a float (None → 0.0)."""
    return float(value) if value is not None else 0.0


def _geo_value(geo: dict, column: str) -> float:
    """Read a bare-named geo column out of a fund's ``geo`` dict.

    load_funds keys ``geo`` by the workbook's literal headers ("USA (%)", …),
    so we accept either the suffixed key or the bare name. The suffix is stripped
    on read for robustness; an absent column reads 0.0.
    """
    if column in geo:
        return _num(geo[column])
    return _num(geo.get(f"{column} (%)"))


def _normalize_to_100(values: list[float]) -> list[float]:
    """Scale ``values`` so they sum to exactly 100.0 (1-dp display), nudging the
    largest slice to absorb the rounding residual. An all-zero input returns
    all zeros (caller decides the neutral fallback)."""
    total = sum(values)
    if total <= 0:
        return [0.0 for _ in values]
    scaled = [round(v / total * 100.0, 1) for v in values]
    residual = round(100.0 - sum(scaled), 1)
    if residual != 0.0 and scaled:
        largest_idx = max(range(len(scaled)), key=lambda i: scaled[i])
        scaled[largest_idx] = round(scaled[largest_idx] + residual, 1)
    return scaled


# ── Asset-class exposure ──────────────────────────────────────────────────────

def compute_asset_exposure(
    portfolio: list[dict], funds_by_abbr: dict[str, dict]
) -> dict[str, float]:
    """Weighted asset-class look-through, normalized to sum to 100.0.

    Returns a dict keyed by the 5 ``exposure.asset.*_pct`` data-slot keys.
    Structural sleeves bypass the workbook breakdown: a ``structural:gold``
    holding contributes its full weighted allocation to Gold and a
    ``structural:money_market`` holding contributes its full weighted allocation
    to Money Market (the sleeve's exposure IS that asset class, so the fund's own
    for_equity/mm cells are not split out). Every other holding uses its workbook
    asset breakdown. If the portfolio holds no asset data at all, the "Gold /
    Other" slice absorbs a neutral 100% so the legend still sums to 100.
    """
    by_slot: dict[str, float] = {slot_key: 0.0 for slot_key, _k, _c in _ASSET_SLICES}
    for holding in portfolio:
        weight = holding.get("allocation_pct", 0.0) / 100.0
        target_slot = _STRUCTURAL_ROLE_SLOT.get(holding.get("role", ""))
        if target_slot is not None:
            # Structural sleeve: full weight to its single asset slice.
            by_slot[target_slot] += weight * 100.0
            continue
        fund = funds_by_abbr.get(holding.get("abbr"), {})
        assets = fund.get("assets") or {}
        for slot_key, asset_keys, _color in _ASSET_SLICES:
            by_slot[slot_key] += weight * sum(_num(assets.get(k)) for k in asset_keys)

    raw = [by_slot[slot_key] for slot_key, _k, _c in _ASSET_SLICES]

    if sum(raw) <= 0:
        # Neutral fallback: 100% on the last slice ("Gold / Other").
        normalized = [0.0] * (len(_ASSET_SLICES) - 1) + [100.0]
    else:
        normalized = _normalize_to_100(raw)

    return {
        slot_key: pct
        for (slot_key, _keys, _color), pct in zip(_ASSET_SLICES, normalized)
    }


def asset_pie_slices(
    portfolio: list[dict], funds_by_abbr: dict[str, dict]
) -> list[tuple[str, float]]:
    """``(color, pct)`` pairs for the asset-class pie, in legend order.

    Reads from ``compute_asset_exposure`` (the single source of truth), which
    already routes the zero-data case to a 100% "Gold / Other" neutral slice.
    """
    by_slot = compute_asset_exposure(portfolio, funds_by_abbr)
    return [
        (color, by_slot[slot_key])
        for (slot_key, _keys, color) in _ASSET_SLICES
    ]


# ── Geographic exposure ───────────────────────────────────────────────────────

def compute_geo_exposure(
    portfolio: list[dict], funds_by_abbr: dict[str, dict]
) -> list[tuple[str, float, str]]:
    """Weighted geographic look-through → surviving ``(label, pct, hex)`` slices.

    Malaysia uses the domestic-equity proxy and is always kept. Foreign
    countries below 2% are merged into "Other" (combined with the "Geo Other"
    bucket). Output is normalized to sum to 100.0 and ordered Malaysia-first,
    surviving foreign countries by descending %, "Other" last.
    """
    # Weighted raw exposures.
    malaysia = 0.0
    foreign: dict[str, float] = {c: 0.0 for c in _GEO_COLUMNS}
    for weight, fund in _holding_weights(portfolio, funds_by_abbr):
        assets = fund.get("assets") or {}
        malaysia += weight * _num(assets.get("dom_equity"))
        geo = fund.get("geo") or {}
        for col in _GEO_COLUMNS:
            foreign[col] += weight * _geo_value(geo, col)

    # Merge: "Geo Other" plus every foreign country below the threshold.
    other = foreign.pop("Geo Other", 0.0)
    survivors: dict[str, float] = {}
    for country, value in foreign.items():
        if value < _MERGE_THRESHOLD:
            other += value
        else:
            survivors[country] = value

    # Assemble label/value list: Malaysia, surviving foreign (desc), Other.
    labels = ["Malaysia"]
    raw = [malaysia]
    for country, value in sorted(survivors.items(), key=lambda kv: kv[1], reverse=True):
        labels.append(country)
        raw.append(value)
    labels.append("Other")
    raw.append(other)

    if sum(raw) <= 0:
        return [("Other", 100.0, _GEO_COLORS["Other"])]

    normalized = _normalize_to_100(raw)
    return [
        (label, pct, _GEO_COLORS.get(label, _NEUTRAL_COLOR))
        for label, pct in zip(labels, normalized)
    ]


def geo_pie_pairs(
    slices: list[tuple[str, float, str]]
) -> list[tuple[str, float]]:
    """``(color, pct)`` pairs for the geographic pie, derived from already-computed
    ``(label, pct, hex)`` slices (avoids recomputing the look-through)."""
    return [(hex_, pct) for _label, pct, hex_ in slices]


# ── Renderers ─────────────────────────────────────────────────────────────────

def render_pie(slices: list[tuple[str, float]]) -> str:
    """Render a ``.pie-chart`` div with a cumulative conic-gradient.

    ``slices`` is a list of ``(color, pct)`` pairs. Zero-width slices are
    skipped. The final stop closes at ``100%`` to absorb any 1-dp rounding gap.
    """
    stops: list[str] = []
    cursor = 0.0
    nonzero = [(c, p) for c, p in slices if p > 0]
    for i, (color, pct) in enumerate(nonzero):
        start = cursor
        cursor = round(cursor + pct, 1)
        end = "100%" if i == len(nonzero) - 1 else f"{cursor}%"
        stops.append(f"  {color} {start}% {end}")
    if not stops:
        stops.append(f"  {_NEUTRAL_COLOR} 0.0% 100%")
    gradient = ",\n".join(stops)
    return (
        '<div class="pie-chart" style="background: conic-gradient(\n'
        f"{gradient}\n"
        ');"></div>'
    )


def render_geo_legend(slices: list[tuple[str, float, str]]) -> str:
    """Render the geographic legend items from ``(label, pct, hex)`` slices.

    Truly-0% rows (no allocation) are omitted; the surviving rows still carry the
    determinism-owned percentages and sum to ~100.
    """
    items = []
    for label, pct, hex_ in slices:
        if pct <= 0:
            continue
        items.append(
            '<div class="legend-item">'
            f'<span class="legend-swatch" style="background:{hex_};"></span>'
            f'<span class="legend-label">{label}</span>'
            f'<span class="legend-pct">{pct}%</span>'
            "</div>"
        )
    return "\n".join(items)


def render_asset_legend(
    portfolio: list[dict], funds_by_abbr: dict[str, dict]
) -> str:
    """Render the asset-class legend items in fixed swatch order.

    Reads from ``compute_asset_exposure`` (the single source of truth). Truly-0%
    rows (no allocation) are omitted; the surviving rows carry the
    determinism-owned percentages and sum to ~100.
    """
    by_slot = compute_asset_exposure(portfolio, funds_by_abbr)
    items = []
    for slot_key, _keys, color in _ASSET_SLICES:
        pct = by_slot[slot_key]
        if pct <= 0:
            continue
        items.append(
            '<div class="legend-item">'
            f'<span class="legend-swatch" style="background:{color};"></span>'
            f'<span class="legend-label">{_ASSET_LABELS[slot_key]}</span>'
            f'<span class="legend-pct">{pct}%</span>'
            "</div>"
        )
    return "\n".join(items)

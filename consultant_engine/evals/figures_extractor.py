"""Pure ``ConsultantState -> figures dict`` reshaper — the prose-number eval's
ground-truth surface (Track A, Phase 1; see docs/superpowers/specs/
2026-07-06-track-a-prose-number-eval-design.md §9).

**Reuse, do not re-verify.** This module reuses figures the engine has already
computed and placed on ``ConsultantState`` (``cfs_scores``, ``portfolio``,
``eligible_funds``) as trusted ground truth for the prose-number judge. It does
**not** recompute or re-verify any of those numbers against the FundMaster
workbook — that independent check is owned entirely by
``tests/test_proposal_validation.py``. Re-deriving figures here would make the
eval circular (checking prose against numbers this module itself invented);
instead the state is the single source of truth, verified elsewhere.

The one exception is ``derived_class`` (the CFS asset-class bucket): when a
holding is missing from ``cfs_scores`` (e.g. a structural sleeve that never
entered CFS scoring), this module falls back to calling the same pure,
deterministic ``consultant_engine.cfs.derived_class`` classifier the engine
itself uses. That is a stateless categorical classification, not a re-check of
a verified performance number, so it does not violate the reuse-not-re-verify
rule.

**Portfolio- and per-derived-class aggregates are pre-computed on purpose**
(spec §4a): weighted-average alpha, weighted CFS, per-derived-class averages,
asset-class/geo exposure totals, and the benchmark-beat count/share are
exactly the derivations a consultant states in prose. Emitting them here means
the later LLM judge checks a prose number for *membership* against a ready
value instead of doing the arithmetic itself — arithmetic is the least
reliable thing to delegate to an LLM.

Note: the ``"by_derived_class"`` grouping below buckets holdings by CFS
``derived_class`` (Equity-equivalent / Balanced / Defensive). This is a
different dimension from ``consultant_engine.portfolio``'s role-based
"sleeves" (``structural:gold``, ``structural:money_market``, etc.) — the two
groupings partition the portfolio along unrelated axes, so this module
deliberately avoids the word "sleeve" for its own grouping to keep the two
concepts from being conflated.

This module is engine-coupled Python and lives inside the ``consultant_engine``
package for frictionless imports. The language-agnostic eval harness (fixtures,
judge prompt, Promptfoo config) lives separately under the repo-root
``evals/prose_numbers/`` directory; the two are joined only by the frozen
fixture JSON that ``figures`` blocks get frozen into, never by a Python import.
"""

from __future__ import annotations

from typing import Any

from consultant_engine import exposure as _exposure
from consultant_engine.cfs import derived_class as _derived_class
from consultant_engine.state import ConsultantState

# Asset-class exposure key beating benchmark is defined the same way the
# screener qualifies a fund (see CLAUDE.md: "weighted alpha > 0%, not a binary
# beat-rate") — a fund "beats its benchmark" here iff its own already-verified
# weighted_alpha is positive.


def _funds_by_abbr(eligible_funds: list) -> dict[str, dict]:
    """Index eligible_funds by abbr; skips any record without one."""
    return {f["abbr"]: f for f in eligible_funds if f.get("abbr")}


def _cfs_by_abbr(cfs_scores: list) -> dict[str, dict]:
    """Index cfs_scores by abbr; skips any record without one."""
    return {c["abbr"]: c for c in cfs_scores if c.get("abbr")}


def _rank_by_abbr(cfs_scores: list) -> dict[str, int]:
    """1-indexed rank = position in the already-sorted cfs_scores list.

    cfs_scores arrives pre-sorted descending by composite (score_all's
    contract) — this reads that order off, it never re-sorts or recomputes it.
    """
    return {c["abbr"]: i + 1 for i, c in enumerate(cfs_scores) if c.get("abbr")}


def _num(value) -> float:
    """Coerce a possibly-None figure to a float for arithmetic (None -> 0.0)."""
    return value if value is not None else 0.0


def extract_figures(state: ConsultantState) -> dict[str, Any]:
    """Reshape an already-computed ``ConsultantState`` into the flat figures dict.

    Pure: performs no I/O and does not mutate ``state`` (every nested dict/list
    read out of it is copied, not aliased, into the returned structure).

    Args:
        state: A ``ConsultantState`` with at least ``portfolio``, ``cfs_scores``,
            and ``eligible_funds`` already populated by the engine's nodes.

    Returns:
        A dict with three top-level groups:

        - ``"funds"``: ``{abbr: {...}}`` for every holding in ``state["portfolio"]``,
          with ``cfs`` (composite score or None), ``rank`` (1-indexed position in
          cfs_scores, or None), ``weighted_alpha`` (the fund's own already-verified
          screener figure), ``allocation_pct``, ``role``, ``derived_class``, and
          ``exposure_pct`` (that fund's raw ``assets``/``geo`` breakdown, as-is).
        - ``"portfolio"``: allocation-weighted aggregates across every holding —
          ``n_holdings``, ``weighted_alpha``, ``weighted_cfs``,
          ``benchmark_beat_count``, ``benchmark_beat_share_pct``, plus the
          deterministic asset-class/geo exposure look-through
          (``asset_exposure_pct``, ``geo_exposure_pct`` — computed via
          ``consultant_engine.exposure``, the same module that renders the real
          proposal's exposure pies, so these numbers match what a proposal
          actually shows).
        - ``"by_derived_class"``: the same weighted-average alpha/CFS aggregates
          as ``"portfolio"``, but grouped by ``derived_class`` (Equity-equivalent /
          Balanced / Defensive) and renormalized within each group. (Not to be
          confused with ``consultant_engine.portfolio``'s role-based "sleeves".)
    """
    portfolio: list = state.get("portfolio") or []
    eligible_funds: list = state.get("eligible_funds") or []
    cfs_scores: list = state.get("cfs_scores") or []

    funds_by_abbr = _funds_by_abbr(eligible_funds)
    cfs_by_abbr = _cfs_by_abbr(cfs_scores)
    rank_by_abbr = _rank_by_abbr(cfs_scores)

    funds_out: dict[str, dict] = {}

    # Running numerators/denominators for the portfolio- and
    # per-derived-class-level weighted averages. Weights are allocation
    # fractions (allocation_pct/100), matching the pattern already used by
    # generate_proposal._compute_portfolio_metrics.
    weighted_alpha_num = 0.0
    weighted_cfs_num = 0.0
    beat_count = 0

    class_alloc: dict[str, float] = {}
    class_alpha_num: dict[str, float] = {}
    class_cfs_num: dict[str, float] = {}
    class_count: dict[str, int] = {}

    for holding in portfolio:
        abbr = holding.get("abbr")
        allocation_pct = holding.get("allocation_pct", 0.0)
        alloc = allocation_pct / 100.0

        fund = funds_by_abbr.get(abbr, {})
        cfs_entry = cfs_by_abbr.get(abbr)
        cfs_composite = cfs_entry.get("composite") if cfs_entry else None
        rank = rank_by_abbr.get(abbr)
        # This is the screener's blended weighted_alpha (col-14, the YTD/1Y/3Y/
        # 5Y/10Y weighted figure) — distinct from generate_proposal.py's 3Y-only
        # weighted_alpha_3y, which is what the real HTML's portfolio.weighted_alpha
        # slot renders (see generate_proposal.py, rules/validation.py). Both are
        # legitimately named "weighted_alpha"; this module intentionally exposes
        # the screener's blended figure as ground truth for the prose-number eval.
        weighted_alpha = fund.get("weighted_alpha")

        dclass = cfs_entry.get("derived_class") if cfs_entry else None
        if dclass is None and fund.get("assets"):
            # Fallback for a holding absent from cfs_scores (e.g. a structural
            # sleeve that never entered CFS ranking) — a pure classification,
            # not a re-verification of a performance figure (see module docstring).
            dclass = _derived_class(fund)

        funds_out[abbr] = {
            "cfs": cfs_composite,
            "rank": rank,
            "weighted_alpha": weighted_alpha,
            "allocation_pct": allocation_pct,
            "role": holding.get("role"),
            "derived_class": dclass,
            "exposure_pct": {
                "assets": dict(fund.get("assets") or {}),
                "geo": dict(fund.get("geo") or {}),
            },
        }

        weighted_alpha_num += _num(weighted_alpha) * alloc
        weighted_cfs_num += _num(cfs_composite) * alloc
        if _num(weighted_alpha) > 0:
            beat_count += 1

        if dclass is not None:
            class_alloc[dclass] = class_alloc.get(dclass, 0.0) + alloc
            class_alpha_num[dclass] = class_alpha_num.get(dclass, 0.0) + _num(weighted_alpha) * alloc
            class_cfs_num[dclass] = class_cfs_num.get(dclass, 0.0) + _num(cfs_composite) * alloc
            class_count[dclass] = class_count.get(dclass, 0) + 1

    n_holdings = len(portfolio)

    by_derived_class_out: dict[str, dict] = {}
    for dclass, alloc_total in class_alloc.items():
        by_derived_class_out[dclass] = {
            "n": class_count[dclass],
            "weighted_alpha": round(class_alpha_num[dclass] / alloc_total, 4) if alloc_total else 0.0,
            "weighted_cfs": round(class_cfs_num[dclass] / alloc_total, 4) if alloc_total else 0.0,
        }

    # Exposure look-through reuses consultant_engine.exposure's own deterministic
    # compute — the exact functions that render the real proposal's exposure
    # pies — rather than re-implementing the asset/geo aggregation here.
    asset_exposure_pct = dict(_exposure.compute_asset_exposure(portfolio, funds_by_abbr))
    geo_slices = _exposure.compute_geo_exposure(portfolio, funds_by_abbr)
    geo_exposure_pct = {label: pct for label, pct, _hex in geo_slices}

    return {
        "funds": funds_out,
        "portfolio": {
            "n_holdings": n_holdings,
            "weighted_alpha": round(weighted_alpha_num, 4),
            "weighted_cfs": round(weighted_cfs_num, 4),
            "benchmark_beat_count": beat_count,
            "benchmark_beat_share_pct": round(100.0 * beat_count / n_holdings, 2) if n_holdings else 0.0,
            "asset_exposure_pct": asset_exposure_pct,
            "geo_exposure_pct": geo_exposure_pct,
        },
        "by_derived_class": by_derived_class_out,
    }

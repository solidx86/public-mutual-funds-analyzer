"""Shared validation rules for generated fund proposals.

Pure functions that return ``list[dict]`` of ``{"code": str, "msg": str}``.
Empty list means clean — no violations.

Both consumers import from here:
  * runtime ``validate`` node in the consultant engine graph
  * offline pytest suite (tests/consultant_engine/test_validation_rules.py and
    the legacy tests/test_proposal_validation.py, unchanged)
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any

import openpyxl

# ── Shared constants ─────────────────────────────────────────────────────────

LOCKED_SECTIONS: list[str] = [
    "Executive Summary",
    "Global &amp; Local Macro Context",
    "Client Risk Profile",
    "Fund Recommendations",
    "Portfolio Summary",
    "Portfolio Exposure",
    "Investment Strategy",
    "Fee Disclosure",
    "Disclaimer, Sources &amp; References",
]

WHOLESALE_ABBRS: frozenset[str] = frozenset({"PBCPF", "PWSIF", "PIWSIF", "PeWS20F"})

_DISCLOSURE_H4S: list[str] = [
    "AI-Generated Document",
    "Regulatory Disclaimer",
    "Cooling-Off Right",
    "Conflict of Interest",
]

# ── Shared helpers ────────────────────────────────────────────────────────────


def fund_cards(text: str) -> list[tuple[str, str]]:
    """Split the Fund Recommendations section into per-fund card chunks.

    Returns a list of ``(abbr, chunk_html)`` tuples.
    """
    chunks = re.split(r'<div class="fund-card">', text)[1:]
    cards: list[tuple[str, str]] = []
    for chunk in chunks:
        m = re.search(r"<h3>([^<]+)</h3>", chunk)
        if not m:
            continue
        title = _html.unescape(m.group(1))
        # "Name · ABBR" with an optional " — role" suffix after the abbreviation
        abbr = title.rsplit("·", 1)[1].split("—")[0].strip()
        cards.append((abbr, chunk))
    return cards


def workbook_index(workbook_path: str | Path) -> dict[str, dict[str, Any]]:
    """Load a FundMaster workbook and return an abbr-keyed index.

    Each entry: ``{"name": str, "status": str}``.
    The ``status`` column (col 10) holds "Qualified" | "Disqualified".
    """
    ws = openpyxl.load_workbook(str(workbook_path))["Master"]
    funds: dict[str, dict[str, Any]] = {}
    for r in range(4, ws.max_row + 1):
        abbr = ws.cell(r, 2).value
        if abbr:
            funds[abbr] = {
                "name": ws.cell(r, 1).value,
                "status": ws.cell(r, 10).value,
            }
    return funds


# ── Individual rule functions ─────────────────────────────────────────────────


def check_sections(html_text: str) -> list[dict[str, str]]:
    """Verify the 9 locked section titles are present, in order, and that
    there are exactly 9 ``.section`` divs.

    Violation codes:
      ``section_count``  — wrong number of .section divs
      ``section_order``  — section title out of order / missing / extra
    """
    violations: list[dict[str, str]] = []

    # Count <div class="section"> occurrences
    section_div_count = len(re.findall(r'<div class="section">', html_text))
    if section_div_count != 9:
        violations.append({
            "code": "section_count",
            "msg": (
                f"Expected 9 .section divs, found {section_div_count}"
            ),
        })

    # Extract ordered section titles
    titles = re.findall(r'<div class="section-title">([^<]+)</div>', html_text)
    if titles != LOCKED_SECTIONS:
        # Determine specific drift
        if set(titles) == set(LOCKED_SECTIONS) and titles != LOCKED_SECTIONS:
            violations.append({
                "code": "section_order",
                "msg": f"Sections present but out of order: {titles}",
            })
        else:
            # Could be missing, extra, or both — still report as section_order
            violations.append({
                "code": "section_order",
                "msg": f"Section skeleton drifted: {titles}",
            })

    return violations


def check_version_and_disclosure(html_text: str, version: str) -> list[dict[str, str]]:
    """Verify version stamp and the 4 mandatory disclosure headings.

    Violation codes:
      ``skill_version_literal``  — unresolved ``[SKILL_VERSION]`` placeholder
      ``version_mismatch``       — cover footer version doesn't match ``version``
      ``disclosure_heading``     — one or more of the 4 required h4s missing/out of order
    """
    violations: list[dict[str, str]] = []

    if "[SKILL_VERSION]" in html_text:
        violations.append({
            "code": "skill_version_literal",
            "msg": "Unresolved [SKILL_VERSION] literal found in proposal",
        })

    if f"fund-consultant v{version}" not in html_text:
        # Find what version is actually stamped
        m = re.search(r"fund-consultant v([\d.]+)", html_text)
        found = m.group(1) if m else "<none>"
        violations.append({
            "code": "version_mismatch",
            "msg": (
                f"Expected 'fund-consultant v{version}' in cover footer, "
                f"found 'fund-consultant v{found}'"
            ),
        })

    # Check all 4 disclosure headings present in order (within the disclaimer section)
    h4_headings = re.findall(r"<h4>([^<]+)</h4>", html_text)
    # Look for all 4 in order within h4_headings
    found_order: list[str] = []
    h4_iter = iter(h4_headings)
    for required in _DISCLOSURE_H4S:
        for heading in h4_iter:
            if heading.strip() == required:
                found_order.append(heading.strip())
                break
    if found_order != _DISCLOSURE_H4S:
        missing = [h for h in _DISCLOSURE_H4S if h not in found_order]
        violations.append({
            "code": "disclosure_heading",
            "msg": f"Disclosure headings missing or out of order: {missing}",
        })

    return violations


def check_cfs_consistency(html_text: str) -> list[dict[str, str]]:
    """Recompute each fund card's CFS composite from its displayed dimension
    scores + weights and compare to the displayed composite.

    Mismatch tolerance: ±1.0 (matches the existing test).

    Violation code: ``cfs_recompute``
    """
    violations: list[dict[str, str]] = []

    bars = re.split(r'<div class="cfs-bar">', html_text)[1:]
    for bar in bars:
        bar_trimmed = bar.split('<div class="cfs-bar-note"')[0]
        score_m = re.search(r'class="cfs-score">([\d.]+)</span>', bar_trimmed)
        if score_m is None:
            # Passive/structural holding — "n/a" or "—" is acceptable
            continue
        composite = float(score_m.group(1))
        rows = re.findall(
            r"(\d+(?:\.\d+)?) / 100\*? &middot; (\d+(?:\.\d+)?)% weight",
            bar_trimmed,
        )
        if len(rows) != 4:
            continue  # structural bar without all 4 dimensions — skip
        scores = [float(s) for s, _ in rows]
        weights = [float(w) for _, w in rows]
        recomputed = sum(s * w / 100 for s, w in zip(scores, weights))
        if abs(composite - recomputed) > 1.0:
            violations.append({
                "code": "cfs_recompute",
                "msg": (
                    f"CFS composite {composite} != recomputed {recomputed:.2f} "
                    f"(diff {abs(composite - recomputed):.2f})"
                ),
            })

    return violations


def check_perf_consistency(html_text: str) -> list[dict[str, str]]:
    """For each performance-table row, verify displayed Alpha == Fund - Bench
    (the MFR 'value add' relation). Rows with any missing cell ("&mdash;"/"—")
    are skipped. Tolerance: ±0.1.

    Violation code: ``perf_recompute``
    """
    violations: list[dict[str, str]] = []
    tables = re.findall(r'<table class="perf-table">.*?</table>', html_text, re.DOTALL)
    for table in tables:
        for row in re.findall(r"<tr>(.*?)</tr>", table, re.DOTALL):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(cells) != 4:
                continue

            def _num(cell: str):
                txt = _html.unescape(re.sub(r"<[^>]+>", "", cell)).strip().replace("+", "")
                if txt in ("—", "-", "", "n/a", "N/A"):
                    return None
                try:
                    return float(txt)
                except ValueError:
                    return None

            period = _html.unescape(re.sub(r"<[^>]+>", "", cells[0])).strip()
            fund, bench, alpha = _num(cells[1]), _num(cells[2]), _num(cells[3])
            if None in (fund, bench, alpha):
                continue
            if abs(alpha - (fund - bench)) > 0.1:
                violations.append({
                    "code": "perf_recompute",
                    "msg": (
                        f"{period}: displayed alpha {alpha} != fund-bench "
                        f"{fund - bench:.2f} (diff {abs(alpha - (fund - bench)):.2f})"
                    ),
                })
    return violations


def check_exposure_consistency(html_text: str) -> list[dict[str, str]]:
    """Within the Portfolio Exposure section, verify each ``.exposure-chart-block``
    legend's ``legend-pct`` values sum to 100.0 (a pie is parts-of-a-whole).

    Scoped to the exposure section so it never picks up unrelated ``legend-pct``
    spans elsewhere in the document. Tolerance: ±2.0.

    Violation code: ``exposure_sum``
    """
    violations: list[dict[str, str]] = []

    # Isolate the Portfolio Exposure section (up to the next section or EOF).
    sect_m = re.search(
        r'Portfolio Exposure</div>(.*?)(?=<div class="section">|</body>)',
        html_text,
        re.DOTALL,
    )
    if sect_m is None:
        return violations  # section absent — check_sections owns that failure
    section = sect_m.group(1)

    blocks = re.findall(
        r'<div class="exposure-chart-block">(.*?)(?=<div class="exposure-chart-block">|$)',
        section,
        re.DOTALL,
    )
    for block in blocks:
        title_m = re.search(r'exposure-chart-title">([^<]+)<', block)
        title = title_m.group(1).strip() if title_m else "?"
        total = 0.0
        found = False
        for raw in re.findall(r'class="legend-pct"[^>]*>([^<]*)<', block):
            txt = _html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
            txt = txt.replace("%", "").replace("+", "")
            try:
                total += float(txt)
                found = True
            except ValueError:
                continue
        if not found:
            continue  # no numeric legend in this block — nothing to check
        if abs(total - 100.0) > 2.0:
            violations.append({
                "code": "exposure_sum",
                "msg": (
                    f"{title} exposure legend sums to {total:.1f} "
                    f"(expected 100.0 ± 2.0)"
                ),
            })
    return violations


def check_summary_consistency(html_text: str) -> list[dict[str, str]]:
    """Cross-check each Portfolio Summary row's CFS against the same fund's
    fund-card composite.

    Both numbers are Python-rendered from the same ``cfs_scores``, so a mismatch
    means the summary table was corrupted downstream (defense-in-depth for the
    Python-owned summary numbers, mirroring the CFS/perf/exposure guards).
    Structural rows (no card composite) and ``—`` cells are skipped.
    Tolerance: ±1.0.

    Violation code: ``summary_mismatch``
    """
    violations: list[dict[str, str]] = []

    # Composite per fund from the fund cards (the cfs-score span).
    card_cfs: dict[str, float] = {}
    for abbr, chunk in fund_cards(html_text):
        m = re.search(r'class="cfs-score">([\d.]+)</span>', chunk)
        if m:
            card_cfs[abbr] = float(m.group(1))

    # Isolate the Portfolio Summary section (up to the next section or EOF).
    sect_m = re.search(
        r'Portfolio Summary</div>(.*?)(?=<div class="section">|</body>)',
        html_text,
        re.DOTALL,
    )
    if sect_m is None:
        return violations

    for row in re.findall(r"<tr>(.*?)</tr>", sect_m.group(1), re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 4:
            continue
        abbr = _html.unescape(re.sub(r"<[^>]+>", "", cells[0])).strip()
        if abbr not in card_cfs:
            continue  # structural row / fund without a card composite
        cfs_txt = _html.unescape(re.sub(r"<[^>]+>", "", cells[3])).strip()
        try:
            summary_cfs = float(cfs_txt)
        except ValueError:
            continue  # "—" or non-numeric
        if abs(summary_cfs - card_cfs[abbr]) > 1.0:
            violations.append({
                "code": "summary_mismatch",
                "msg": (
                    f"{abbr}: Portfolio Summary CFS {summary_cfs} != "
                    f"fund-card composite {card_cfs[abbr]}"
                ),
            })
    return violations


def check_funds_in_workbook(
    html_text: str,
    wb_index: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Verify every fund card abbreviation exists in the workbook index.

    Violation code: ``fund_not_in_workbook``
    """
    violations: list[dict[str, str]] = []
    for abbr, _ in fund_cards(html_text):
        if abbr not in wb_index:
            violations.append({
                "code": "fund_not_in_workbook",
                "msg": f"Recommended fund '{abbr}' not found in source FundMaster workbook",
            })
    return violations


def check_alpha_warning(
    html_text: str,
    wb_index: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Verify alpha-warning blocks appear exactly when a fund is Disqualified.

    Disclosure rule: a fund card carries an ALPHA WARNING block iff
    the fund's status in the source workbook is "Disqualified".

    Violation code: ``alpha_warning``
    """
    violations: list[dict[str, str]] = []
    for abbr, chunk in fund_cards(html_text):
        if abbr not in wb_index:
            continue  # already caught by check_funds_in_workbook
        has_warning = '<div class="alpha-warning">' in chunk
        disqualified = wb_index[abbr]["status"] == "Disqualified"
        if has_warning != disqualified:
            violations.append({
                "code": "alpha_warning",
                "msg": (
                    f"{abbr}: status={wb_index[abbr]['status']}, "
                    f"alpha-warning present={has_warning}"
                ),
            })
    return violations


def check_retail_eligibility(
    html_text: str,
    wb_index: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Verify no PB-named, -B class, or wholesale funds are recommended.

    Violation code: ``retail_eligibility``
    """
    violations: list[dict[str, str]] = []
    for abbr, _ in fund_cards(html_text):
        if abbr not in wb_index:
            continue  # already caught by check_funds_in_workbook
        name = wb_index[abbr]["name"] or ""
        if name.startswith("PB ") or abbr.endswith("-B") or abbr in WHOLESALE_ABBRS:
            violations.append({
                "code": "retail_eligibility",
                "msg": (
                    f"{abbr} ({name!r}) fails retail eligibility: "
                    "PB-named, -B class, or wholesale fund"
                ),
            })
    return violations


# ── Composite runner ──────────────────────────────────────────────────────────


def validate_html(
    html_text: str,
    version: str,
    wb_index: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Run all validation rules and return the concatenated list of violations.

    Returns ``[]`` for a clean proposal.
    """
    return (
        check_sections(html_text)
        + check_version_and_disclosure(html_text, version)
        + check_cfs_consistency(html_text)
        + check_perf_consistency(html_text)
        + check_exposure_consistency(html_text)
        + check_summary_consistency(html_text)
        + check_funds_in_workbook(html_text, wb_index)
        + check_alpha_warning(html_text, wb_index)
        + check_retail_eligibility(html_text, wb_index)
    )

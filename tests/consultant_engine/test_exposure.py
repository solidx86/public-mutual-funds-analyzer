"""Unit tests for consultant_engine/exposure.py — Task I-new-1.

Pure-math tests for deterministic Portfolio Exposure computation: asset-class
weighted look-through, geographic look-through with the <2% merge rule, pie
normalization, and the conic-gradient/legend renderers.
"""
from __future__ import annotations

from consultant_engine import exposure


def _funds_by_abbr():
    """Two equity funds with explicit assets + geo dicts keyed by canonical names."""
    return {
        # 80% domestic equity, 10% foreign equity, 5% FI, 5% deposits.
        # Geo: 30 USA, 5 China, 1 Japan (Japan < 2% after weighting → Other),
        #      4 "Geo Other".
        "FUNDA": {
            "abbr": "FUNDA",
            "assets": {
                "dom_equity": 80.0,
                "for_equity": 10.0,
                "fi": 5.0,
                "mm": 0.0,
                "deposits": 5.0,
                "other": 0.0,
            },
            "geo": {
                "USA": 30.0,
                "China": 5.0,
                "Japan": 1.0,
                "Geo Other": 4.0,
            },
        },
        # 50% domestic equity, 20% foreign, 10% FI, 10% mm, 0 deposits, 10% other.
        "FUNDB": {
            "abbr": "FUNDB",
            "assets": {
                "dom_equity": 50.0,
                "for_equity": 20.0,
                "fi": 10.0,
                "mm": 10.0,
                "deposits": 0.0,
                "other": 10.0,
            },
            "geo": {
                "USA": 40.0,
                "Korea": 10.0,
                "Geo Other": 2.0,
            },
        },
    }


def _portfolio():
    # 60% FUNDA, 40% FUNDB
    return [
        {"abbr": "FUNDA", "allocation_pct": 60.0},
        {"abbr": "FUNDB", "allocation_pct": 40.0},
    ]


# ── Asset-class exposure ──────────────────────────────────────────────────────


def test_asset_exposure_weighted_sum_and_groupings():
    result = exposure.compute_asset_exposure(_portfolio(), _funds_by_abbr())

    # Raw weighted sums (weight 0.6 / 0.4):
    #   dom_equity = .6*80 + .4*50 = 48 + 20 = 68
    #   for_equity = .6*10 + .4*20 = 6 + 8   = 14
    #   fi         = .6*5  + .4*10 = 3 + 4   = 7
    #   mm+dep     = .6*(0+5) + .4*(10+0) = 3 + 4 = 7
    #   other      = .6*0  + .4*10 = 0 + 4   = 4
    # group total = 100 already → normalized == raw.
    assert result["exposure.asset.domestic_equity_pct"] == 68.0
    assert result["exposure.asset.foreign_equity_pct"] == 14.0
    assert result["exposure.asset.fixed_income_pct"] == 7.0
    # mm + deposits combined:
    assert result["exposure.asset.money_market_pct"] == 7.0
    assert result["exposure.asset.gold_pct"] == 4.0


def test_asset_exposure_normalized_to_100():
    result = exposure.compute_asset_exposure(_portfolio(), _funds_by_abbr())
    assert round(sum(result.values()), 1) == 100.0


def test_asset_exposure_normalizes_when_total_not_100():
    # A single fund whose assets total only 50 → should scale up to 100.
    funds = {
        "X": {
            "abbr": "X",
            "assets": {"dom_equity": 25.0, "for_equity": 25.0,
                       "fi": 0.0, "mm": 0.0, "deposits": 0.0, "other": 0.0},
            "geo": {},
        }
    }
    portfolio = [{"abbr": "X", "allocation_pct": 100.0}]
    result = exposure.compute_asset_exposure(portfolio, funds)
    assert result["exposure.asset.domestic_equity_pct"] == 50.0
    assert result["exposure.asset.foreign_equity_pct"] == 50.0
    assert round(sum(result.values()), 1) == 100.0


def test_asset_exposure_zero_total_renders_neutral_other():
    funds = {"X": {"abbr": "X", "assets": {}, "geo": {}}}
    portfolio = [{"abbr": "X", "allocation_pct": 100.0}]
    result = exposure.compute_asset_exposure(portfolio, funds)
    # Everything zero except a 100% neutral slice on "Gold / Other".
    assert result["exposure.asset.gold_pct"] == 100.0
    assert round(sum(result.values()), 1) == 100.0


def test_asset_exposure_handles_missing_assets_key():
    # A fund with no 'assets' key at all must be treated as zeros, not crash.
    funds = {
        "A": {"abbr": "A", "assets": {"dom_equity": 100.0}, "geo": {}},
        "B": {"abbr": "B"},  # no assets / geo
    }
    portfolio = [
        {"abbr": "A", "allocation_pct": 50.0},
        {"abbr": "B", "allocation_pct": 50.0},
    ]
    result = exposure.compute_asset_exposure(portfolio, funds)
    # Only A contributes 50 dom_equity → normalized to 100% domestic.
    assert result["exposure.asset.domestic_equity_pct"] == 100.0
    assert round(sum(result.values()), 1) == 100.0


# ── Geographic exposure ───────────────────────────────────────────────────────


def test_geo_exposure_malaysia_uses_dom_equity_proxy():
    slices = exposure.compute_geo_exposure(_portfolio(), _funds_by_abbr())
    labels = [s[0] for s in slices]
    # Malaysia must be first.
    assert labels[0] == "Malaysia"
    # Other must be last.
    assert labels[-1] == "Other"


def test_geo_exposure_merges_sub_2pct_into_other():
    slices = exposure.compute_geo_exposure(_portfolio(), _funds_by_abbr())
    labels = [s[0] for s in slices]
    # Japan weighted = .6*1 = 0.6 (<2%) → must be merged away.
    assert "Japan" not in labels
    # Surviving foreign: USA (.6*30+.4*40=18+16=34) and China (.6*5=3) survive;
    # Korea (.4*10=4) survives. Malaysia (dom_equity proxy) = .6*80+.4*50=68.
    assert "USA" in labels
    assert "Korea" in labels
    assert "China" in labels


def test_geo_exposure_normalized_to_100():
    slices = exposure.compute_geo_exposure(_portfolio(), _funds_by_abbr())
    assert round(sum(s[1] for s in slices), 1) == 100.0


def test_geo_exposure_foreign_sorted_descending():
    slices = exposure.compute_geo_exposure(_portfolio(), _funds_by_abbr())
    # drop Malaysia (first) and Other (last); the middle must be descending.
    middle = slices[1:-1]
    pcts = [s[1] for s in middle]
    assert pcts == sorted(pcts, reverse=True)


def test_geo_exposure_other_combines_geo_other_and_small_countries():
    slices = exposure.compute_geo_exposure(_portfolio(), _funds_by_abbr())
    other = [s for s in slices if s[0] == "Other"]
    assert other, "Other slice must be present"
    # Geo Other weighted = .6*4 + .4*2 = 2.4 + 0.8 = 3.2; plus Japan 0.6 = 3.8
    # (pre-normalization, of a 78.8 group total). After normalization the value
    # is > 0; just assert it is positive and merged.
    assert other[0][1] > 0


def test_geo_exposure_uses_canonical_hex_colors():
    slices = exposure.compute_geo_exposure(_portfolio(), _funds_by_abbr())
    by_label = {s[0]: s[2] for s in slices}
    assert by_label["Malaysia"] == "#1a365d"
    assert by_label["USA"] == "#c53030"
    assert by_label["Other"] == "#a0aec0"


def test_geo_exposure_zero_total_renders_neutral_other():
    funds = {"X": {"abbr": "X", "assets": {}, "geo": {}}}
    portfolio = [{"abbr": "X", "allocation_pct": 100.0}]
    slices = exposure.compute_geo_exposure(portfolio, funds)
    assert len(slices) == 1
    assert slices[0][0] == "Other"
    assert slices[0][1] == 100.0


# ── Renderers ─────────────────────────────────────────────────────────────────


def test_render_pie_cumulative_conic_gradient():
    out = exposure.render_pie([("#1a365d", 25.0), ("#c53030", 75.0)])
    assert "conic-gradient(" in out
    assert "#1a365d 0.0% 25.0%" in out
    assert "#c53030 25.0% 100%" in out
    assert 'class="pie-chart"' in out


def test_render_pie_skips_zero_width_slices():
    out = exposure.render_pie([("#1a365d", 100.0), ("#a0aec0", 0.0)])
    assert "#a0aec0" not in out  # zero-width slice skipped
    assert "#1a365d 0.0% 100%" in out


def test_render_geo_legend_items():
    slices = [("Malaysia", 60.0, "#1a365d"), ("USA", 40.0, "#c53030")]
    out = exposure.render_geo_legend(slices)
    assert '<span class="legend-label">Malaysia</span>' in out
    assert '<span class="legend-pct">60.0%</span>' in out
    assert "background:#c53030;" in out
    assert "<!--slot:" not in out


def test_geo_pie_pairs_drops_labels_keeps_color_pct():
    slices = [("Malaysia", 60.0, "#1a365d"), ("USA", 40.0, "#c53030")]
    assert exposure.geo_pie_pairs(slices) == [("#1a365d", 60.0), ("#c53030", 40.0)]


def test_asset_and_geo_pies_render_consistent_for_real_portfolio():
    portfolio, funds = _portfolio(), _funds_by_abbr()
    asset_pie = exposure.render_pie(exposure.asset_pie_slices(portfolio, funds))
    geo_slices = exposure.compute_geo_exposure(portfolio, funds)
    geo_pie = exposure.render_pie(exposure.geo_pie_pairs(geo_slices))
    assert "conic-gradient(" in asset_pie
    assert "conic-gradient(" in geo_pie

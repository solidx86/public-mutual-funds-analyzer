def derived_class(fund) -> str:
    """
    Determine derived asset class from asset allocation.

    Equity-equivalent if dom_equity + for_equity >= 60
    Defensive if fi + mm + deposits >= 60
    Otherwise Balanced
    """
    a = fund["assets"]
    eq = a.get("dom_equity", 0) + a.get("for_equity", 0)
    deff = a.get("fi", 0) + a.get("mm", 0) + a.get("deposits", 0)
    if eq >= 60:
        return "Equity-equivalent"
    if deff >= 60:
        return "Defensive"
    return "Balanced"


def percentile_rank(value, population) -> float:
    """
    Calculate percentile rank of a value in a population.

    Top value returns 100, bottom returns 0, ties share the rank.
    """
    pop = sorted(population)
    if len(pop) <= 1:
        return 100.0
    below = sum(1 for x in pop if x < value)
    return round(100 * below / (len(pop) - 1), 1)


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


_ANCHORS = [(0.0, 0), (0.25, 5), (0.5, 20), (0.75, 50), (1.0, 80), (1.5, 100)]


def returnfit_score(ratio: float) -> float:
    if ratio <= 0: return 0.0
    if ratio >= 1.5: return 100.0
    for (x0, y0), (x1, y1) in zip(_ANCHORS, _ANCHORS[1:]):
        if x0 <= ratio <= x1:
            return round(y0 + (y1 - y0) * (ratio - x0) / (x1 - x0), 1)
    return 0.0


def efficiency_raw(fund) -> float:
    """
    Efficiency_raw = 3Y Alpha Efficiency with fallback to 1Y AE, else 0.

    Prefer 3Y AE over 1Y AE. Uses explicit None checks to preserve 0.0 as a valid value.
    """
    ae = fund.get("ae", {})
    v = ae.get("3y")
    if v is None:
        v = ae.get("1y")
    if v is None:
        v = 0.0
    return v

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

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

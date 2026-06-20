import functools


def _num(value) -> float:
    """Coerce a possibly-None allocation/return cell to a float (None → 0.0).

    Explicit None check rather than ``value or 0`` — the ``or`` form also swallows
    a legitimate ``0.0``, which is the exact None-vs-0 trap the plan warns against.
    """
    return value if value is not None else 0.0


def derived_class(fund) -> str:
    """
    Determine derived asset class from asset allocation.

    Equity-equivalent if dom_equity + for_equity >= 60
    Defensive if fi + mm + deposits >= 60
    Otherwise Balanced
    """
    a = fund["assets"]
    eq = _num(a.get("dom_equity")) + _num(a.get("for_equity"))
    deff = _num(a.get("fi")) + _num(a.get("mm")) + _num(a.get("deposits"))
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
        # Explicit None checks: a missing alpha is "no penalty", distinct from a
        # genuine negative alpha. (None and 0.0 both fail `< 0`, so behaviour is
        # unchanged — this just drops the `or 0` None-vs-0 trap.)
        alpha_3y = fund["returns"].get("3y", {}).get("alpha")
        alpha_5y = fund["returns"].get("5y", {}).get("alpha")
        if alpha_3y is not None and alpha_3y < 0: raw /= 2
        if alpha_5y is not None and alpha_5y < 0: raw /= 2
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


def _dd_base(dd):
    for hi, score in [(-5,80),(-10,70),(-15,60),(-25,40),(-40,20)]:
        if dd >= hi: return score
    return 10


def _recovery(days):
    if days is None: return 0
    if days < 30: return 15
    if days <= 90: return 10
    if days <= 180: return 5
    if days <= 365: return 0
    return -10


def momentum_score(drawdown, days) -> float:
    dd = drawdown if drawdown is not None else -50.0
    return max(0.0, min(100.0, _dd_base(dd) + _recovery(days)))


BASE = {
    "Conservative": {"alpha": 28, "returnfit": 40, "efficiency": 25, "momentum": 7},
    "Moderate": {"alpha": 28, "returnfit": 40, "efficiency": 20, "momentum": 12},
    "Moderately Aggressive": {"alpha": 26, "returnfit": 40, "efficiency": 17, "momentum": 17},
    "Aggressive": {"alpha": 30, "returnfit": 40, "efficiency": 13, "momentum": 17},
}
MID = {"Conservative": 3.5, "Moderate": 5.0, "Moderately Aggressive": 7.0, "Aggressive": 9.0}


def profile_weights(profile, e_target) -> dict:
    w = dict(BASE[profile])
    mid = MID[profile]
    stretch = (e_target - mid) / mid
    if stretch > 0:
        shift = min(10.0, 10.0 * stretch)
        w["alpha"] -= shift
        w["returnfit"] += shift
    elif stretch < 0:
        shift = min(5.0, 5.0 * abs(stretch))
        w["returnfit"] -= shift
        w["alpha"] += shift
    w = {k: max(5.0, min(50.0, v)) for k, v in w.items()}
    total = sum(w.values())
    return {k: round(v * 100 / total, 2) for k, v in w.items()}


def score_all(funds: list, profile: str, e_target: float) -> list:
    """
    Compose per-fund CFS dimensions into a final score.

    Steps:
    1. Group funds by derived_class.
    2. Within each class, compute Alpha_N and Efficiency_N as percentile ranks.
    3. ReturnFit_N uses the absolute piecewise curve (returnfit_score), except
       when ALL funds in the class have Wtd_Return < 0 (bear exception), in
       which case ReturnFit_N becomes a percentile rank within the class.
    4. Momentum_N is always absolute (momentum_score), never percentile.
    5. Composite = weighted dot product / 100.
    6. Sort descending: within 2.0 composite gap → tiebreak by alpha_n desc,
       then efficiency_n desc; else by composite desc.
    """
    w = profile_weights(profile, e_target)

    # --- pre-compute raw dimension values per fund ---
    raw = {}
    for fund in funds:
        abbr = fund["abbr"]
        cls = derived_class(fund)
        alpha_raw = raw_alpha_penalised(fund)
        eff_raw = efficiency_raw(fund)
        wtd_ret = weighted_blend(
            {p: fund["returns"].get(p, {}).get("fund") for p in WEIGHTS}
        )
        mom = momentum_score(fund.get("drawdown"), fund.get("days_from_ath"))
        raw[abbr] = {
            "fund": fund,
            "cls": cls,
            "alpha_raw": alpha_raw,
            "eff_raw": eff_raw,
            "wtd_ret": wtd_ret,
            "mom": mom,
        }

    # --- group by derived class ---
    classes: dict[str, list[str]] = {}
    for abbr, r in raw.items():
        classes.setdefault(r["cls"], []).append(abbr)

    # --- compute normalised dimensions per class then build result dicts ---
    scores: list[dict] = []
    for cls, abbrs in classes.items():
        alpha_pop = [raw[a]["alpha_raw"] for a in abbrs]
        eff_pop = [raw[a]["eff_raw"] for a in abbrs]
        wtd_ret_pop = [raw[a]["wtd_ret"] for a in abbrs]

        bear_exception = all(r < 0 for r in wtd_ret_pop)

        for abbr in abbrs:
            r = raw[abbr]
            alpha_n = round(percentile_rank(r["alpha_raw"], alpha_pop), 2)
            eff_n = round(percentile_rank(r["eff_raw"], eff_pop), 2)

            if bear_exception:
                rf_n = round(percentile_rank(r["wtd_ret"], wtd_ret_pop), 2)
            else:
                ratio = r["wtd_ret"] / e_target if e_target else 0.0
                rf_n = round(returnfit_score(ratio), 2)

            mom_n = round(r["mom"], 2)

            composite = round(
                (w["alpha"] * alpha_n
                 + w["returnfit"] * rf_n
                 + w["efficiency"] * eff_n
                 + w["momentum"] * mom_n) / 100,
                2,
            )

            scores.append({
                "abbr": abbr,
                "alpha_n": alpha_n,
                "returnfit_n": rf_n,
                "efficiency_n": eff_n,
                "momentum_n": mom_n,
                "composite": composite,
                "weights": w,
                "derived_class": cls,
            })

    # --- sort: composite desc, with an intentional 2.0-gap tiebreaker band ---
    # Within 2.0 composite points two funds are "close enough" and ranked by
    # alpha_n then efficiency_n; beyond that gap, composite wins. This banding is
    # deliberately NON-transitive (A~B and B~C by gap, yet A vs C by composite),
    # so it is not a total order. Determinism is preserved by Python's stable sort
    # over the fixed input order (FundMaster row order), which never varies for a
    # given workbook. A true total order would mean dropping the spec-mandated
    # 2.0-gap semantics — a scoring change, not a cleanup, so out of scope here.
    def _cmp(a, b):
        if abs(a["composite"] - b["composite"]) <= 2.0:
            if a["alpha_n"] != b["alpha_n"]:
                return -1 if a["alpha_n"] > b["alpha_n"] else 1
            if a["efficiency_n"] != b["efficiency_n"]:
                return -1 if a["efficiency_n"] > b["efficiency_n"] else 1
            return 0
        return -1 if a["composite"] > b["composite"] else 1

    scores.sort(key=functools.cmp_to_key(_cmp))
    return scores

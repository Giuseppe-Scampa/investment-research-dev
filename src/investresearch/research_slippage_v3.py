"""V3 spread/slippage sensitivity, strictly secondary to the frozen primary gate.

The V3 protocol already froze four bps scenarios. Interpret each as adverse
execution bps PER SIDE: buy at entry close*(1+bps/10000), sell at exit
close*(1-bps/10000). Commissions still apply to the executed cash values,
including minimums; USD FX friction is unchanged. This is an illustrative
sensitivity, not bid/ask or verified tradable quotes. No score, selected ID,
historical return path, preregistered primary statistic or gate is modified.
"""
from __future__ import annotations

from math import isfinite
from statistics import mean

BPS_TO_FRACTION = 10000


def net_at_bps(gross, currency, costs, notional, bps):
    """One K-position leg, return net of two adverse price executions.

    For bps=0 the formula is mathematically identical to the frozen
    _net_trade calculation used by V3. No future data are accessed here.
    """
    if (type(bps) is not int or bps not in (0,10,25,50)
            or type(gross) not in (float,int) or not isfinite(gross)
            or gross <= -1 or gross > 100
            or currency not in ("EUR","USD")
            or not isinstance(costs,dict)
            or type(notional) not in (int,float) or not isfinite(notional)
            or notional <= 0):
        raise ValueError("V3 spread sensitivity received invalid non-executable inputs")
    commission=costs["commission_fraction_each_side"]
    minimum=costs["minimum_commission_eur_each_side"]
    fx=costs["usd_fx_fraction_each_side"] if currency=="USD" else 0
    if (type(commission) not in (int,float) or type(minimum) not in (int,float)
            or type(fx) not in (int,float)
            or not all(isfinite(x) for x in (commission,minimum,fx))
            or not 0<=commission<1 or not 0<=fx<1
            or minimum<0 or notional<=minimum):
        raise ValueError("Invalid V3 commission/FX sensitivity assumptions")
    fraction=bps/BPS_TO_FRACTION
    buy_fee=max(notional*commission,minimum)
    available=notional-buy_fee-notional*fx
    if available <= 0:
        raise ValueError("Original K-leg fees exhaust the hypothetical notional")
    # The same number of units pays the adverse entry ask and gets the
    # adverse exit bid; final sale commission and FX are based on proceeds.
    proceeds=available*(1+gross)*(1-fraction)/(1+fraction)
    sell_fee=max(proceeds*commission,minimum)
    return (proceeds-sell_fee-proceeds*fx)/notional-1


def fold_spread_scenarios(ranked, observed, selected, bottom, policy):
    """Compute all frozen bps scenarios on EXACT same as-of K-member universe."""
    levels=policy["costs"]["slippage_spread_eur_bps_scenarios"]
    if levels != [0,10,25,50] or len(ranked)<3:
        raise ValueError("Registered V3 spread scenarios or original pool changed")
    cost=policy["costs"]
    k=policy["comparisons"]["selected_top_k"]
    capital=cost["notional_eur"]/k
    ids={r["id"] for r in ranked}
    if (len(ids)!=len(ranked) or set(observed)!=ids
            or len(selected)!=k or len(bottom)!=k
            or any(x["id"] not in ids for x in selected+bottom)):
        raise ValueError("Spread scenario must use original full same-K research cohort")
    report=[]
    for bps in levels:
        returns={
            r["id"]:net_at_bps(observed[r["id"]]["gross"],r["currency"],
                               cost,capital,bps)
            for r in ranked
        }
        selected_net=mean(returns[x["id"]] for x in selected)
        bottom_net=mean(returns[x["id"]] for x in bottom)
        same_k_expected=mean(returns.values())
        report.append({
            "bps_each_side":bps,
            "selected_net":round(selected_net,8),
            "bottom_net":round(bottom_net,8),
            "same_K_random_expected_net":round(same_k_expected,8),
            "same_K_excess_net":round(selected_net-same_k_expected,8),
        })
    return report


def aggregate_spread_scenarios(folds, levels):
    if levels != [0,10,25,50]:
        raise ValueError("V3 spread scenario aggregation must use frozen levels")
    if not folds:
        return []
    aggregate=[]
    for index,bps in enumerate(levels):
        snapshots=[fold["slippage_spread_scenarios_DESCRIPTIVE_ONLY"][index]
                   for fold in folds]
        if any(x["bps_each_side"]!=bps for x in snapshots):
            raise ValueError("V3 spread scenario fold ordering changed")
        aggregate.append({
            "bps_each_side":bps,
            "mean_selected_net":round(mean(s["selected_net"] for s in snapshots),8),
            "mean_bottom_net":round(mean(s["bottom_net"] for s in snapshots),8),
            "mean_same_K_random_expected_net":round(
                mean(s["same_K_random_expected_net"] for s in snapshots),8),
            "mean_same_K_excess_net_DESCRIPTIVE_ONLY":round(
                mean(s["same_K_excess_net"] for s in snapshots),8),
        })
    return aggregate

"""R-008: historical *illustrative* equal-weight risk, not portfolio advice.

Reads only the same 61 dated EUR closes from the already validated B bundle
through research_risk. No personal holdings, weights, forecasts, trading,
optimizer, or API calls. Missing aligned observations are explicit.
"""
from __future__ import annotations

import math
from statistics import mean

VERSION = "r008-source-bound-illustrative-portfolio-stress-v1"
MIN_COMMON_RETURNS = 20
MAX_ILLUSTRATIVE_ASSETS = 3


def _sample_std(values):
    if len(values) < 2:
        return None
    mu = mean(values)
    return math.sqrt(sum((x-mu)**2 for x in values)/(len(values)-1))


def build_portfolio_stress(ids, by_id, pairs, *, synthetic):
    """Fixed equal-weight illustration of first up to 3 ordered B risk ids.

    Group returns are derived from same-calendar EUR closes for all members.
    No optimized/selected weights and no claim of holdings-level suitability.
    """
    if not isinstance(ids, list) or len(ids) != len(set(ids)):
        raise ValueError("Duplicate or invalid risk identities")
    if any(uid not in by_id for uid in ids):
        raise ValueError("Risk member not present in source-bound EUR series")
    # Full covariance-like correlation table is a display of the source-bound
    # pairwise diagnostics; missing entries remain None, never filled as zero.
    correlations = {(row["id_a"], row["id_b"]): row["correlation_eur_eod_historical"]
                    for row in pairs}
    matrix=[]
    for i, ida in enumerate(ids):
        row=[]
        for j, idb in enumerate(ids):
            if i == j:
                prices=by_id[ida]["observations"]
                days=sorted(prices)
                changes=[float(prices[days[k]]/prices[days[k-1]]-1)
                         for k in range(1,len(days))]
                std=_sample_std(changes)
                val=1.0 if std is not None and std > 0 else None
            else:
                val=correlations.get((ida,idb)) if i<j else correlations.get((idb,ida))
            row.append(val)
        matrix.append(row)
    chosen = ids[:MAX_ILLUSTRATIVE_ASSETS]
    base={
        "schema_version":VERSION,
        "method":"FIXED_EQUAL_WEIGHT_DAILY_REBALANCED_HISTORICAL_ILLUSTRATION",
        "status":"INSUFFICIENT_CANDIDATES",
        "identities":chosen,
        "weights":[str(1/len(chosen)) for _ in chosen] if chosen else [],
        "correlation_matrix_ids":list(ids),
        "correlation_matrix":matrix,
        "common_return_observations":0,
        "first_common_session":None,
        "last_common_session":None,
        "historical_annualized_volatility_pct":None,
        "historical_worst_day_pct":None,
        "historical_max_drawdown_pct":None,
        "parallel_shock_minus_10_pct":None,
        "parallel_shock_minus_20_pct":None,
        "portfolio_optimality_asserted":False,
        "actual_holdings_weights_used":False,
        "diversification_or_downside_forecast_verified":False,
        "risk_approved":False,
        "trade_ready":False,
        "synthetic_fictional_data":synthetic,
        "limitations":[
            "Illustrative top ordered 2-3 risk candidates, NOT investment selection or actual holdings.",
            "Equal-weight daily-rebalanced mathematical illustration excludes fees, slippage, taxes, bid/ask and leverage.",
            "Only common historical EUR EOD dates; US closes and ECB FX fixings are asynchronous.",
            "Fixed parallel -10%/-20% scenarios are assumptions, NOT observed or forecast losses.",
            "Nonlinear payoff products, counterparty exposures and terminal-payoff path dependence are NOT modeled.",
            "Historical drawdown/volatility do not predict future losses or establish portfolio suitability.",
        ],
    }
    if len(chosen)<2:
        return base
    dates=sorted(set.intersection(*[set(by_id[u]["observations"]) for u in chosen]))
    if len(dates)<MIN_COMMON_RETURNS+1:
        base["status"]="INSUFFICIENT_ALIGNED_EUR_EOD_SESSIONS"
        base["common_return_observations"]=max(0,len(dates)-1)
        if dates:
            base["first_common_session"]=dates[0]
            base["last_common_session"]=dates[-1]
        return base
    portfolio=[]
    for k in range(1,len(dates)):
        daily=[float(by_id[u]["observations"][dates[k]] /
                     by_id[u]["observations"][dates[k-1]]-1) for u in chosen]
        value=mean(daily)
        if not math.isfinite(value) or value<=-1:
            raise ValueError("Risk series contains invalid or nonfinite source returns")
        portfolio.append(value)
    wealth=1.0
    peak=1.0
    max_drawdown=0.0
    for ret in portfolio:
        wealth*=1+ret
        peak=max(peak,wealth)
        max_drawdown=max(max_drawdown,1-wealth/peak)
    vol=_sample_std(portfolio)
    base.update({
        "status":"SYNTHETIC_EQUAL_WEIGHT_STRESS_ONLY" if synthetic else
                 "SOURCE_BOUND_HISTORICAL_STRESS_UNVERIFIED_NOT_TRADE_READY",
        "common_return_observations":len(portfolio),
        "first_common_session":dates[0],
        "last_common_session":dates[-1],
        "historical_annualized_volatility_pct":round(100*vol*math.sqrt(252),4) if vol is not None else None,
        "historical_worst_day_pct":round(100*min(portfolio),4),
        "historical_max_drawdown_pct":round(100*max_drawdown,4),
        "parallel_shock_minus_10_pct":-10.0,
        "parallel_shock_minus_20_pct":-20.0,
    })
    return base

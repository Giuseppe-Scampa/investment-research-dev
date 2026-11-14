"""One thousand *null* random-walk worlds for preregistered V2 type-I error.

Runs the production Block B 61-session score, 30 following return intervals,
TOP2/BOTTOM2, same-K random controls, N-leg costed universe, and 10000
whole-fold bootstrap draws. All returns and prices here are SIMULATED;
this cannot validate historical investment returns or source licensing.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

from .historical_calendar_v2 import dates_v2
from .research_historical_validation_v2 import v2_protocol,SCHEMA
from .research_historical_validation import _spearman
from .research_screen import _score_indicators,_market_score


def run_null_worlds(*,worlds=1000):
    policy,sha=v2_protocol()
    if not isinstance(worlds,int) or not 1<=worlds<=1000:
        raise ValueError("V2 null world count must be between 1 and frozen 1000")
    import numpy as np
    config=policy["comparisons"]
    n=int(config["negative_control_random_walk_assets"])
    f=int(config["negative_control_random_walk_folds"])
    if n!=30 or f!=30 or config["random_portfolios"]!=10000:
        raise ValueError("V2 null control population or random-comparator protocol changed")
    from .historical_calendar_v2 import dates_v2
    dates=dates_v2(date(2024,1,2),date(2024,7,1),"XMIL")[:92]
    if len(dates)!=92:
        raise ValueError("Unexpected reference null calendar session count")
    seed=int(config["negative_control_seed"])
    rng=np.random.default_rng(seed)
    cost=policy["costs"]
    notional=cost["notional_eur"]
    fee=cost["commission_fraction_each_side"]
    min_fee=cost["minimum_commission_eur_each_side"]
    selection_count=config["selected_top_k"]
    boot=int(policy["statistics"]["bootstrap_repetitions"])
    random_trials=config["random_portfolios"]
    count_accepted=0
    count_spurious_excess=0
    count_spurious_ic=0
    wealth_of_folds=[]
    for world in range(worlds):
        scored=np.empty((f,n))
        future_gross=np.empty((f,n))
        net_k=np.empty((f,n))
        net_n=np.empty((f,n))
        for fold in range(f):
            # Independent returns across both fold and symbol; no true
            # predictable relation between 61 lookback and future 30.
            daily=rng.normal(loc=0,scale=.012,size=(n,91))
            prices=np.concatenate([
                np.full((n,1),100.,dtype=np.float64),
                100*np.exp(np.cumsum(daily,axis=1))],axis=1)
            for index in range(n):
                old=[(dates[j],Decimal(str(prices[index,j])),
                      Decimal(100000+1000*index)) for j in range(61)]
                indicators=_score_indicators(old)
                scored[fold,index]=_market_score(indicators)[0]
            next_entry=prices[:,61]
            last=prices[:,91]
            growth=last/next_entry
            future_gross[fold,:]=growth-1.
            for k,mat in ((selection_count,net_k),(n,net_n)):
                leg=notional/k
                buy_fee=max(leg*fee,min_fee)
                acquired=leg-buy_fee
                final=acquired*growth
                sell_fee=np.maximum(final*fee,min_fee)
                mat[fold,:]=(final-sell_fee)/leg-1
        ranks=np.argsort(-scored,axis=1,kind="stable")
        top=ranks[:,:2];bottom=ranks[:,-2:]
        observed=net_k[np.arange(f)[:,None],top].mean(axis=1)
        inverse=net_k[np.arange(f)[:,None],bottom].mean(axis=1)
        benchmark=net_n.mean(axis=1)
        excess=observed-benchmark
        ic=np.array([_spearman(scored[j].tolist(),future_gross[j].tolist())
                     for j in range(f)],dtype=float)
        if not np.all(np.isfinite(ic)):
            raise ValueError("Random-walk null unexpectedly produced nonfinite rank correlation")
        draws=rng.integers(0,f,size=(boot,f),endpoint=False)
        mean_e=excess[draws].mean(axis=1)
        mean_ic=ic[draws].mean(axis=1)
        lo_e=float(np.quantile(mean_e,.025))
        lo_ic=float(np.quantile(mean_ic,.025))
        if lo_e>0:
            count_spurious_excess+=1
        if lo_ic>0:
            count_spurious_ic+=1
        # Exactly K=2 randomly selected, same simulated per-leg costs.
        lhs=rng.integers(0,n,size=(random_trials,f),endpoint=False)
        rhs=rng.integers(0,n-1,size=(random_trials,f),endpoint=False)
        rhs=rhs+(rhs>=lhs)
        indexed=np.arange(f)[None,:]
        rand_mean=(net_k[indexed,lhs]+net_k[indexed,rhs]).mean(axis=1)/2
        chosen_mean=float(np.mean(observed))
        percentile=float(np.mean(rand_mean<chosen_mean))
        passed=(lo_e>0 and lo_ic>0 and percentile>=
                policy["statistics"]["random_portfolio_percentile_at_least"]
                and float(np.mean(observed-inverse))>0)
        if passed:count_accepted+=1
        wealth_of_folds.append(float(np.mean(excess)))
    p=count_accepted/worlds
    # Wilson one-sided-conservative 95% upper error bound.
    z=1.96
    denominator=1+z*z/worlds
    center=(p+z*z/(2*worlds))/denominator
    spread=z*math.sqrt(p*(1-p)/worlds+z*z/(4*worlds*worlds))/denominator
    upper=min(1,center+spread)
    return {
        "schema_version":"V3_V2_RANDOM_WALK_NULL_CALIBRATION",
        "preregistered_protocol_sha256":sha,
        "worlds_completed":worlds,"worlds_preregistered":1000,
        "independent_null_folds_per_world":f,
        "synthetic_random_walk_assets_per_world":n,
        "random_portfolio_trials_per_world":random_trials,
        "bootstrap_resamples_per_world":boot,
        "worlds_falsely_passed_all_diagnostic_gates":count_accepted,
        "false_positive_rate_observed":round(p,6),
        "false_positive_rate_Wilson95_upper":round(upper,6),
        "worlds_with_spurious_excess_lower_CI_positive":count_spurious_excess,
        "worlds_with_spurious_IC_lower_CI_positive":count_spurious_ic,
        "null_calibration_threshold":policy["comparisons"]["negative_control_target_false_positive_rate"],
        "full_preregistered_world_count_completed":worlds==1000,
        "null_calibration_passed":bool(worlds==1000 and upper<=.05),
        "mean_null_excess_vs_N_leg_universe":round(float(sum(wealth_of_folds)/worlds),8),
        "warning_N_leg_benchmark_minimum_fee_bias":True,
        "price_source":"SIMULATED_INDEPENDENT_GAUSSIAN_RANDOM_WALKS",
        "historical_returns_verified":False,
        "predictive_edge_certified":False,
        "trade_ready":False,
    }

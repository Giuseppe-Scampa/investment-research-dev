"""V2 preregistered 2021–2026 multiyear falsification of existing B score.

This module never orders securities, scrapes providers or treats a later
download as a contemporaneous investable research universe. V1 and the
2026 tax/settlement calendars are unchanged.
"""
from __future__ import annotations

from datetime import date,timedelta
from decimal import Decimal
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean,median,NormalDist

from .historical_calendar_v2 import dates_v2,session_v2
from .research_bundle import load_bundle,SYNTHETIC,EXTERNAL
from .research_historical_validation import (
    _spearman,_ci,_net_trade,_adjusted_eur_prices,
)
from .research_screen import _score_indicators,_market_score,WEIGHTS
from .constraints import instrument_constraints

PROTOCOL_V2=Path(__file__).resolve().parents[2]/"config/backtest/v3_long_horizon_protocol_v2_2026-11-10.json"
FROZEN_BLOB_SHA="fc2a7013171f156449f324749b89970cff02bb93"
SCHEMA="V3_LONG_HORIZON_BACKTEST_V2"
SUPPORTED_PROVIDERS={"FWB_PERSONAL_HISTORY_FILE","EURONEXT_PERSONAL_HISTORY_FILE"}
ELIGIBLE_BASIS={"FWB_OPERATOR_ASSERTED_ADJUSTED_NOT_INDEPENDENTLY_VERIFIED",
                "EURONEXT_OPERATOR_SELECTED_ADJUSTED_NOT_INDEPENDENTLY_VERIFIED"}
MAX_ASSETS=500


def v2_protocol():
    raw=PROTOCOL_V2.read_bytes()
    blob=b"blob "+str(len(raw)).encode()+bytes([0])+raw
    if hashlib.sha1(blob).hexdigest()!=FROZEN_BLOB_SHA:
        raise ValueError("PREREGISTERED_V2_PROTOCOL_CHANGED; create a new protocol version")
    policy=json.loads(raw)
    if (policy["schema_version"]!="v3-historical-evaluation-protocol-v2"
            or policy["score"]["weights_frozen"]!=WEIGHTS
            or policy["comparisons"]["selected_top_k"]!=2
            or policy["comparisons"]["random_portfolios"]!=10000
            or policy["cohort"]["forward_return_intervals"]!=30
            or policy["calendar"]["required_version"]!="4.13.1"):
        raise ValueError("V2 scoring weights or frozen controls differ from baseline")
    return policy,hashlib.sha256(raw).hexdigest()


def preregistered_anchors(venues,policy=None):
    p=policy or v2_protocol()[0]
    schedule=p["cohort"]
    first=date.fromisoformat(schedule["first_decision_date"])
    last=date.fromisoformat(schedule["last_decision_date"])
    if not venues or len(set(venues))>5:
        raise ValueError("Invalid V2 venue basket")
    # Materialise version-pinned calendars once per venue.
    valid={v:set(dates_v2(date(2020,1,1),date(2026,12,31),v))
           for v in sorted(set(venues))}
    points=[]
    current=first
    while current<=last:
        candidate=current
        for _ in range(schedule["max_anchor_rollback_calendar_days"]+1):
            if all(candidate.isoformat() in days for days in valid.values()):
                break
            candidate-=timedelta(days=1)
        else:
            raise ValueError("No common historical exchange trading session")
        if not points or points[-1]!=candidate.isoformat():
            points.append(candidate.isoformat())
        current+=timedelta(days=schedule["decision_step_calendar_days"])
    return tuple(points)


def _verified_61(dated,venue,t):
    before=[r for r in dated if r[0]<=t]
    if len(before)<61 or before[-1][0]!=t:
        return None
    selected=before[-61:]
    expected=dates_v2(date.fromisoformat(selected[0][0]),
                      date.fromisoformat(t),venue)
    if tuple(r[0] for r in selected)!=expected:
        return None
    if any(abs(selected[j][1]/selected[j-1][1]-1)>=Decimal(".15")
           for j in range(1,61)):
        return None
    return selected


def _eligible(asset,dated,t,settings):
    if (asset["asset_type"] not in ("EQUITY","ETF_UCITS","ETC","ETN")
            or not asset.get("sector")
            or asset.get("oil_exposure")!="none"
            or any(x.level=="BLOCKED" for x in instrument_constraints(
                asset,settings,new_purchase=True))):
        return None
    # Disclosure at T: prohibit future-launched instruments; if exact
    # listing vintage unavailable, retrospective results remain uncertified.
    listed=asset.get("listing_date")
    if listed is not None and listed>t:
        return None
    ended=asset.get("delisted_date")
    if ended is not None and ended<t:
        return None
    history=_verified_61(dated,asset["venue"],t)
    if history is None:
        return None
    m=_score_indicators(history)
    score,_=_market_score(m)
    return {"id":asset["id"],"venue":asset["venue"],
            "currency":asset["currency"],"score":score}


def _forward(candidate,dated,t,policy,notional):
    holding=policy["cohort"]["forward_return_intervals"]
    path=[row for row in dated if row[0]>t][:holding+1]
    if len(path)!=holding+1:
        return None
    expected=dates_v2(date.fromisoformat(path[0][0]),
                      date.fromisoformat(path[-1][0]),candidate["venue"])
    if tuple(row[0] for row in path)!=expected:
        return None
    # Entry must be the NEXT trading session, never two or more days later.
    expected_entry=dates_v2(date.fromisoformat(t)+timedelta(days=1),
                            date.fromisoformat(path[0][0]),candidate["venue"])
    if expected_entry!=(path[0][0],):
        return None
    if any(abs(path[i][1]/path[i-1][1]-1)>=Decimal(".15")
           for i in range(1,len(path))):
        return None
    c=policy["costs"]
    gross_price_return=float(path[-1][1]/path[0][1]-1)
    net,curve,gross=_net_trade(path,notional=notional,
            fee_bps=c["commission_fraction_each_side"],
            min_fee=c["minimum_commission_eur_each_side"],
            fx_bps=c["usd_fx_fraction_each_side"],
            usd=candidate["currency"]=="USD")
    return {"gross":gross_price_return,"net":net,"curve":curve,
            "exit_date":path[-1][0]}


def _dd(curves):
    value=[mean(xs[j] for xs in curves) for j in range(len(curves[0]))]
    peak=1.
    drawdown=0.
    for x in value:
        peak=max(peak,x)
        drawdown=min(drawdown,x/peak-1)
    return drawdown


def _bootstrap(folds,policy):
    if len(folds)<2:
        return None,None
    rng=random.Random(policy["statistics"]["bootstrap_seed"])
    n=policy["statistics"]["bootstrap_repetitions"]
    excess=[];ic=[]
    for _ in range(n):
        sample=rng.choices(folds,k=len(folds))
        excess.append(mean(f["excess"] for f in sample))
        indicators=[f["ic"] for f in sample if f["ic"] is not None]
        if indicators:
            ic.append(mean(indicators))
    return _ci(excess),_ci(ic)


def evaluate_v2(bundle,*,settings=None):
    policy,digest=v2_protocol()
    manifest,items,fx,events=load_bundle(Path(bundle))
    if (manifest["mode"] not in (SYNTHETIC,EXTERNAL)
            or len(items)<3 or len(items)>MAX_ASSETS or events):
        raise ValueError("V2 input must be small bounded original or synthetic bundle without hindsight events")
    if manifest["mode"]==EXTERNAL:
        for asset,bars,_ in items:
            meta=asset["prices"]
            if (meta.get("provider") not in SUPPORTED_PROVIDERS
                    or meta.get("price_basis") not in ELIGIBLE_BASIS):
                raise ValueError("REAL_V2_SOURCE_BLOCKED: original adjusted FWB/Euronext only, no Tiingo Starter")
    settings=settings or {"exclude_primary_oil":True,
        "exclude_additional_gold":True,"avoid_duplicate_eurostoxx50":True}
    aligned={}
    for asset,bars,_ in items:
        converted=_adjusted_eur_prices(asset,bars,fx)
        if converted is None:
            raise ValueError("V2 missing original same-day EUR FX")
        if len(converted)>2000:
            raise ValueError("V2 historic price series above bounded cap")
        aligned[asset["id"]]=(asset,converted)
    if len(aligned)!=len(items):
        raise ValueError("V2 duplicate original security identity")
    anchors=preregistered_anchors([a["venue"] for a,b,_ in items],policy)
    fold_results=[]
    rejected=[]
    last_exit=None
    selected_k=policy["comparisons"]["selected_top_k"]
    for t in anchors:
        if t>=manifest["as_of"]:
            rejected.append([t,"BEYOND_SOURCE_CUTOFF"]);continue
        if last_exit is not None and t<=last_exit:
            rejected.append([t,"OVERLAPPING_HOLDOUT"]);continue
        available=[]
        for asset,bars in aligned.values():
            c=_eligible(asset,bars,t,settings)
            if c is not None:available.append(c)
        if len(available)<max(3,selected_k+1):
            rejected.append([t,"TOO_FEW_AS_OF_ELIGIBLE"]);continue
        # Set is frozen before *any* future path is inspected.
        ranked=sorted(available,key=lambda c:(-c["score"],c["id"]))
        sample_at_k={}
        missing=False
        for c in ranked:
            result=_forward(c,aligned[c["id"]][1],t,policy,
                            policy["costs"]["notional_eur"]/selected_k)
            if result is None:
                missing=True;break
            sample_at_k[c["id"]]=result
        if missing:
            rejected.append([t,"MISSING_FUTURE_OR_SPLIT;DO_NOT_DROP_LOSERS"]);continue
        chosen=ranked[:selected_k];inverse=ranked[-selected_k:]
        # Universe comparator needs N trades, separate min-fee drag.
        univ=[]
        for c in ranked:
            q=_forward(c,aligned[c["id"]][1],t,policy,
                       policy["costs"]["notional_eur"]/len(ranked))
            if q is None:raise ValueError("Future completeness should be invariant to position size")
            univ.append(q["net"])
        picked=mean(sample_at_k[c["id"]]["net"] for c in chosen)
        rejected_strategy=mean(sample_at_k[c["id"]]["net"] for c in inverse)
        benchmark=mean(univ)
        ic=_spearman([c["score"] for c in ranked],
                     [sample_at_k[c["id"]]["gross"] for c in ranked])
        exit_day=max(q["exit_date"] for q in sample_at_k.values())
        last_exit=exit_day
        fold_results.append({
            "date":t,"exit_date":exit_day,"eligible":len(ranked),
            "selected_ids":[c["id"] for c in chosen],
            "bottom_ids":[c["id"] for c in inverse],
            "selected_net":round(picked,8),
            "bottom_net":round(rejected_strategy,8),
            "universe_net":round(benchmark,8),
            "excess":round(picked-benchmark,8),
            "ic":round(ic,8) if ic is not None else None,
            "max_drawdown":round(_dd([sample_at_k[c["id"]]["curve"] for c in chosen]),8),
            "selection_above_median_rate":round(mean(
                sample_at_k[c["id"]]["gross"]>
                median(x["gross"] for x in sample_at_k.values())
                for c in chosen),4),
            "_candidate_net":{c["id"]:sample_at_k[c["id"]]["net"] for c in ranked},
        })
    rng=random.Random(policy["comparisons"]["random_seed"])
    trials=policy["comparisons"]["random_portfolios"]
    random_pool=[]
    if fold_results:
        for _ in range(trials):
            value=[]
            for fold in fold_results:
                ids=rng.sample(tuple(fold["_candidate_net"]),selected_k)
                value.append(mean(fold["_candidate_net"][uid] for uid in ids))
            random_pool.append(mean(value))
    observed=mean(f["selected_net"] for f in fold_results) if fold_results else None
    rank_pct=(sum(x<observed for x in random_pool)/len(random_pool)) if random_pool else None
    excess_ci,ic_ci=_bootstrap(fold_results,policy)
    enough=(len(fold_results)>=policy["cohort"]["minimum_independent_folds_for_predictive_evidence"]
            and all(f["eligible"]>=policy["cohort"]["minimum_eligible_instruments"] for f in fold_results))
    diagnostics=bool(enough and excess_ci and ic_ci and
        excess_ci[0]>0 and ic_ci[0]>0 and rank_pct is not None and
        rank_pct>=policy["statistics"]["random_portfolio_percentile_at_least"] and
        mean(f["selected_net"]-f["bottom_net"] for f in fold_results)>0)
    for fold in fold_results:
        del fold["_candidate_net"]
    data_mode=("SYNTHETIC_NO_MARKET_EVIDENCE" if manifest["mode"]==SYNTHETIC
               else "REAL_SOURCE_RETROSPECTIVE_DATA_RIGHTS_AND_VINTAGE_REVIEW_REQUIRED")
    return {
        "schema_version":SCHEMA,"preregistered_protocol_sha256":digest,
        "protocol_git_blob_sha":FROZEN_BLOB_SHA,
        "input_manifest_sha256":hashlib.sha256(
            (Path(bundle)/"manifest.json").read_bytes()).hexdigest(),
        "status":data_mode,"as_of":manifest["as_of"],
        "complete_nonoverlapping_folds":len(fold_results),
        "planned_decision_anchors":len(anchors),
        "rejections":rejected,"folds":fold_results,
        "mean_net_selected":round(observed,8) if observed is not None else None,
        "mean_excess_vs_universe":round(mean(f["excess"] for f in fold_results),8)
            if fold_results else None,
        "mean_rank_IC":round(mean(f["ic"] for f in fold_results if f["ic"] is not None),8)
            if any(f["ic"] is not None for f in fold_results) else None,
        "mean_top_minus_bottom":round(mean(f["selected_net"]-f["bottom_net"]
            for f in fold_results),8) if fold_results else None,
        "confidence_interval_95_excess":excess_ci,
        "confidence_interval_95_ic":ic_ci,
        "random_portfolio_trials":len(random_pool),
        "random_percentile":round(rank_pct,6) if rank_pct is not None else None,
        "minimum_fold_and_universe_power_met":enough,
        "statistical_diagnostic_gate_without_null_control":diagnostics,
        "random_walk_false_positive_rate_calibrated":False,
        "historical_corporate_actions_independently_verified":False,
        "historical_point_in_time_universe_independently_verified":False,
        "data_rights_independently_verified":False,
        "italian_tax_by_isin_verified":False,
        "predictive_edge_certified":False,
        "trade_ready":False,
        "limitations":[
            "Not contemporaneous point-in-time membership unless issuer listing/delisting evidence separately audited.",
            "Imported adjusted flags are operator assertions; independent split/dividend/rights validation still pending.",
            "A noncommercial license may restrict third-party distribution of raw prices.",
            "Slippage/scenario spreads and issuer taxes remain outside this descriptive score.",
            "Minimum fold count cannot by itself establish adequate power for a 0.05 true IC.",
            "No live/paper out-of-sample performance is certified.",
        ],
    }


def approximate_power(policy=None):
    """Pre-run normal approximation; not calibrated type-I error or market edge."""
    p=policy or v2_protocol()[0]
    out=[]
    normal=NormalDist()
    for assets in (20,30,40):
        for folds in (10,20,30,40,60):
            se=(assets-1)**(-.5)*folds**(-.5)
            for ic in p["power_calibration"]["pre_run_simulation_effect_sizes_IC"]:
                signal=ic/se
                power=1-normal.cdf(1.9599639845-signal)+normal.cdf(-1.9599639845-signal)
                out.append({"assets":assets,"folds":folds,"IC":ic,
                            "SE_approx":round(se,5),"two_sided_power_approx":round(power,5)})
    return out

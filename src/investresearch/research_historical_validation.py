"""Preregistered non-predictive R-007/R-008 historical validation.

Only existing hash-checked B bundles; no network, quote harvesting or paid
providers. The *same* frozen B indicator and market-score functions select
historical portfolios at date T. Future prices are accessed solely after
the selection and universe eligibility have been fixed.

A 2026 session calendar plus later-retrieved adjusted files is retrospective
replay, NOT a genuinely contemporaneous investable universe, licensed data
proof, or real return. No tax-loss wallet or personalized money input here.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean, median, stdev

from .constraints import instrument_constraints
from .market_calendar import session
from .research_bundle import SYNTHETIC, EXTERNAL, load_bundle
from .research_screen import (
    WEIGHTS, _score_indicators, _market_score, _history_quality,
    _fx_dated_prices,
)

VERSION = "v3-2026-frozen-historical-falsification-v1"
# SHA-256 of the protocol actually committed BEFORE synthetic outcome review,
# GitHub commit 8755eb8821b9b0a9f6fe26140c39e67cf5c211c6.
FROZEN_PROTOCOL_SHA256 = "e2ce1ba5928218c2ff78b7962058e7f862713226ff51ef574be5aac8617a26d2"
PROTOCOL = Path(__file__).resolve().parents[2]/"config/backtest/v3_2026_fixed_protocol.json"
PRICE_BASIS_ALLOWLIST = {
    "FWB_OPERATOR_ASSERTED_ADJUSTED_NOT_INDEPENDENTLY_VERIFIED",
    "EURONEXT_OPERATOR_SELECTED_ADJUSTED_NOT_INDEPENDENTLY_VERIFIED",
}
ALLOWED_ASSET_TYPES = {"EQUITY", "ETF_UCITS", "ETC", "ETN"}
MAX_ASSETS = 500
MAX_DATES = 5000


def protocol_file(path=PROTOCOL):
    loc=Path(path).resolve()
    if loc!=PROTOCOL.resolve() or not loc.is_file():
        raise ValueError("Use only the previously committed V3 protocol, never optimize after outcomes")
    raw=loc.read_bytes()
    p=json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!=FROZEN_PROTOCOL_SHA256:
        raise ValueError("FROZEN V3 protocol hash changed after pre-registration; new protocol/version required")
    if (p.get("schema_version")!="v3-2026-frozen-evaluation-protocol-v1"
            or p.get("registered_on")!="2026-11-07"
            or p.get("cohort",{}).get("freeze_ranking_weights")!=WEIGHTS
            or p.get("schedule",{}).get("holding_return_intervals")!=30
            or p.get("portfolio",{}).get("random_portfolios")!=10000
            or p.get("statistics",{}).get("bootstrap_resamples")!=10000):
        raise ValueError("Frozen V3 historical protocol or score weights modified")
    return p,hashlib.sha256(raw).hexdigest()


def _prereview_source_gate(manifest,items):
    """Free Tiingo Starter cannot be saved/backtested under current terms."""
    if len(items)>MAX_ASSETS:
        raise ValueError("Backtest security count exceeds bounded reviewed universe")
    if manifest["mode"]==SYNTHETIC:
        return True
    if manifest["mode"]!=EXTERNAL:
        raise ValueError("Only explicitly original external or synthetic demonstration bundles")
    for asset,bars,_ in items:
        provider=asset["prices"]["provider"]
        if provider=="TIINGO_EOD_PERSONAL_RESEARCH":
            raise ValueError("TIINGO_STARTER_NO_BACKTEST_OR_PERSISTENT_STORAGE: provider rights not suitable")
        if provider not in ("FWB_PERSONAL_HISTORY_FILE","EURONEXT_PERSONAL_HISTORY_FILE"):
            raise ValueError("Original history provider not authorized for this frozen experiment")
        if asset["prices"].get("price_basis") not in PRICE_BASIS_ALLOWLIST:
            raise ValueError("Original unadjusted history excluded from backtest")
        if not 61<=len(bars)<=MAX_DATES:
            raise ValueError("Original price history too short or oversize")
    return False


def _adjusted_eur_prices(asset,bars,fx):
    if any(set(r)!={"date","close","volume"} for r in bars):
        raise ValueError("Unexpected future/target column in original price inputs")
    aligned,issue=_fx_dated_prices(bars,fx,asset["currency"])
    if issue:
        return None
    if len(aligned)>MAX_DATES:
        raise ValueError("Excessive aligned historic prices")
    return aligned


def _decision_calendar_dates(policy,venues):
    first=date.fromisoformat(policy["schedule"]["first_decision_date"])
    last=date.fromisoformat(policy["schedule"]["last_decision_date"])
    step=policy["schedule"]["decision_step_calendar_days"]
    if not (1<=step<=365 and first<=last<=date(2026,12,31)):
        raise ValueError("Invalid frozen research decision schedule")
    anchors=[]
    cursor=first
    while cursor<=last:
        prior=cursor
        for _ in range(11):
            if all(session(prior,v) for v in venues):
                anchors.append(prior.isoformat())
                break
            prior-=timedelta(days=1)
        else:
            raise ValueError("No common validated exchange session near fixed decision anchor")
        cursor+=timedelta(days=step)
    return sorted(set(anchors))


def _rank(values):
    ordered=sorted(range(len(values)),key=lambda i:values[i])
    ranks=[0.0]*len(values)
    i=0
    while i<len(values):
        j=i+1
        while j<len(values) and values[ordered[i]]==values[ordered[j]]:
            j+=1
        average=(i+1+j)/2.
        for k in range(i,j):
            ranks[ordered[k]]=average
        i=j
    return ranks


def _pearson(x,y):
    if len(x)<3 or len(x)!=len(y):
        return None
    ax,ay=mean(x),mean(y)
    a=[v-ax for v in x]
    b=[v-ay for v in y]
    sx=sum(v*v for v in a);sy=sum(v*v for v in b)
    if sx<=0 or sy<=0:
        return None
    return sum(u*v for u,v in zip(a,b))/math.sqrt(sx*sy)


def _spearman(x,y):
    return _pearson(_rank(x),_rank(y))


def _net_trade(path,*,notional,fee_bps,min_fee,fx_bps,usd):
    """Entry next EOD, 30 daily return intervals; commissions on both sides."""
    buy=max(notional*fee_bps,min_fee)
    entry=notional-buy-notional*(fx_bps if usd else 0)
    values=[entry*float(bar[1]/path[0][1]) for bar in path]
    final=values[-1]
    selling=max(final*fee_bps,min_fee)
    net=final-selling-final*(fx_bps if usd else 0)
    return net/notional-1,[v/notional for v in values],float(path[-1][1]/path[0][1]-1)


def _candidate(asset,dated,t,settings):
    """Only dates <= T enter any eligible selection and market score."""
    if (asset["asset_type"] not in ALLOWED_ASSET_TYPES
            or any(flag.level=="BLOCKED" for flag in
                   instrument_constraints(asset,settings,new_purchase=True))
            or not asset.get("sector")
            or asset.get("oil_exposure") not in ("none", "unknown")):
        return None
    prior=[r for r in dated if r[0]<=t]
    if not prior or prior[-1][0]!=t or len(prior)<61:
        return None
    old=prior[-61:]
    history=_history_quality(old,asset["venue"])
    if not history["verified"]:
        return None
    # The same B score functions and coefficients as production screening.
    metrics=_score_indicators(old)
    score,_=_market_score(metrics)
    return {"id":asset["id"],"venue":asset["venue"],
            "currency":asset["currency"],"score":score}


def _outcome(candidate,aligned,t,horizon,params,total_candidates):
    later=[r for r in aligned if r[0]>t]
    if len(later)<horizon+1:
        return None
    path=later[:horizon+1]
    # A sparse post-selection series must not magically become 30 sessions.
    expected=[]
    start=date.fromisoformat(path[0][0])
    end=date.fromisoformat(path[-1][0])
    for offset in range((end-start).days+1):
        day=start+timedelta(days=offset)
        if session(day,candidate["venue"]):
            expected.append(day.isoformat())
    if [d for d,_,_ in path]!=expected or len(expected)!=horizon+1:
        return None
    fee=params["buy_sell_commission_fraction"]
    minimum=params["minimum_commission_eur_each_side"]
    exchange=params["usd_fx_fraction_each_side"]
    capital=params["generic_notional_eur"]/total_candidates
    net,curve,gross=_net_trade(path,notional=capital,fee_bps=fee,
                             min_fee=minimum,fx_bps=exchange,
                             usd=candidate["currency"]=="USD")
    return {"id":candidate["id"],"score":candidate["score"],
            "net":net,"gross":gross,"curve":curve,
            "entry_date":path[0][0],"exit_date":path[-1][0]}


def _drawdown(curves):
    points=[mean(v[i] for v in curves) for i in range(len(curves[0]))]
    top=1.0
    trough=0.0
    for value in points:
        top=max(top,value)
        trough=min(trough,value/top-1)
    return trough


def _ci(resampled,level=0.95):
    if len(resampled)<2:
        return None
    arr=sorted(resampled)
    alpha=(1-level)/2
    return [round(arr[int(alpha*(len(arr)-1))],8),
            round(arr[int((1-alpha)*(len(arr)-1))],8)]


def validate_historical(bundle,*,protocol_path=PROTOCOL,
                        settings=None):
    policy,policy_hash=protocol_file(protocol_path)
    manifest,items,fx,events=load_bundle(Path(bundle))
    synthetic=_prereview_source_gate(manifest,items)
    if len(items)<3:
        raise ValueError("Frozen backtest requires at least three securities to compare")
    if events:
        raise ValueError("Historic event reference is not time-vintaged; outcome study blocked")
    settings=settings or {
        "exclude_primary_oil":True,"exclude_additional_gold":True,
        "avoid_duplicate_eurostoxx50":True,
    }
    identifiers=[a["id"] for a,b,f in items]
    if len(identifiers)!=len(set(identifiers)):
        raise ValueError("Repeated identity in retrospective study")
    universe={asset["id"]:(asset,_adjusted_eur_prices(asset,bars,fx))
              for asset,bars,_ in items}
    venues=set(a["venue"] for a,b,f in items)
    anchors=_decision_calendar_dates(policy,venues)
    horizon=policy["schedule"]["holding_return_intervals"]
    k=policy["portfolio"]["selected_instruments"]
    params=policy["costs"]
    folds=[];declined=[]
    last_exit=None
    for t in anchors:
        if t>=manifest["as_of"]:
            declined.append({"decision_date":t,"reason":"BEYOND_AVAILABLE_CUTOFF"})
            continue
        if last_exit is not None and t<=last_exit:
            declined.append({"decision_date":t,"reason":"OVERLAPPING_HOLDING_INTERVAL"})
            continue
        candidates=[]
        for uid,(asset,history) in universe.items():
            if history is not None:
                eligible=_candidate(asset,history,t,settings)
                if eligible is not None:
                    candidates.append(eligible)
        if len(candidates)<max(3,k+1):
            declined.append({"decision_date":t,"reason":"TOO_FEW_VERIFIED_AS_OF_ELIGIBLE"})
            continue
        candidates=sorted(candidates,key=lambda row:(-row["score"],row["id"]))
        # Outcomes are accessed only after scoring and the full eligible list
        # is frozen. Missing delisted paths invalidates the entire fold.
        per_id={}
        for item in candidates:
            outcome=_outcome(item,universe[item["id"]][1],t,horizon,
                             params,len(candidates))
            if outcome is None:
                declined.append({"decision_date":t,
                    "reason":"MISSING_OR_NONCONSECUTIVE_POST_SELECTION_OUTCOME"})
                break
            per_id[item["id"]]=outcome
        else:
            # All K-way candidate trade costs are computed exactly once,
            # BEFORE the random generator tests any competing portfolios.
            by_k={}
            for candidate in candidates:
                by_k[candidate["id"]]=_outcome(
                    candidate,universe[candidate["id"]][1],t,horizon,
                    params,k)
            selected_ids=[c["id"] for c in candidates[:k]]
            selected=mean(by_k[uid]["net"] for uid in selected_ids)
            drawdown=_drawdown([by_k[uid]["curve"] for uid in selected_ids])
            # Different minimum-fee burden for an N-leg equal-universe buy:
            # this is shown transparently, not treated as a cost-matched control.
            equal_universe=mean(per_id[c["id"]]["net"] for c in candidates)
            ic=_spearman([c["score"] for c in candidates],
                         [per_id[c["id"]]["gross"] for c in candidates])
            med=median(per_id[c["id"]]["gross"] for c in candidates)
            beats=mean(per_id[c["id"]]["gross"]>med for c in candidates[:k])
            exit_date=max(per_id[uid]["exit_date"] for uid in per_id)
            last_exit=exit_date
            folds.append({
                "decision_date":t,"entry_next_session":True,
                "exit_date_latest":exit_date,
                "eligible_instruments":len(candidates),
                "selected_ids":selected_ids,
                "selected_net_return":round(selected,8),
                "equal_universe_net_return":round(equal_universe,8),
                "excess_vs_universe":round(selected-equal_universe,8),
                "excess_vs_cash":round(selected,8),
                "selected_max_drawdown":round(drawdown,8),
                "selection_above_universe_median_rate":round(beats,6),
                "rank_information_coefficient":round(ic,8) if ic is not None else None,
                # Retain only rounded *aggregate* candidate outcomes, not
                # original prices. Raw instrument price data never exported.
                "_candidates":candidates,"_net_by_k":{uid:z["net"] for uid,z in by_k.items()},
            })
    random_count=policy["portfolio"]["random_portfolios"]
    rng=random.Random(policy["portfolio"]["random_seed"])
    random_means=[]
    def recompute_random(fold,ids):
        # Compare identical trade counts, per-leg capital, fees and FX,
        # without re-reading prices for each of 10,000 random experiments.
        return mean(fold["_net_by_k"][uid] for uid in ids)
    if folds:
        for _ in range(random_count):
            random_means.append(mean(
                recompute_random(fold,rng.sample(
                    [c["id"] for c in fold["_candidates"]],k))
                for fold in folds
            ))
    observed=mean(f["selected_net_return"] for f in folds) if folds else None
    excess=mean(f["excess_vs_universe"] for f in folds) if folds else None
    average_ic=(mean(f["rank_information_coefficient"] for f in folds
                     if f["rank_information_coefficient"] is not None)
                if any(f["rank_information_coefficient"] is not None for f in folds)
                else None)
    bs=random.Random(policy["statistics"]["bootstrap_seed"])
    count=policy["statistics"]["bootstrap_resamples"]
    bootstrap_excess=[];bootstrap_ic=[]
    if len(folds)>=2:
        for _ in range(count):
            sample=[bs.choice(folds) for j in folds]
            bootstrap_excess.append(mean(f["excess_vs_universe"] for f in sample))
            values=[f["rank_information_coefficient"] for f in sample
                    if f["rank_information_coefficient"] is not None]
            if values:
                bootstrap_ic.append(mean(values))
    excess_ci=_ci(bootstrap_excess)
    ic_ci=_ci(bootstrap_ic)
    percentile=(sum(x<observed for x in random_means)/len(random_means)
                if random_means else None)
    eligible_power=(len(folds)>=policy["cohort"]["minimum_independent_folds_for_predictive_evidence"]
                    and all(f["eligible_instruments"]>=policy["cohort"]["minimum_instruments_for_predictive_evidence"]
                            for f in folds))
    has_stat_edge=(eligible_power and ic_ci and excess_ci and
                   ic_ci[0]>0 and excess_ci[0]>0 and percentile>=.90)
    state=("SYNTHETIC_NOT_MARKET_EVIDENCE" if synthetic else
           "RETROSPECTIVE_SOURCE_UNVERIFIED_NOT_PREDICTIVE_EVIDENCE")
    results=[]
    for fold in folds:
        results.append({k:v for k,v in fold.items() if not k.startswith("_")})
    return {
        "schema_version":VERSION,
        "protocol_sha256":policy_hash,
        "bundle_manifest_sha256":hashlib.sha256(
            (Path(bundle)/"manifest.json").read_bytes()).hexdigest(),
        "as_of":manifest["as_of"],"dataset_mode":manifest["mode"],
        "status":state,
        "selected_strategy":"TOP_2_BY_FROZEN_BLOCK_B_MARKET_SCORE",
        "cohort_at_time_t_only":True,"future_for_selection":False,
        "tax_net_returns_verified":False,
        "source_rights_and_historical_issuer_universe_verified":False,
        "folds_evaluable":len(results),"folds_rejected":declined,
        "folds":results,
        "mean_selected_net_return":round(observed,8) if observed is not None else None,
        "mean_excess_vs_equal_universe":round(excess,8) if excess is not None else None,
        "mean_IC_spearman":round(average_ic,8) if average_ic is not None else None,
        "IC_95pct_bootstrap_CI":ic_ci,
        "excess_95pct_bootstrap_CI":excess_ci,
        "random_portfolio_percentile":round(percentile,6) if percentile is not None else None,
        "random_portfolio_trials":len(random_means),
        "sufficient_independent_statistical_power":eligible_power,
        "statistical_edge_screening_passed":bool(has_stat_edge),
        "predictive_edge_certified":False,
        "trade_ready":False,
        "caveats":[
            "Historical replay uses later downloaded vendor adjusted history, not a genuine contemporary vintage.",
            "Survivorship and point-in-time index membership/exchange identity are not established.",
            "2026-exchange calendars only; later historical periods need independent official calendar extension.",
            "30 exchange-session return intervals follow next-day EOD entry proxy, not executable fills.",
            "Commissions and FX are generic stress assumptions, not authenticated broker execution.",
            "No tax applied; user-specific Italian 2026 loss netting must be validated privately by ISIN.",
            "Random and equal-universe comparators assume candidate source completeness; missing delistings may bias.",
            "CI includes no regime/stationarity guarantee; a positive historical result cannot certify a future edge.",
        ],
    }


def write_backtest(report,output,*,repo_root):
    out=Path(output).resolve()
    root=Path(repo_root).resolve()
    if (not out.is_relative_to(root/"data/private")
            or out.exists() or not out.parent.is_dir()):
        raise ValueError("Historical validation output must be a NEW private file under data/private")
    payload=json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\n"
    out.write_text(payload,encoding="utf-8")
    return out

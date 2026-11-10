"""V2 2022–2026 pre-registered historical research replay.

Distinct from immutable V1 and 2026-only tax calendars.
Source, vintage, delisting and rights remain independent gate requirements.
No network, no trading and no claim of predictive capacity.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean,median

from .research_bundle import load_bundle
from .research_screen import WEIGHTS,_score_indicators,_market_score
from .research_historical_validation import (
    _prereview_source_gate,_adjusted_eur_prices,_net_trade,
    _drawdown,_spearman,_ci,
)
from .validated_multiyear_calendar import (
    session_historical,previous_common_session,subsequent_sessions,
)

PROTOCOL=Path(__file__).resolve().parents[2]/"config/backtest/v3_2022_2026_v2_preregistered.json"
VERSION="HISTORICAL_V2_RESEARCH_NOT_PREDICTIVE_CERTIFICATION"


def read_protocol():
    raw=PROTOCOL.read_bytes()
    v=json.loads(raw)
    if (v.get("schema_version")!="v3-v2-2022-2026-registered-protocol"
            or v.get("registered_on")!="2026-11-10"
            or v.get("scoring_weights")!=WEIGHTS
            or v.get("entry_lag_exchange_sessions")!=1
            or v.get("holding_return_intervals")!=30
            or v.get("selected_n")!=2
            or v.get("calendar_version")!="4.13.1"):
        raise ValueError("Historical v2 protocol changed or contradicts frozen B ranking")
    return v,hashlib.sha256(raw).hexdigest()


def _anchors(policy,venues):
    end=date.fromisoformat(policy["as_of_last"])
    day=date.fromisoformat(policy["as_of_first"])
    out=[]
    while day<=end:
        prior=previous_common_session(day,venues)
        if not out or prior>out[-1]:
            out.append(prior)
        day+=timedelta(days=policy["decision_step_calendar_days"])
    return out


def _consecutive(rows,venue):
    if len(rows)<61:return False
    tail=rows[-61:]
    try:
        start=date.fromisoformat(tail[0][0])
        end=date.fromisoformat(tail[-1][0])
        expected=[(start+timedelta(days=i)).isoformat()
                  for i in range((end-start).days+1)
                  if session_historical(start+timedelta(days=i),venue)]
    except ValueError:
        return False
    if expected!=[a[0] for a in tail]:
        return False
    return all(abs(tail[i][1]/tail[i-1][1]-1)<Decimal(".15")
               for i in range(1,len(tail)))


def _candidate(asset,series,as_of):
    if (asset.get("asset_type") not in ("EQUITY","ETF_UCITS","ETC","ETN")
            or asset.get("oil_exposure")!="none"
            or not asset.get("sector")
            or asset.get("currency") not in ("EUR","USD")):
        return None
    old=[x for x in series if x[0]<=as_of][-61:]
    if (len(old)!=61 or old[-1][0]!=as_of
            or not _consecutive(old,asset["venue"])):
        return None
    score,parts=_market_score(_score_indicators(old))
    return {"id":asset["id"],"score":score,"venue":asset["venue"],
            "currency":asset["currency"]}


def _post_path(series,as_of,venue,holding):
    try:
        needed=subsequent_sessions(date.fromisoformat(as_of),venue,holding+1)
    except ValueError:return None
    lookup={date.fromisoformat(r[0]):r for r in series if r[0]>as_of}
    if any(day not in lookup for day in needed):return None
    bars=[lookup[day] for day in needed]
    if any(abs(bars[i][1]/bars[i-1][1]-1)>=Decimal(".15")
           for i in range(1,len(bars))):
        return None
    return bars


def validate_v2(bundle):
    p,digest=read_protocol()
    m,items,fx,events=load_bundle(Path(bundle))
    synthetic=_prereview_source_gate(m,items)
    if events:raise ValueError("Un-vintaged event/fundamental file blocks V2")
    if not 3<=len(items)<=500:raise ValueError("V2 requires 3–500 explicit instruments")
    ids=[a["id"] for a,b,f in items]
    if len(set(ids))!=len(ids):raise ValueError("Duplicate V2 instrument ID")
    venues=sorted({a["venue"] for a,b,f in items})
    if any(v not in p["venues"] for v in venues):
        raise ValueError("Unsupported V2 venue")
    originals={}
    for a,b,f in items:
        if f is not None:
            # Without fact-level as-filed vintage, do not let future corporate
            # facts bleed into historical feature scores.
            raise ValueError("Contemporaneous annual report vintage not certified")
        originals[a["id"]]=(a,_adjusted_eur_prices(a,b,fx))
    positions=p["selected_n"]
    money=p["notional_eur"]
    fees=dict(
        fee_bps=p["commission_rate_each_side"],
        min_fee=p["min_commission_eur_each_side"],
        fx_bps=p["fx_fee_each_side"],
    )
    folds=[]
    rejected=[]
    last_exit=None
    for day in _anchors(p,venues):
        cutoff=day.isoformat()
        if cutoff>=m["as_of"]:
            rejected.append({"as_of":cutoff,"reason":"AFTER_OR_AT_BUNDLE_AS_OF"});continue
        if last_exit and day<=last_exit:
            rejected.append({"as_of":cutoff,"reason":"OVERLAPPING_HOLDING"});continue
        eligible=[]
        for uid,(a,rows) in originals.items():
            if rows is not None:
                c=_candidate(a,rows,cutoff)
                if c:eligible.append(c)
        if len(eligible)<3:
            rejected.append({"as_of":cutoff,"reason":"INSUFFICIENT_HISTORY"});continue
        eligible.sort(key=lambda v:(-v["score"],v["id"]))
        # Reconstruct outcomes only *after* freezing score ranking and
        # full eligible cohort. A single missing/delisted path invalidates
        # fold rather than introducing survivor-only optimistic bias.
        outcomes={}
        for c in eligible:
            a,rows=originals[c["id"]]
            path=_post_path(rows,cutoff,c["venue"],p["holding_return_intervals"])
            if path is None:
                rejected.append({"as_of":cutoff,"reason":"MISSING_POST_T_PATH_NO_SURVIVOR_FILTER"})
                break
            portfolio_result,_curve,gross=_net_trade(
                path,notional=money/positions,usd=c["currency"]=="USD",**fees)
            # Full-universe benchmark has its actual per-leg fee floor,
            # different from two-asset strategy.
            universe_result,_,_= _net_trade(
                path,notional=money/len(eligible),usd=c["currency"]=="USD",**fees)
            outcomes[c["id"]]={"top_costed":portfolio_result,
                               "universe_costed":universe_result,
                               "gross":gross,
                               "curve":_curve,
                               "exit":path[-1][0]}
        else:
            top=eligible[:positions]
            low=eligible[-positions:]
            mean_net=mean(outcomes[x["id"]]["top_costed"] for x in top)
            equal=mean(x["universe_costed"] for x in outcomes.values())
            bottom=mean(outcomes[x["id"]]["top_costed"] for x in low)
            fold={
                "as_of":cutoff,
                "selected_ids":[x["id"] for x in top],
                "reversed_bottom_ids":[x["id"] for x in low],
                "eligible_count":len(eligible),
                "top2_net":round(mean_net,8),
                "bottom2_net":round(bottom,8),
                "top2_minus_bottom2":round(mean_net-bottom,8),
                "universe_equal_net":round(equal,8),
                "top2_excess_equal":round(mean_net-equal,8),
                "spearman_ic":_spearman([c["score"] for c in eligible],
                                        [outcomes[c["id"]]["gross"] for c in eligible]),
                "worst_drawdown":round(_drawdown(
                   [outcomes[x["id"]]["curve"] for x in top]),8),
                "exit_date":max(x["exit"] for x in outcomes.values()),
            }
            fold["_random_k_returns"]=[outcomes[x["id"]]["top_costed"] for x in eligible]
            folds.append(fold)
            last_exit=date.fromisoformat(fold["exit_date"])
    rng=random.Random(p["random_seed"])
    random_avgs=[]
    if folds:
        for _ in range(p["random_portfolios_per_backtest"]):
            random_avgs.append(mean(
                mean(rng.sample(f["_random_k_returns"],positions)) for f in folds))
    observed=mean(f["top2_net"] for f in folds) if folds else None
    percentile=(sum(r<observed for r in random_avgs)/len(random_avgs)
                if random_avgs else None)
    boot=random.Random(p["bootstrap_seed"])
    excess_ci=None;ic_ci=None
    if len(folds)>=2:
        draws=[];ics=[]
        for _ in range(p["fold_bootstrap_count"]):
            picked=[boot.choice(folds) for _ in folds]
            draws.append(mean(x["top2_excess_equal"] for x in picked))
            sample_ic=[x["spearman_ic"] for x in picked if x["spearman_ic"] is not None]
            if sample_ic:ics.append(mean(sample_ic))
        excess_ci=_ci(draws)
        ic_ci=_ci(ics)
    min_eligible=min((x["eligible_count"] for x in folds),default=0)
    power=len(folds)>=p["min_nonoverlapping_folds_for_gate"] and min_eligible>=p["min_eligible_assets_for_statistical_gate"]
    ranking_inverted=bool(folds and mean(f["top2_minus_bottom2"] for f in folds)>0)
    # Null type-I control has not been executed independently, so even
    # apparently strong historic results may NEVER trigger approval.
    clean=[{k:v for k,v in x.items() if not k.startswith("_")} for x in folds]
    return {
        "schema_version":VERSION,"protocol_sha256":digest,
        "bundle_manifest_sha256":hashlib.sha256((Path(bundle)/"manifest.json").read_bytes()).hexdigest(),
        "mode":m["mode"],"as_of":m["as_of"],
        "result_type":"SYNTHETIC_SOFTWARE_DEMONSTRATION" if synthetic else "AUTHENTIC_ORIGINAL_BUT_VINTAGE_AND_RIGHTS_UNVERIFIED",
        "folds":clean,"folds_count":len(clean),"folds_rejected":rejected,
        "mean_top2_net":round(observed,8) if observed is not None else None,
        "mean_top2_minus_bottom2":round(mean(f["top2_minus_bottom2"] for f in folds),8) if folds else None,
        "mean_rank_ic":round(mean(f["spearman_ic"] for f in folds if f["spearman_ic"] is not None),8) if any(f["spearman_ic"] is not None for f in folds) else None,
        "top2_random_percentile":round(percentile,6) if percentile is not None else None,
        "excess_bootstrap_ci":excess_ci,"ic_bootstrap_ci":ic_ci,
        "reversed_top_bottom_positive":ranking_inverted,
        "enough_independent_folds_and_assets":power,
        "null_type1_calibrated":False,
        "source_vintages_verified":False,"source_usage_rights_verified":False,
        "tax_net_returns_verified":False,
        "predictive_edge_certified":False,"trade_ready":False,
        "notional_scenario_only":True,
        "caveats":["Retrospective only: survivorship and issuer point-in-time availability not proven",
                   "Use historical close as unexecutable next-session fill proxy",
                   "Taxes, spreads, slippage and broker-specific fees unverified",
                   "Null false positive control must be run before evidence gate",
                   "Real market source/adjustments require independent legal and corporate-action review"],
    }

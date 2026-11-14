"""Ex-ante 1/3/6 CALENDAR MONTHS time-travel research replay (NO trading).

A separate registered experiment: never modifies/repurposes the frozen
V1/V2/V3 30-session protocol. The original Block B _eligible scorer uses
ONLY 61 prior exchange closes available at T. All outcome, cash P&L and
spread/commission calculations happen after freezing the as-of cohort.

Market-price vintage, CA/delist, rights and genuine alpha are unverified.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from functools import lru_cache
from decimal import Decimal
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean

from .historical_calendar_v2 import dates_v2
from .research_bundle import load_bundle,SYNTHETIC,EXTERNAL
from .research_historical_validation import _net_trade,_spearman,_adjusted_eur_prices,_ci
from .research_historical_validation_v2 import (
    _eligible,preregistered_anchors,SUPPORTED_PROVIDERS,ELIGIBLE_BASIS,MAX_ASSETS,
)
from .research_historical_validation_v3 import v3_protocol
from .research_slippage_v3 import net_at_bps
from .research_screen import WEIGHTS

PROTOCOL=(Path(__file__).resolve().parents[2]/
    "config/backtest/v3_asof_multihorizon_1_3_6m_protocol_2026-11-11.json")
FROZEN_GIT_BLOB="05a63cc0906c782b2909031b0bb1fe0d09ad76e4"
VERSION="V3_AS_OF_1_3_6_CALENDAR_MONTH_REPLAY_V1"
SUPPORTED=(1,3,6)
MAX_HISTORY=2000


def replay_protocol():
    raw=PROTOCOL.read_bytes()
    blob=b"blob "+str(len(raw)).encode()+b"\x00"+raw
    if hashlib.sha1(blob).hexdigest()!=FROZEN_GIT_BLOB:
        raise ValueError("Historical 1/3/6-month preregistration was changed")
    p=json.loads(raw)
    if (p.get("schema_version")!="v3-asof-calendar-multihorizon-replay-v1"
            or p["registered_on"]!="2026-11-11"
            or p["schedule"]["horizons_calendar_months"]!=[1,3,6]
            or p["schedule"]["anchor_source"]!=
                "EXACT_FROZEN_V3_PREREGISTERED_49_DAY_COMMON_EXCHANGE_DATE_ANCHORS"
            or p["frozen_model"]["portfolio_k"]!=2
            or p["frozen_model"]["minimum_independent_folds_for_predictive_evidence"]!=30
            or p["comparators"]["primary"]!=
                "EXACT_EXPECTED_UNIFORM_RANDOM_K_AS_OF_INSTRUMENTS_SAME_LEG_FEES"
            or p["comparators"]["random_K_portfolios"]!=10000
            or p["comparators"]["per_horizon_bootstrap_repetitions"]!=10000
            or p["costs"]["slippage_sensitivity_bps_each_side"]!=[0,10,25,50]
            or p["replay_only"] is not True or p["trade_ready"] is not False
            or p["failure_policy"]["no_lookahead"]!=
                "RANKING_AS_OF_T_AND_CALENDAR_RESERVATIONS_BEFORE_CONSULTING_ANY_OUTCOME"):
        raise ValueError("Historical 1/3/6 month protocol control invalid")
    v3,_=v3_protocol()
    if p["costs"]["notional_eur"]!=v3["costs"]["notional_eur"]:
        raise ValueError("Cannot rebase historical notional after score review")
    return p,hashlib.sha256(raw).hexdigest()


def add_calendar_months(d,months):
    """Month anniversaries clamp 29/30/31 to last day (not 21/63/126 bars)."""
    if not isinstance(d,date) or months not in SUPPORTED:
        raise ValueError("Expected 1/3/6 calendar months, date")
    year=d.year+(d.month-1+months)//12
    month=(d.month-1+months)%12+1
    return date(year,month,min(d.day,calendar.monthrange(year,month)[1]))


@lru_cache(maxsize=2048)
def _first_session_on_or_after(d,venue):
    if d>date(2026,12,31):
        raise ValueError("Horizon goes beyond the frozen exchange calendar")
    days=dates_v2(d,date(2026,12,31),venue)
    if not days:
        raise ValueError("No permitted venue session before end of 2026")
    return days[0]


@lru_cache(maxsize=4096)
def _venue_dates(t,venue,months):
    entry=_first_session_on_or_after(date.fromisoformat(t)+timedelta(days=1),venue)
    target=add_calendar_months(date.fromisoformat(entry),months)
    end=_first_session_on_or_after(target,venue)
    return entry,end


def _future_member(member,history,entry,end,policy,k):
    """Every expected venue session required, no dropping a losing member."""
    expected=dates_v2(date.fromisoformat(entry),
                      date.fromisoformat(end),member["venue"])
    observed=[x for x in history if entry<=x[0]<=end]
    if (not expected or len(observed)!=len(expected)
            or tuple(v[0] for v in observed)!=expected):
        return None,"MISSING_ONE_OR_MORE_ORIGINAL_MARKET_SESSIONS"
    if any(abs(observed[i][1]/observed[i-1][1]-1)>=Decimal(".15")
           for i in range(1,len(observed))):
        return None,"GE15_PERCENT_REAL_CRASH_OR_CORPORATE_ACTION_UNRESOLVED"
    c=policy["costs"]
    notional=c["notional_eur"]/k
    net,curve,gross=_net_trade(observed,notional=notional,
        fee_bps=c["commission_fraction_each_side"],
        min_fee=c["minimum_commission_eur_each_side"],
        fx_bps=c["usd_fx_fraction_each_side"],
        usd=member["currency"]=="USD")
    return {"net":net,"gross":gross,"entry":entry,"exit":end},None


def _bootstrap(folds,seed,reps):
    if len(folds)<2:
        return None,None
    rng=random.Random(seed)
    e=[];ic=[]
    for _ in range(reps):
        sample=rng.choices(folds,k=len(folds))
        e.append(mean(x["same_K_excess_net"] for x in sample))
        vals=[x["ic"] for x in sample if x["ic"] is not None]
        if vals:
            ic.append(mean(vals))
    return _ci(e),_ci(ic)


def _one_horizon(months,anchors,universe,as_of,policy,settings):
    k=policy["frozen_model"]["portfolio_k"]
    cash=policy["costs"]["notional_eur"]
    audit=[]
    completed=[]
    previous_ex_ante_exit=None
    for t in anchors:
        if t>=as_of:
            audit.append({"decision_date":t,"state":"NOT_YET_IN_SOURCE_AS_OF",
                          "as_of_eligible":None,"planned_latest_exit":None})
            continue
        if previous_ex_ante_exit and t<=previous_ex_ante_exit:
            audit.append({"decision_date":t,"state":"EX_ANTE_OVERLAPPING_HOLDOUT",
                          "as_of_eligible":None,"planned_latest_exit":None})
            continue
        eligible=[]
        for asset,history in universe.values():
            x=_eligible(asset,history,t,settings)
            if x is not None:
                eligible.append(x)
        if len(eligible)<max(3,k+1):
            audit.append({"decision_date":t,"state":"INSUFFICIENT_AS_OF_HISTORY",
                          "as_of_eligible":len(eligible),"planned_latest_exit":None})
            continue
        ranked=sorted(eligible,key=lambda x:(-x["score"],x["id"]))
        selected=ranked[:k]
        bottom=ranked[-k:]
        dates_by_id={r["id"]:_venue_dates(t,r["venue"],months) for r in ranked}
        exit_date=max(v[1] for v in dates_by_id.values())
        previous_ex_ante_exit=exit_date
        cohort_ids=[x["id"] for x in ranked]
        digest=hashlib.sha256(json.dumps(cohort_ids,ensure_ascii=False,
                separators=(",",":")).encode()).hexdigest()
        row={
            "decision_date":t,"as_of_eligible":len(ranked),
            "as_of_eligible_ids_in_score_order":cohort_ids,
            "as_of_cohort_sha256":digest,
            "selected_ids":[x["id"] for x in selected],
            "bottom_ids":[x["id"] for x in bottom],
            "entry_exit_by_id":{uid:{"entry":e,"exit":d}
                                 for uid,(e,d) in dates_by_id.items()},
            "planned_latest_exit":exit_date,
        }
        if exit_date>as_of:
            row["state"]="NOT_YET_MATURED_AS_OF_CUTOFF"
            audit.append(row)
            continue
        observed={}
        reasons={}
        for r in ranked:
            entry,exit_=dates_by_id[r["id"]]
            value,reason=_future_member(r,universe[r["id"]][1],
                                        entry,exit_,policy,k)
            if reason is not None:
                reasons[r["id"]]=reason
            else:
                observed[r["id"]]=value
        if reasons:
            row["state"]="MATURED_UNRESOLVED_DO_NOT_DISCARD_MEMBERS"
            row["unresolved_by_id"]=reasons
            audit.append(row)
            continue
        row["state"]="MATURED_COMPLETE"
        row["unresolved_by_id"]={}
        audit.append(row)
        selected_ret=mean(observed[x["id"]]["net"] for x in selected)
        bottom_ret=mean(observed[x["id"]]["net"] for x in bottom)
        expected_ret=mean(x["net"] for x in observed.values())
        ic=_spearman(
            [r["score"] for r in ranked],
            [observed[r["id"]]["gross"] for r in ranked])
        spreads=[]
        for bps in policy["costs"]["slippage_sensitivity_bps_each_side"]:
            by_name={
                x["id"]:net_at_bps(observed[x["id"]]["gross"],x["currency"],
                                  policy["costs"],cash/k,bps)
                for x in ranked
            }
            selected_s=mean(by_name[x["id"]] for x in selected)
            random_s=mean(by_name.values())
            spreads.append({"bps_each_side":bps,
                            "selected_net":round(selected_s,8),
                            "uniform_random_K_expected_net":round(random_s,8),
                            "same_K_excess_net":round(selected_s-random_s,8)})
        if (abs(spreads[0]["selected_net"]-selected_ret)>2.1e-8
                or abs(spreads[0]["uniform_random_K_expected_net"]-
                       expected_ret)>2.1e-8):
            raise ValueError("Zero spread 1/3/6 replay contradicts frozen costs")
        completed.append({
            "decision_date":t,"planned_latest_exit":exit_date,
            "holding_calendar_months":months,
            "as_of_eligible":len(ranked),
            "as_of_cohort_sha256":digest,
            "selected_ids":[x["id"] for x in selected],
            "bottom_ids":[x["id"] for x in bottom],
            "selected_entry_exit":[{"id":x["id"],
                "entry_date":dates_by_id[x["id"]][0],
                "exit_date":dates_by_id[x["id"]][1]} for x in selected],
            "selected_net":round(selected_ret,8),
            "selected_cash_pnl_eur":round(cash*selected_ret,2),
            "bottom_net":round(bottom_ret,8),
            "same_K_uniform_random_expected_net":round(expected_ret,8),
            "same_K_excess_net":round(selected_ret-expected_ret,8),
            "ic":round(ic,8) if ic is not None else None,
            "spread_sensitivity_DESCRIPTIVE_ONLY":spreads,
            "_net_by_id":{x["id"]:observed[x["id"]]["net"] for x in ranked},
        })
    rng=random.Random(policy["comparators"]["random_seed"]+months)
    sampled=[]
    if completed:
        for _ in range(policy["comparators"]["random_K_portfolios"]):
            sampled.append(mean(mean(f["_net_by_id"][x] for x in
                rng.sample(tuple(f["_net_by_id"]),k)) for f in completed))
    selected_mean=mean(f["selected_net"] for f in completed) if completed else None
    percentile=round(sum(x<selected_mean for x in sampled)/len(sampled),6) if sampled else None
    primary_ci,ic_ci=_bootstrap(completed,
        policy["comparators"]["bootstrap_seed"]+months,
        policy["comparators"]["per_horizon_bootstrap_repetitions"])
    for f in completed:
        del f["_net_by_id"]
    counts={
        "matured_complete":sum(x["state"]=="MATURED_COMPLETE" for x in audit),
        "matured_unresolved":sum(x["state"]=="MATURED_UNRESOLVED_DO_NOT_DISCARD_MEMBERS" for x in audit),
        "future_pending":sum(x["state"]=="NOT_YET_MATURED_AS_OF_CUTOFF" for x in audit),
        "overlap_reservations":sum(x["state"]=="EX_ANTE_OVERLAPPING_HOLDOUT" for x in audit),
        "as_of_ineligible":sum(x["state"]=="INSUFFICIENT_AS_OF_HISTORY" for x in audit),
    }
    adequate=bool(counts["matured_complete"]>=
                  policy["frozen_model"]["minimum_independent_folds_for_predictive_evidence"]
                  and counts["matured_unresolved"]==0
                  and all(f["as_of_eligible"]>=
                          policy["frozen_model"]["minimum_as_of_eligible_members"]
                          for f in completed))
    return {
        "calendar_months":months,
        "as_of_anchor_audit":audit,
        "count":counts,
        "selection_lookahead_denied":True,
        "overlapping_holdouts_excluded_from_independent_count":True,
        "folds":completed,
        "mean_selected_net":round(selected_mean,8) if selected_mean is not None else None,
        "mean_selected_cash_pnl_eur":round(cash*selected_mean,2) if selected_mean is not None else None,
        "mean_uniform_random_K_expected_net":round(
            mean(f["same_K_uniform_random_expected_net"] for f in completed),8)
            if completed else None,
        "mean_same_K_excess_net":round(
            mean(f["same_K_excess_net"] for f in completed),8) if completed else None,
        "primary_paired_fold_bootstrap_CI_95":primary_ci,
        "rank_ic_bootstrap_CI_95":ic_ci,
        "random_K_portfolio_trials":len(sampled),
        "selected_random_K_percentile":percentile,
        "minimum_independent_fold_and_complete_data_gate":adequate,
        "confirmatory_alpha_validation":False,
        "trade_ready":False,
    }


def evaluate_historical_1_3_6(bundle,*,settings=None):
    p,hash_=replay_protocol()
    root=Path(bundle)
    manifest,items,fx,events=load_bundle(root)
    if (manifest["mode"] not in (SYNTHETIC,EXTERNAL)
            or events or not 3<=len(items)<=MAX_ASSETS):
        raise ValueError("Historical 1/3/6 requires a bounded original bundle")
    if manifest["mode"]==EXTERNAL:
        for asset,_,_ in items:
            source=asset["prices"]
            if (source.get("provider") not in SUPPORTED_PROVIDERS
                    or source.get("price_basis") not in ELIGIBLE_BASIS):
                raise ValueError("Only operator-reviewed original FWB/Euronext sources")
    universe={}
    for asset,bars,_ in items:
        adjusted=_adjusted_eur_prices(asset,bars,fx)
        if adjusted is None or len(adjusted)>MAX_HISTORY:
            raise ValueError("Missing EUR FX or unsupported price data length")
        if asset["id"] in universe:
            raise ValueError("Duplicate original asset research identity")
        universe[asset["id"]]=(asset,adjusted)
    settings=settings or {"exclude_primary_oil":True,
        "exclude_additional_gold":True,"avoid_duplicate_eurostoxx50":True}
    v3,_=v3_protocol()
    anchors=preregistered_anchors(
        [asset["venue"] for asset,_,_ in items],v3)
    outcomes=[_one_horizon(m,anchors,universe,manifest["as_of"],p,settings)
              for m in SUPPORTED]
    return {
        "schema_version":VERSION,
        "original_registered_protocol_sha256":hash_,
        "registered_protocol_git_blob":FROZEN_GIT_BLOB,
        "input_manifest_sha256":hashlib.sha256(
            (root/"manifest.json").read_bytes()).hexdigest(),
        "data_mode":manifest["mode"],
        "as_of":manifest["as_of"],
        "months_definition":"CALENDAR_MONTHS_ENTRY_TO_FIRST_SESSION_ON_OR_AFTER_ANNIVERSARY",
        "selection_model":"ORIGINAL_UNCHANGED_B_V3_61_PRIOR_SESSIONS",
        "as_of_anchor_count":len(anchors),
        "independent_horizon_results":outcomes,
        "horizons_share_selection_and_are_statistically_correlated":True,
        "benchmark":"EXACT_SAME_K_UNIFORM_RANDOM_AS_OF_UNIVERSE_SAME_FEES",
        "actual_market_index_benchmark_attested":False,
        "original_market_prices_adjustments_independently_verified":False,
        "point_in_time_delisted_and_failed_membership_verified":False,
        "data_reuse_rights_independently_verified":False,
        "broker_tax_and_fiscal_by_ISIN_verified":False,
        "retrospective_report_is_a_real_prospective_holdout":False,
        "predictive_edge_certified":False,
        "trade_ready":False,
        "limitations":[
            "Results are retrospective replays, never unseen prospective validation.",
            "No original provider/right/CA/PIT historical security identities verified.",
            "The same frozen selections at 1/3/6m create correlated outcomes.",
            "Non-overlapping 6-month windows in 2021–2026 cannot reach 30 independent folds.",
            "Any unresolved matured member fails the statistical gate; no dividend/delist imputation.",
            "EOD close-to-close simulation does not establish executable next-day quotes.",
            "No per-ISIN Italian fiscal offset nor actual bank fees/tax wallet certified.",
        ],
    }

"""Actual-market-data, non-investment, secondary-source research pilot.

CONSTRAINTS: US stock prices from today's S&P500 members only (survivorship
bias), source adjusted closes not corporate-action-verified, ISIN absent.
This is not the authorized B→A investable universe; no real portfolios or
stock recommendations are emitted. No original prices uploaded or persisted.
Input selection protocol was committed BEFORE inspecting subsequent returns.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import re
from datetime import date,timedelta
from decimal import Decimal,InvalidOperation
from pathlib import Path
from statistics import mean,median
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import URLError,HTTPError

from investresearch.historical_calendar_v2 import dates_v2
from investresearch.research_historical_validation_v2 import (
    v2_protocol,preregistered_anchors,_verified_61,_forward,_bootstrap
)
from investresearch.research_historical_validation import _spearman
from investresearch.research_screen import _score_indicators,_market_score
from investresearch.research_sources import parse_ecb

POLICY=Path(__file__).resolve().parents[1]/"config/backtest/v3_secondary_real_history_pilot_2026-11-10.json"
MAX_PRICE_BYTES=110_000_000
MAX_REF_BYTES=300_000
MAX_ECB_BYTES=12_000_000
MIN_ANCHORS_FOR_DESCRIPTIVE=3


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def _fetch(url,size):
    req=Request(url,headers={"User-Agent":"investment-research-2026/1.0 noncommercial-study",
                             "Accept":"text/csv,application/xml"})
    with build_opener(NoRedirect()).open(req,timeout=60) as res:
        content=res.read(size+1)
    if not content or len(content)>size:
        raise ValueError("Original research input missing or exceeds bounded source size")
    return content


def select_cohort(ref:bytes,policy:dict):
    fields=["ticker","name","sector","industry","headquarters","date_added","cik","founded"]
    rdr=csv.DictReader(io.StringIO(ref.decode("utf-8-sig")))
    if rdr.fieldnames!=fields:
        raise ValueError("Source current-constituent reference header changed")
    excluded_sector=set(policy["universe_definition"]["sector_exclude"])
    bad_words=tuple(policy["universe_definition"]["exclude_industry_words"])
    candidates={}
    for row in rdr:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Incomplete source membership reference")
        symbol=row["ticker"]
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}",symbol):
            raise ValueError("Unexpected ticker in current membership source")
        if symbol in candidates:
            raise ValueError("Duplicate source ticker")
        try:
            added=date.fromisoformat(row["date_added"])
        except ValueError:
            # Unknown listing vintage is *never* silently treated as early.
            continue
        if (added>date.fromisoformat(
                policy["universe_definition"]["require_index_date_added_on_or_before"])
                or row["sector"] in excluded_sector
                or any(w in row["industry"].lower() for w in bad_words)):
            continue
        candidates[symbol]=row
    target=policy["universe_definition"]["target_ticker_count"]
    seed=policy["universe_definition"]["seed"]
    if len(candidates)<target or target!=40:
        raise ValueError("Fixed research cohort cannot be formed from membership source")
    ordered=sorted(candidates,key=lambda ticker:hashlib.sha256(
        (seed+":"+ticker).encode()).hexdigest())
    return tuple(ordered[:target]),{
        "current_constituents_in_reference":len(candidates),
        "chosen_blind_instruments":target,
        "excluded_energy_sector":True,
        "membership_is_hindsight_current":True,
        "individual_oil_exposure_verified":False,
        "historical_index_membership_verified":False,
    }


def prepare_price_rows(data:bytes,selected:tuple[str,...],usd_per_eur:dict,cutoff:str):
    rdr=csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if rdr.fieldnames!=["date","ticker","open","high","low","close","adj_close","volume"]:
        raise ValueError("Real historical source schema drift")
    chosen=set(selected)
    out={s:[] for s in chosen}
    seen={s:set() for s in chosen}
    selected_raw_rows=0;missing_fx=0
    for rec in rdr:
        ticker=rec["ticker"]
        if ticker not in chosen:continue
        day=rec["date"]
        if day>cutoff:continue
        if day in seen[ticker]:
            raise ValueError("Duplicate original security/date input")
        seen[ticker].add(day)
        selected_raw_rows+=1
        # parse source values exactly; never replace missing original data.
        try:
            adj=Decimal(rec["adj_close"])
            close=Decimal(rec["close"])
            volume=Decimal(rec["volume"])
        except (InvalidOperation,TypeError):
            raise ValueError("Invalid original price/volume in selected source") from None
        if (not all(x.is_finite() for x in (adj,close,volume))
                or adj<=0 or close<=0 or volume<0):
            raise ValueError("Selected source price/volume nonfinite or nonpositive")
        fx=usd_per_eur.get(day)
        if fx is None:
            missing_fx+=1;continue
        # Liquidity on adjusted close must use an adjusted-volume proxy so
        # that turnover remains RAW_CLOSE*RAW_SHARES in EUR on each day.
        px_eur=adj/fx
        adjusted_volume=volume*close/adj
        out[ticker].append((day,px_eur,adjusted_volume))
    for ticker in out:
        out[ticker].sort(key=lambda x:x[0])
    return out,{
        "selected_original_price_rows":selected_raw_rows,
        "selected_us_sessions_without_same_day_ecb":missing_fx,
        "provider_corporate_actions_adjusted_only_by_claim":True,
        "usd_price_normalized_using_original_ecb_same_day":True,
        "contemporaneous_data_snapshots_authenticated":False,
    }


def evaluate_secondary_pilot(raw_prices:bytes,raw_ref:bytes,raw_ecb:bytes):
    policy=json.loads(POLICY.read_text())
    protocol,sha=v2_protocol()
    if policy["v2_protocol_git_blob"]!=protocol["release_gate"].get("protocol_git_blob",policy["v2_protocol_git_blob"]):
        raise ValueError("V2 protocol cannot be silently exchanged")
    source_sha=hashlib.sha256(raw_prices).hexdigest()
    if source_sha!=policy["source_price_fixed_sha256"]:
        raise ValueError("Original multi-year price source SHA changed: MUST preregister new data-vintage study")
    if len(raw_prices)>MAX_PRICE_BYTES or len(raw_ref)>MAX_REF_BYTES or len(raw_ecb)>MAX_ECB_BYTES:
        raise ValueError("Real original historical inputs exceeded bounded size")
    selected,cohort=select_cohort(raw_ref,policy)
    usd_per_eur={r["date"]:Decimal(r["usd_per_eur"]) for r in
                 parse_ecb(raw_ecb,date(2026,11,10))}
    data,quality=prepare_price_rows(raw_prices,selected,usd_per_eur,"2026-11-06")
    anchors=preregistered_anchors(["XNYS"],protocol)
    folds=[]
    rejected={}
    last_exit=None
    for T in anchors:
        if last_exit is not None and T<=last_exit:
            rejected["OVERLAPPING_EVAL_FOLD"]=rejected.get("OVERLAPPING_EVAL_FOLD",0)+1
            continue
        ranked=[]
        for ticker in selected:
            past=_verified_61(data[ticker],"XNYS",T)
            if past is None:
                ranked=[]
                rejected["MISSING_TRAINING_FX_OR_PRICE"]=rejected.get("MISSING_TRAINING_FX_OR_PRICE",0)+1
                break
            # Exactly unchanged Block B scoring functions. No issuer identity,
            # facts, sector or benchmark figures are fabricated.
            score,_=_market_score(_score_indicators(past))
            ranked.append({"id":ticker,"venue":"XNYS","currency":"USD","score":score})
        if len(ranked)!=len(selected):
            continue
        ranked.sort(key=lambda x:(-x["score"],x["id"]))
        results={}
        for row in ranked:
            future=_forward(row,data[row["id"]],T,protocol,policy["fee_simulation"]["notional_eur"]/2)
            if future is None:
                rejected["INCOMPLETE_HOLDOUT_NO_SURVIVOR_DROPS"]=rejected.get(
                    "INCOMPLETE_HOLDOUT_NO_SURVIVOR_DROPS",0)+1
                break
            results[row["id"]]=future
        if len(results)!=len(ranked):
            continue
        all_n=[]
        for row in ranked:
            future=_forward(row,data[row["id"]],T,protocol,
                    policy["fee_simulation"]["notional_eur"]/len(ranked))
            if future is None:
                raise ValueError("Real historical source changed within one fold")
            all_n.append(future["net"])
        top=ranked[:2];bottom=ranked[-2:]
        top_return=mean(results[x["id"]]["net"] for x in top)
        bottom_return=mean(results[x["id"]]["net"] for x in bottom)
        universe=mean(all_n)
        ic=_spearman([x["score"] for x in ranked],
                     [results[x["id"]]["gross"] for x in ranked])
        exit_date=max(q["exit_date"] for q in results.values())
        last_exit=exit_date
        folds.append({
            "date":T,
            "exit_date":exit_date,
            "eligible":len(ranked),
            "selected_net":round(top_return,8),
            "bottom_net":round(bottom_return,8),
            "universe_net":round(universe,8),
            "excess":round(top_return-universe,8),
            "ic":round(ic,8) if ic is not None else None,
            "_net_by_k":{x:results[x]["net"] for x in results},
        })
    rng=random.Random(policy["analysis"]["random_seed"])
    random_means=[]
    for _ in range(policy["analysis"]["random_portfolios"] if folds else 0):
        random_means.append(mean(mean(fold["_net_by_k"][x] for x in rng.sample(selected,2))
                                 for fold in folds))
    observed=mean(f["selected_net"] for f in folds) if folds else None
    percentile=(sum(x<observed for x in random_means)/len(random_means)) if folds else None
    excess_ci,ic_ci=_bootstrap(folds,protocol)
    for f in folds:
        del f["_net_by_k"]
    return {
        "schema_version":"REAL_S_P_500_SECONDARY_REPLAY_V2_UNCERTIFIED",
        "status":"ACTUAL_MARKET_OBSERVATIONS_RETROSPECTIVE_NON_INVESTABLE_RESEARCH_PILOT",
        "observed_price_source_sha256":source_sha,
        "current_membership_source_sha256":hashlib.sha256(raw_ref).hexdigest(),
        "original_ecb_xml_sha256":hashlib.sha256(raw_ecb).hexdigest(),
        "frozen_v2_protocol_sha256":sha,
        "blind_cohort_policy":"FIXED_SEED_HASH_CURRENT_MEMBERS_ADDED_BEFORE_2021",
        "planned_date_anchors":len(anchors),
        "evaluable_nonoverlapping_folds":len(folds),
        "excluded_folds_reasons":rejected,
        "source_cohort":cohort,
        "source_quality":quality,
        "folds":folds,
        "mean_selected_net":round(observed,8) if observed is not None else None,
        "mean_bottom_net":round(mean(f["bottom_net"] for f in folds),8) if folds else None,
        "mean_equal_universe_net":round(mean(f["universe_net"] for f in folds),8) if folds else None,
        "mean_excess_vs_40_stock_universe":round(mean(f["excess"] for f in folds),8) if folds else None,
        "mean_rank_ic":round(mean(f["ic"] for f in folds if f["ic"] is not None),8)
            if any(f["ic"] is not None for f in folds) else None,
        "top_two_minus_bottom_two":round(mean(f["selected_net"]-f["bottom_net"] for f in folds),8) if folds else None,
        "excess_95_ci":excess_ci,
        "ic_95_ci":ic_ci,
        "random_2_stock_portfolios":len(random_means),
        "rank_vs_random_percentile":round(percentile,6) if percentile is not None else None,
        "survivorship_bias":"SEVERE_CURRENT_2026_MEMBERS_BACKFILLED_TO_2021",
        "original_price_point_in_time_versioning":False,
        "original_source_adjustment_validated_independently":False,
        "currency_provenance":"ECB_REAL_ORIGINAL_SAME_DAY_REFERENCE_FX_NOT_EXECUTABLE",
        "instrument_tax_broker_usability":False,
        "user_specific_equity_or_oil_eligibility_verified":False,
        "model_predictive_edge_certified":False,
        "ready_for_real_money":False,
    }


def main():
    policy=json.loads(POLICY.read_text())
    p=_fetch(policy["source_price_csv"],MAX_PRICE_BYTES)
    # Ensure identical original market input BEFORE any analysis.
    if hashlib.sha256(p).hexdigest()!=policy["source_price_fixed_sha256"]:
        raise SystemExit("PREREGISTERED_ORIGINAL_MARKET_DATA_SHA_CHANGED; NO_RETROSPECTIVE_RESULTS")
    try:
        c=_fetch(policy["source_current_members_csv"],MAX_REF_BYTES)
        fx=_fetch(policy["source_fx"],MAX_ECB_BYTES)
        result=evaluate_secondary_pilot(p,c,fx)
    except (ValueError,HTTPError,URLError,OSError,TimeoutError) as exc:
        # Fixed allowlisted diagnostics only, never echo raw vendor price,
        # ticker, response body, credentials or a sensitive source path.
        allowed={
            "Original research input missing or exceeds bounded source size":"SOURCE_SIZE_OR_EMPTY",
            "Source current-constituent reference header changed":"COMPANY_REFERENCE_SCHEMA",
            "Fixed research cohort cannot be formed from membership source":"COHORT_MEMBERSHIP",
            "Original multi-year price source SHA changed: MUST preregister new data-vintage study":"PRICE_VINTAGE",
            "Real historical source schema drift":"PRICE_COLUMNS",
            "V2 input must be small bounded original or synthetic bundle without hindsight events":"UNIVERSE_MODE",
        }
        detail=allowed.get(str(exc),"INPUT_SOURCE_OR_CROSSMARKET_VALIDATION")
        print("REAL_PILOT_UNAVAILABLE_OR_BLOCKED",type(exc).__name__,detail)
        raise SystemExit(2) from None
    # Strictly descriptive aggregate output; raw original prices, tickers,
    # individual investment returns, personal holdings never published.
    print("REAL_2021_2026_RESEARCH_ONLY_SECONDARY_SOURCE_RETROSPECTIVE_RESULT")
    to_print={key:value for key,value in result.items() if key!="folds"}
    print(json.dumps(to_print,sort_keys=True))
    print("NO_INVESTMENT_ADVICE; SURVIVORSHIP_BIAS; NO_REAL_MONEY_VALIDATION")


if __name__=="__main__":
    main()

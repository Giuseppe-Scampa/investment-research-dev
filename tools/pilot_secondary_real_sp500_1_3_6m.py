"""REAL price (secondary educational-only) 1/3/6-month retrospective experiment.

NOT the original FWB/Euronext licensed PIT/ISIN validation.
Aethereal current-S&P500-membership backfilled to 2021 is SEVERELY
survivorship biased. This script never saves, uploads, prints, or recommends
original ticker prices or selected securities. Original market data is read
in memory solely for research/education; output is aggregate statistics.

Input transformation and source policy were committed BEFORE first experiment
in config/backtest/secondary_aethereal_real_1_3_6m_pilot_2026-11-11.json.
Do NOT change this configuration after seeing any source outcomes.
"""
from __future__ import annotations

import bisect
import csv
import hashlib
import io
import json
import math
from datetime import date
from decimal import Decimal,InvalidOperation
from pathlib import Path

import pilot_real_sp500_backtest_v2 as previous_source
from investresearch.research_sources import parse_ecb
from investresearch.research_historical_1_3_6m import (
    replay_protocol,_one_horizon,
)
from investresearch.research_historical_validation_v2 import preregistered_anchors
from investresearch.research_historical_validation_v3 import v3_protocol

ROOT=Path(__file__).resolve().parents[1]
POLICY_FILE=ROOT/"config/backtest/secondary_aethereal_real_1_3_6m_pilot_2026-11-11.json"
OLD_COHORT_POLICY=ROOT/"config/backtest/v3_secondary_real_history_pilot_2026-11-10.json"
MAX_PRICE_BYTES=110_000_000
MAX_REF_BYTES=300_000
MAX_FX_BYTES=12_000_000
SCHEMA="AETHEREAL_REAL_SOURCE_EXPLORATORY_1_3_6M_V1"


def source_policy():
    p=json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    if (p.get("schema_version")!=
        "AETHEREAL_SP500_US_RESEARCH_1_3_6M_SECONDARY_EXPLORATORY_V1"
        or p["horizons_calendar_months"]!=[1,3,6]
        or p["source_row_cutoff"]!="2026-11-09"
        or p["fx"]["max_previous_calendar_days"]!=5
        or p["research_use_only"] is not True
        or p["predictive_edge_certified"] is not False
        or p["trade_ready"] is not False):
        raise ValueError("Original secondary-source research policy changed")
    return p,hashlib.sha256(POLICY_FILE.read_bytes()).hexdigest()


def dated_ecb_lookup(raw_xml, cutoff, maximum_lag_days):
    original=parse_ecb(raw_xml,date.fromisoformat(cutoff))
    rates={}
    for row in original:
        day=row["date"]
        num=Decimal(row["usd_per_eur"])
        if not num.is_finite() or num<=0 or day in rates:
            raise ValueError("Official original FX duplicate or invalid")
        rates[day]=num
    days=sorted(rates)
    if not days:
        raise ValueError("No official ECB currency sessions")
    cache={}
    def at_or_before(day):
        if day in cache:
            return cache[day]
        idx=bisect.bisect_right(days,day)-1
        if idx<0:
            cache[day]=None
        else:
            dated=days[idx]
            lag=(date.fromisoformat(day)-date.fromisoformat(dated)).days
            cache[day]=(rates[dated],lag) if 0<=lag<=maximum_lag_days else None
        return cache[day]
    return at_or_before


def source_usd_adjusted_to_research_eur(data,selected,fx_for_day,cutoff):
    rdr=csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if rdr.fieldnames!=["date","ticker","open","high","low","close",
                        "adj_close","volume"]:
        raise ValueError("Secondary research price source columns changed")
    out={ticker:[] for ticker in selected}
    seen={ticker:set() for ticker in selected}
    nraw=0;nskip_fx=0;fx_lagged=0;max_fx_lag=0
    wanted=set(selected)
    for row in rdr:
        ticker=row.get("ticker")
        if ticker not in wanted:
            continue
        d=row["date"]
        if d>cutoff:continue
        if d in seen[ticker]:
            raise ValueError("Duplicate historical ticker/date (not authorized)")
        seen[ticker].add(d)
        nraw+=1
        try:
            adj=Decimal(row["adj_close"])
            close=Decimal(row["close"])
            volume=Decimal(row["volume"])
        except (TypeError,InvalidOperation):
            raise ValueError("Non-numeric original source close/volume") from None
        if (not all(x.is_finite() for x in (adj,close,volume))
                or adj<=0 or close<=0 or volume<0):
            raise ValueError("Historical source price/volume invalid")
        rate=fx_for_day(d)
        if rate is None:
            nskip_fx+=1
            continue
        usd_per_eur,lag=rate
        fx_lagged+=int(lag>0)
        max_fx_lag=max(max_fx_lag,lag)
        # Earnings and dividends remain the SOURCE'S retro-adjusted view.
        # Price = adjusted USD / ECB USD-per-EUR at the prior published fix.
        # Turnover = raw close USD * raw shares / ECB USD-per-EUR.
        # Adjust volume so adjusted close*adjusted volume matches turnover.
        out[ticker].append((d,adj/usd_per_eur,volume*close/adj))
    for ticker in out:
        out[ticker].sort(key=lambda x:x[0])
    return out,{
        "original_selected_price_rows":nraw,
        "dropped_rows_no_prior_qualified_ECB":nskip_fx,
        "rows_using_previous_ECB_fix":fx_lagged,
        "max_prior_ECB_fix_lag_calendar_days":max_fx_lag,
        "source_prices_are_retroactively_adjusted_claim_only":True,
        "verified_point_in_time_corporate_actions":False,
    }


def evaluate_secondary_real(raw_prices,raw_current_members,raw_ecb):
    source,policy_digest=source_policy()
    prior=json.loads(OLD_COHORT_POLICY.read_text())
    horizon,registered_digest=replay_protocol()
    v3,_=v3_protocol()
    if (source["sample_source_prior_policy"] !=
        "config/backtest/v3_secondary_real_history_pilot_2026-11-10.json"
        or source["sample_selection"]!=
        "BLIND_SEED_HASH_ASCENDING_40_CURRENT_NOV2026_MEMBERS_ADDED_PRE2021_EXCLUDING_ENERGY_AND_INDUSTRY_OIL"
        or source["lookback"] != "ORIGINAL_BLOCK_B_FROZEN_61_TRADING_SESSIONS"):
        raise ValueError("Aethereal cohort/data method changed after preregistration")
    selection,cohort=previous_source.select_cohort(raw_current_members,prior)
    cutoff=source["source_row_cutoff"]
    lookup=dated_ecb_lookup(raw_ecb,cutoff,
                            source["fx"]["max_previous_calendar_days"])
    panel,coverage=source_usd_adjusted_to_research_eur(
        raw_prices,selection,lookup,cutoff)
    # This is a secondary source research adapter only. NEVER label it as
    # original EXTERNAL FWB/Euronext, a verified ISIN/PIT licensed universe,
    # nor pass it through B's certified source bundle/Decision Engine.
    current={row["ticker"]:row for row in csv.DictReader(
        io.StringIO(raw_current_members.decode("utf-8-sig")))}
    universe={}
    for ticker in selection:
        row=current[ticker]
        universe[ticker]=({
            "id":ticker,"name":row["name"],
            "venue":"XNYS","currency":"USD","asset_type":"EQUITY",
            "sector":row["sector"],"oil_exposure":"none",
            "index_membership_status":"UNKNOWN",
            "listing_date":None,
        },panel[ticker])
    anchors=preregistered_anchors(["XNYS"],v3)
    settings={"exclude_primary_oil":True,"exclude_additional_gold":True,
              "avoid_duplicate_eurostoxx50":True}
    results=[
        _one_horizon(months,anchors,universe,cutoff,horizon,settings)
        for months in (1,3,6)
    ]
    # STRICT AGGREGATE ONLY. Security names and chosen trading pairs
    # are intentionally never printed or persisted in GitHub.
    summaries=[]
    for result in results:
        counts=result["count"]
        summaries.append({
            "months":result["calendar_months"],
            "complete_nonoverlap_folds":counts["matured_complete"],
            "matured_outcome_unresolved_folds":counts["matured_unresolved"],
            "future_pending_folds":counts["future_pending"],
            "overlap_reservations":counts["overlap_reservations"],
            "asof_ineligible_folds":counts["as_of_ineligible"],
            "mean_selected_net":result["mean_selected_net"],
            "mean_selected_pnl_per_10000_eur":result["mean_selected_cash_pnl_eur"],
            "mean_same_K_cost_matched_random_net":result[
                "mean_uniform_random_K_expected_net"],
            "mean_excess_vs_same_K":result["mean_same_K_excess_net"],
            "paired_excess_bootstrap_95_CI":result[
                "primary_paired_fold_bootstrap_CI_95"],
            "mean_rank_IC_per_fold_bootstrap_95_CI":result[
                "rank_ic_bootstrap_CI_95"],
            "percentile_among_10000_random_K":result[
                "selected_random_K_percentile"],
            "complete_data_30_independent_fold_gate":result[
                "minimum_independent_fold_and_complete_data_gate"],
            "predictive_edge_certified":False,
            "trade_ready":False,
        })
    return {
        "schema_version":SCHEMA,
        "status":"ACTUAL_SOURCE_PRICES_ONLY_EDUCATIONAL_SURVIVORSHIP_BIASED_EXPLORATION",
        "price_source_SHA256":hashlib.sha256(raw_prices).hexdigest(),
        "members_source_SHA256":hashlib.sha256(raw_current_members).hexdigest(),
        "ecb_fx_original_SHA256":hashlib.sha256(raw_ecb).hexdigest(),
        "source_research_transformation_policy_sha256":policy_digest,
        "registered_historical_horizon_protocol_SHA256":registered_digest,
        "as_of":cutoff,
        "membership":"CURRENT_S_P_500_MEMBERS_BACKFILLED_SEVERE_SURVIVORSHIP",
        "source_research_only":True,
        "source_adjusted_close_not_a_verified_trade_price":True,
        "source_selection_cohort_size":len(selection),
        "source_quality_aggregate":coverage,
        "historical_selection_model":"UNCHANGED_B_MARKET_SCORE_ON_PRIOR_61_SESSIONS",
        "current_member_reference_not_historical_constituent_universe":True,
        "same_day_versus_prior_ecb_fix_applied":"PRIOR_OR_EQUAL_MAX_5_CALENDAR_DAYS",
        "per_horizon_aggregate_results":summaries,
        "public_report_contains_individual_security_data":False,
        "point_in_time_issuer_ISIN_delisting_and_corporate_action_certified":False,
        "commercial_or_trading_source_use_authorized":False,
        "italian_tax_setoff_eligibility_verified":False,
        "retrospective_results_confirmatory_holdout":False,
        "predictive_edge_certified":False,
        "trade_ready":False,
    }


def main():
    source,_=source_policy()
    paths=source["source_urls"]
    try:
        original_price=previous_source._fetch(paths["prices"],MAX_PRICE_BYTES)
        original_members=previous_source._fetch(paths["current_membership"],MAX_REF_BYTES)
        original_fx=previous_source._fetch(paths["ecb_fx"],MAX_FX_BYTES)
        answer=evaluate_secondary_real(original_price,original_members,original_fx)
    except (OSError,ValueError,TimeoutError,UnicodeError,KeyError,
            previous_source.HTTPError,previous_source.URLError) as exc:
        # Only a fixed error category, NEVER URLs with bearer query strings,
        # individual security IDs, original price rows or downloaded bodies.
        print("SECONDARY_REAL_MULTI_HORIZON_UNAVAILABLE",
              type(exc).__name__,
              "NO_ORIGINAL_OUTCOMES_PRESENTED")
        return 3
    print("AETHEREAL_RESEARCH_EDUCATION_ONLY_CURRENT_S_P500_EXPLORATORY_REAL_PRICE_STUDY")
    print(json.dumps(answer,sort_keys=True))
    print("NO_POINT_IN_TIME_UNIVERSE_NO_ISIN_NO_CORPORATE_ACTION_PROOF")
    print("NO_PREDICTIVE_EVIDENCE_NO_TRADE_NO_ITALIAN_TAX_CLASSIFICATION")
    return 0


if __name__=="__main__":
    raise SystemExit(main())

"""POST-HOC, NON-CONFIRMATORY high-jump sensitivity on exact first real CSVs.

Compares ORIGINAL fail-closed 1/3/6-month cohorts to the same cohorts
revalued with the SOURCE-CLAIMED adjusted-close path even across >=15%
daily jumps. Never changes ex-ante scores, selected assets, windows,
source-vintage hashes or original main protocol acceptance. Vendor-adjusted
daily returns are an *unverified proxy*, not split/dividend/delisting proof.

No tickers, original trade prices or individual positions in public output.
Do not use this experiment to choose weights, instruments or execute orders.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path
from statistics import mean

import pilot_real_sp500_backtest_v2 as previous_source
import pilot_secondary_real_sp500_1_3_6m as original_source
from investresearch.research_historical_1_3_6m import (
    replay_protocol,_one_horizon,_bootstrap,
)
from investresearch.research_historical_validation import _net_trade,_spearman
from investresearch.research_historical_validation_v2 import _eligible,preregistered_anchors
from investresearch.research_historical_validation_v3 import v3_protocol
from investresearch.historical_calendar_v2 import dates_v2

ROOT=Path(__file__).resolve().parents[1]
POLICY_FILE=ROOT/"config/backtest/secondary_real_high_jump_sensitivity_2026-11-11.json"
FROZEN_GIT_BLOB="7459916bb3c4824d3134b236efb39a1261c7c7d6"
SCHEMA="REAL_SOURCE_POSTHOC_JUMP_CENSOR_SENSITIVITY_V1"
CENSORED="MATURED_UNRESOLVED_DO_NOT_DISCARD_MEMBERS"
JUMP="GE15_PERCENT_REAL_CRASH_OR_CORPORATE_ACTION_UNRESOLVED"
GAP="MISSING_ONE_OR_MORE_ORIGINAL_MARKET_SESSIONS"
EXPECTED_ORIGINAL_COUNTS={1:(24,13),3:(5,14),6:(1,9)}


def sensitivity_policy():
    raw=POLICY_FILE.read_bytes()
    blob=b"blob "+str(len(raw)).encode()+b"\x00"+raw
    if hashlib.sha1(blob).hexdigest()!=FROZEN_GIT_BLOB:
        raise ValueError("Post-hoc sensitivity original scope changed after registration")
    policy=json.loads(raw)
    if (policy["posthoc_descriptive_only"] is not True
            or policy["first_actual_source_experiment_already_seen"] is not True
            or policy["first_source_missingness_outcome_already_seen"] is not True
            or policy["frozen_original_horizons_calendar_months"]!=[1,3,6]
            or policy["never_change_original_v1_v2_v3_or_1_3_6m_gate"] is not True
            or policy["acceptance"]["allow_conclusion_about_true_alpha"] is not False):
        raise ValueError("Posthoc sensitivity is not a new confirmatory strategy")
    return policy,hashlib.sha256(raw).hexdigest()


def _source_universe(prices,roster,ecb):
    frozen,_=sensitivity_policy()
    actual={
        "prices":hashlib.sha256(prices).hexdigest(),
        "companies":hashlib.sha256(roster).hexdigest(),
        "ecb_fx":hashlib.sha256(ecb).hexdigest(),
    }
    if actual!=frozen["source_original_SHA256"]:
        raise ValueError("Immutable original real source vintage changed")
    ref_policy=json.loads(previous_source.POLICY.read_text())
    selection,_=previous_source.select_cohort(roster,ref_policy)
    fx=original_source.dated_ecb_lookup(ecb,"2026-11-09",5)
    dated,_=original_source.source_usd_adjusted_to_research_eur(
        prices,selection,fx,"2026-11-09")
    meta={x["ticker"]:x for x in csv.DictReader(
        io.StringIO(roster.decode("utf-8-sig")))}
    universe={
        ticker:(
            {
                "id":ticker,"name":meta[ticker]["name"],
                "venue":"XNYS","currency":"USD","asset_type":"EQUITY",
                "sector":meta[ticker]["sector"],"oil_exposure":"none",
                "index_membership_status":"UNKNOWN",
                "listing_date":None,
            },
            dated[ticker],
        )
        for ticker in selection
    }
    return universe,actual


def _reprice_original_censored(row,universe,policy,settings):
    """The ORIGINAL frozen decision IDs and dates are authoritative.

    Only matured sessions with a valid complete original venue date path
    can receive a vendor-adjusted proxy net return. No missing session is
    imputed; all unchanged original top2 rankings are rechecked at T.
    """
    original_ids=row["as_of_eligible_ids_in_score_order"]
    decision=row["decision_date"]
    selected=row["selected_ids"]
    if (len(original_ids)<3 or len(set(original_ids))!=len(original_ids)
            or selected!=original_ids[:2]
            or set(original_ids)!=set(row["entry_exit_by_id"])):
        raise ValueError("No hindsight membership changes allowed in proxy study")
    by_id={}
    scores=[]
    for uid in original_ids:
        asset,full=universe[uid]
        eligible=_eligible(asset,full,decision,settings)
        if eligible is None or eligible["id"]!=uid:
            raise ValueError("Original frozen ex-ante score cannot be reproduced")
        scores.append(eligible["score"])
        times=row["entry_exit_by_id"][uid]
        entry=times["entry"]
        ending=times["exit"]
        expected=dates_v2(date.fromisoformat(entry),
                          date.fromisoformat(ending),asset["venue"])
        observed=[r for r in full if entry<=r[0]<=ending]
        if (not expected or len(observed)!=len(expected)
                or tuple(r[0] for r in observed)!=expected):
            # The ONLY permissible new proxy is fully observed, never
            # zero-imputed or next-nonmissing prices.
            return None
        costs=policy["costs"]
        net,curve,gross=_net_trade(
            observed,notional=costs["notional_eur"]/2,
            fee_bps=costs["commission_fraction_each_side"],
            min_fee=costs["minimum_commission_eur_each_side"],
            fx_bps=costs["usd_fx_fraction_each_side"],
            usd=asset["currency"]=="USD")
        by_id[uid]={"net":net,"gross":gross}
    if sorted(original_ids,key=lambda uid:(
        -dict(zip(original_ids,scores))[uid],uid))!=original_ids:
        raise ValueError("Posthoc source may not rerank the original as-of cohort")
    selected_ret=mean(by_id[uid]["net"] for uid in selected)
    expected_random=mean(x["net"] for x in by_id.values())
    ic=_spearman(scores,[by_id[uid]["gross"] for uid in original_ids])
    return {
        "date":decision,"selected_net":round(selected_ret,8),
        "same_K_uniform_random_expected_net":round(expected_random,8),
        "same_K_excess_net":round(selected_ret-expected_random,8),
        "ic":round(ic,8) if ic is not None else None,
    }


def _summarize(strict,universe,policy,settings):
    out=[]
    for months,result in zip((1,3,6),strict):
        if result["calendar_months"]!=months:
            raise ValueError("Horizon changed")
        original_counts=result["count"]
        if (original_counts["matured_complete"],
            original_counts["matured_unresolved"])!=EXPECTED_ORIGINAL_COUNTS[months]:
            raise ValueError("Strict original real vintage cohort counts not reproduced")
        complete=[
            {
                "date":f["decision_date"],
                "selected_net":f["selected_net"],
                "same_K_uniform_random_expected_net":f[
                    "same_K_uniform_random_expected_net"],
                "same_K_excess_net":f["same_K_excess_net"],
                "ic":f["ic"],
            }
            for f in result["folds"]
        ]
        proxy=[]
        unresolved_gap=0
        for row in result["as_of_anchor_audit"]:
            if row["state"]!=CENSORED:continue
            reasons=set(row["unresolved_by_id"].values())
            if reasons!={JUMP}:
                unresolved_gap+=1
                continue
            computed=_reprice_original_censored(
                row,universe,policy,settings)
            if computed is None:
                unresolved_gap+=1
            else:
                proxy.append(computed)
        full=sorted(complete+proxy,key=lambda f:f["date"])
        if len(full)+unresolved_gap!=sum(EXPECTED_ORIGINAL_COUNTS[months]):
            raise ValueError("Original matured fold denominator not conserved")
        ci,ic_ci=_bootstrap(
            full,20261121+months,10000)
        return_mean=lambda key:round(mean(f[key] for f in full),8) if full else None
        out.append({
            "months":months,
            "original_strict_completed":len(complete),
            "original_strict_unresolved":original_counts["matured_unresolved"],
            "additional_previously_censored_folds_with_vendor_proxy":len(proxy),
            "still_unresolved_missing_original_sessions":unresolved_gap,
            "descriptive_total_folds_with_vendor_adjusted_proxy":len(full),
            "original_strict_selected_mean_net":result["mean_selected_net"],
            "original_strict_same_K_excess_mean":result["mean_same_K_excess_net"],
            "posthoc_vendor_adjusted_selected_mean_net":return_mean("selected_net"),
            "posthoc_vendor_adjusted_random_same_K_mean_net":return_mean(
                "same_K_uniform_random_expected_net"),
            "posthoc_vendor_adjusted_same_K_excess_mean":return_mean(
                "same_K_excess_net"),
            "posthoc_bootstrap_CI_95_EXPLORATORY_NOT_CONFIRMATORY":ci,
            "posthoc_rank_IC_CI_95_EXPLORATORY":ic_ci,
            "all_source_jumps_verified_independent_corporate_actions":False,
            "can_change_frozen_research_acceptance":False,
        })
    return out


def evaluate_high_jump_sensitivity(prices,roster,ecb):
    registered,hash_=sensitivity_policy()
    universe,source_shas=_source_universe(prices,roster,ecb)
    p,_=replay_protocol()
    v3,_=v3_protocol()
    anchors=preregistered_anchors(["XNYS"],v3)
    settings={"exclude_primary_oil":True,"exclude_additional_gold":True,
              "avoid_duplicate_eurostoxx50":True}
    strict=[_one_horizon(m,anchors,universe,"2026-11-09",p,settings)
            for m in (1,3,6)]
    return {
        "schema_version":SCHEMA,
        "status":"POST_HOC_DESCRIPTIVE_ONLY_V3_1_3_6M_UNVERIFIED_CA",
        "input_source_shas":source_shas,
        "posthoc_registered_protocol_sha256":hash_,
        "never_used_to_refit_or_approve_model":True,
        "source_universe_historical_survivorship_bias":True,
        "all_vendor_adjusted_prices_independently_CA_verified":False,
        "actual_broker_venue_prices_verified":False,
        "horizons":_summarize(strict,universe,p,settings),
        "predictive_edge_certified":False,
        "trade_ready":False,
    }


def main():
    p=sensitivity_policy()[0]
    source=json.loads(original_source.POLICY_FILE.read_text())["source_urls"]
    try:
        prices=previous_source._fetch(source["prices"],original_source.MAX_PRICE_BYTES)
        roster=previous_source._fetch(source["current_membership"],original_source.MAX_REF_BYTES)
        ecb=previous_source._fetch(source["ecb_fx"],original_source.MAX_FX_BYTES)
        result=evaluate_high_jump_sensitivity(prices,roster,ecb)
    except (ValueError,OSError,KeyError,UnicodeError,TimeoutError) as exc:
        print("ORIGINAL_HIGH_JUMP_SOURCE_SENSITIVITY_BLOCKED",
              type(exc).__name__,"NO_UPDATED_OR_SUBSTITUTED_SOURCE_OR_NEW_ALPHA")
        return 3
    print("POST_HOC_REAL_ADJUSTED_VENDOR_PRICE_HIGH_JUMP_STRESS_ONLY")
    print(json.dumps(result,sort_keys=True))
    print("NEVER_MODEL_ALPHA_OR_BROKER_PRICE_CONFIRMATION")
    return 0


if __name__=="__main__":
    raise SystemExit(main())

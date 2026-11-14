"""Aggregate diagnosis of unresolved folds in the FIRST real-price study.

Reads only the exact ORIGINAL immutable Aethereal/roster/ECB vintage already
used in the 11 Nov 2026 1/3/6-month study; refuses changed bytes. Never
prints asset IDs, selections, source rows, original prices, or a new alpha
estimate. This analysis identifies missing-data mechanics, not returns or
retuned research parameters.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pilot_real_sp500_backtest_v2 as original
import pilot_secondary_real_sp500_1_3_6m as pilot
from investresearch.research_historical_1_3_6m import (
    replay_protocol,_one_horizon,
)
from investresearch.research_historical_validation_v2 import preregistered_anchors
from investresearch.research_historical_validation_v3 import v3_protocol

REASONS=(
    "MISSING_ONE_OR_MORE_ORIGINAL_MARKET_SESSIONS",
    "GE15_PERCENT_REAL_CRASH_OR_CORPORATE_ACTION_UNRESOLVED",
)
PAST_FOLD_COUNTS={1:(24,13),3:(5,14),6:(1,9)}


def reason_counts(report):
    results=[]
    for horizon in report:
        months=horizon["calendar_months"]
        count=horizon["count"]
        if months not in (1,3,6):
            raise ValueError("Unregistered historical horizon")
        by_type={key:0 for key in REASONS}
        affected_members=set()
        mixed=0
        source_missing=0
        suspect_jump=0
        for row in horizon["as_of_anchor_audit"]:
            if row["state"]!="MATURED_UNRESOLVED_DO_NOT_DISCARD_MEMBERS":
                continue
            causes=row.get("unresolved_by_id")
            if not isinstance(causes,dict) or not causes:
                raise ValueError("Censored original as-of cohort lost source reasons")
            reasons=set(causes.values())
            if not reasons.issubset(REASONS):
                raise ValueError("Unexpected unsupported censored original reason")
            mixed+=int(len(reasons)>1)
            source_missing+=int(REASONS[0] in reasons)
            suspect_jump+=int(REASONS[1] in reasons)
            for uid,cause in causes.items():
                by_type[cause]+=1
                affected_members.add(uid)
        if (source_missing+suspect_jump-mixed<count["matured_unresolved"]
                or count["matured_complete"]+count["matured_unresolved"]<=0):
            raise ValueError("Original matured-missing denominator inconsistent")
        results.append({
            "months":months,
            "complete_original_folds":count["matured_complete"],
            "unresolved_original_folds":count["matured_unresolved"],
            "incomplete_folds_with_missing_venue_session":source_missing,
            "incomplete_folds_with_unverified_ge15pct_jump":suspect_jump,
            "incomplete_folds_with_both_types":mixed,
            "missing_session_asset_fold_events":by_type[REASONS[0]],
            "unverified_ge15_jump_asset_fold_events":by_type[REASONS[1]],
            "distinct_affected_research_ids_never_disclosed":len(affected_members),
            "exact_market_crashes_vs_splits_independently_resolved":False,
            "future_source_outcomes_repaired":False,
            "retrospective_complete_case_returns_promoted_to_alpha":False,
        })
    return results


def investigate_original_vintage(prices,roster,ecb):
    actual={
        "prices":hashlib.sha256(prices).hexdigest(),
        "members":hashlib.sha256(roster).hexdigest(),
        "ecb":hashlib.sha256(ecb).hexdigest(),
    }
    if actual!=pilot.FIRST_OBSERVED_SOURCE_SHA256:
        raise ValueError("First historical REAL input vintage no longer available")
    policy=json.loads(original.POLICY.read_text())
    selection,diagnostic=original.select_cohort(roster,policy)
    dates=pilot.dated_ecb_lookup(ecb,"2026-11-09",5)
    panel,quality=pilot.source_usd_adjusted_to_research_eur(
        prices,selection,dates,"2026-11-09")
    if len(selection)!=40:
        raise ValueError("Original cohort not reproducible from frozen reference")
    current={rec["ticker"]:rec for rec in csv.DictReader(
        io.StringIO(roster.decode("utf-8-sig")))}
    universe={
        symbol:({
            "id":symbol,"name":current[symbol]["name"],
            "venue":"XNYS","currency":"USD","asset_type":"EQUITY",
            "sector":current[symbol]["sector"],"oil_exposure":"none",
            "index_membership_status":"UNKNOWN","listing_date":None,
        },panel[symbol])
        for symbol in selection
    }
    registered,_=replay_protocol()
    v3,_=v3_protocol()
    anchors=preregistered_anchors(["XNYS"],v3)
    settings={"exclude_primary_oil":True,"exclude_additional_gold":True,
              "avoid_duplicate_eurostoxx50":True}
    audit=[
        _one_horizon(m,anchors,universe,"2026-11-09",registered,settings)
        for m in (1,3,6)
    ]
    counts=reason_counts(audit)
    for row in counts:
        expected=PAST_FOLD_COUNTS[row["months"]]
        if (row["complete_original_folds"],row["unresolved_original_folds"])!=expected:
            raise ValueError("Old frozen 1/3/6m complete-case counts were not reproduced")
    return {
        "schema_version":"FIRST_ORIGINAL_REAL_STUDY_MATURED_MISSINGNESS_AUDIT_V1",
        "status":"ORIGINAL_SOURCE_VINTAGE_MATCH_ONLY_MISSINGNESS_DIAGNOSTIC",
        "price_sha256":actual["prices"],
        "roster_sha256":actual["members"],
        "ecb_sha256":actual["ecb"],
        "source_current_member_survivorship_bias":True,
        "eligible_security_identifiers_and_prices_not_output":True,
        "no_research_model_or_outcome_parameter_tuned":True,
        "per_horizon":counts,
        "actual_corporate_actions_and_delisted_returns_reconciled":False,
        "trade_ready":False,
    }


def main():
    sources=json.loads(pilot.POLICY_FILE.read_text())["source_urls"]
    try:
        prices=original._fetch(sources["prices"],pilot.MAX_PRICE_BYTES)
        roster=original._fetch(sources["current_membership"],pilot.MAX_REF_BYTES)
        ecb=original._fetch(sources["ecb_fx"],pilot.MAX_FX_BYTES)
        report=investigate_original_vintage(prices,roster,ecb)
    except (ValueError,OSError,UnicodeError,KeyError,TimeoutError) as exc:
        print("ORIGINAL_REAL_PRICE_VINTAGE_NOT_AVAILABLE_FOR_MISSINGNESS_DIAGNOSTIC",
              type(exc).__name__,"NO_REPLACEMENT_SOURCE_OR_NEW_RETURN_SCORES")
        return 3
    print("ORIGINAL_REAL_PRICE_MATURITY_MISSINGNESS_ONLY")
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
